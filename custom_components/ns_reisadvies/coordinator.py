"""DataUpdateCoordinator for the NS Reisadvies integration."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    API_URL,
    DOMAIN,
    JOURNEY_API_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
    TRIP_API_URL,
)

_LOGGER = logging.getLogger(__name__)

class NSUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches NS travel advice and manages favourites."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        from_station: str,
        to_station: str,
        scan_interval_minutes: int = 5,
        fav_hours: int = 6,
        fetch_composition: bool = False,
    ) -> None:
        self.api_key = api_key
        self.from_station = from_station
        self.to_station = to_station
        self.fav_hours = fav_hours
        self.fetch_composition = fetch_composition

        # Central in-memory store for pinned favourites.
        # Mapping: ctx_recon -> epoch seconds at which it was pinned.
        self.tracked_trips: dict[str, float] = {}

        # Train composition cache: train_number -> dict (per refresh).
        # Cleared at the start of each _async_update_data run so that
        # the same train fetched twice in one refresh hits the cache.
        self._composition_cache: dict[str, dict | None] = {}

        # Persistent storage so favourites survive a Home Assistant restart.
        self._store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{from_station}_{to_station}"
        )

        # Re-use Home Assistant's shared aiohttp client.
        self._session = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=max(1, int(scan_interval_minutes))),
        )

    # ---- persistent storage helpers ----

    async def async_load_tracked(self) -> None:
        """Load the tracked-trips dict from disk."""
        data = await self._store.async_load()
        if isinstance(data, dict):
            # Backwards compatibility: an older version persisted a list.
            if isinstance(data.get("trips"), list):
                now = time.time()
                self.tracked_trips = {ctx: now for ctx in data["trips"]}
            elif isinstance(data.get("trips"), dict):
                self.tracked_trips = {k: float(v) for k, v in data["trips"].items()}

    async def _async_save_tracked(self) -> None:
        await self._store.async_save({"trips": self.tracked_trips})

    # ---- public API: track / untrack ----

    def track_trip(self, ctx_recon: str) -> None:
        """Pin a trip as a favourite."""
        if not ctx_recon:
            return
        if ctx_recon not in self.tracked_trips:
            self.tracked_trips[ctx_recon] = time.time()
            self.hass.async_create_task(self._async_save_tracked())
            self.hass.async_create_task(self.async_request_refresh())

    def untrack_trip(self, ctx_recon: str) -> None:
        """Unpin a previously favourited trip."""
        if ctx_recon in self.tracked_trips:
            self.tracked_trips.pop(ctx_recon, None)
            self.hass.async_create_task(self._async_save_tracked())
            self.hass.async_create_task(self.async_request_refresh())

    # ---- expiry ----

    def _expire_old_trips(self) -> list[str]:
        """Remove favourites that were pinned longer ago than fav_hours."""
        if not self.fav_hours or self.fav_hours <= 0:
            return []
        limit = self.fav_hours * 3600
        now = time.time()
        expired = [ctx for ctx, ts in self.tracked_trips.items() if now - ts > limit]
        for ctx in expired:
            self.tracked_trips.pop(ctx, None)
        if expired:
            _LOGGER.debug("Removed expired favourites: %s", expired)
            self.hass.async_create_task(self._async_save_tracked())
        return expired

    # ---- composition (train carriages) ----

    async def _fetch_journey_composition(self, train_number: str, headers: dict) -> dict | None:
        """Fetch carriage composition for a single train number.

        Returns a slim dict suitable for the sensor attributes:
          {
            "trainType": "VIRM IV",
            "numberOfParts": 6,
            "numberOfSeats": 580,
            "shorter": false,
            "parts": [
              {"image": "https://.../virm-iv.png", "type": "VIRM-IV"},
              ...
            ]
          }

        Cached per train_number for the duration of a single refresh.
        Returns None on any error so the rest of the trip still renders.
        """
        if not train_number:
            return None
        if train_number in self._composition_cache:
            return self._composition_cache[train_number]
        try:
            async with self._session.get(
                JOURNEY_API_URL,
                headers=headers,
                params={"train": train_number, "omitCrowdForecast": "true"},
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "Journey composition fetch %s -> HTTP %s", train_number, resp.status
                    )
                    self._composition_cache[train_number] = None
                    return None
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Journey composition fetch %s failed: %s", train_number, err)
            self._composition_cache[train_number] = None
            return None

        payload = (data or {}).get("payload") or {}
        stock = payload.get("actualStock") or payload.get("plannedStock") or {}
        train_parts = stock.get("trainParts") or []
        slim = {
            "trainType": stock.get("trainType"),
            "numberOfParts": stock.get("numberOfParts") or len(train_parts) or None,
            "numberOfSeats": stock.get("numberOfSeats"),
            "numberOfFirstClassSeats": stock.get("numberOfFirstClassSeats"),
            "shorter": bool(stock.get("hasSignificantChange")) or False,
            "parts": [
                {
                    "image": (p.get("image") or {}).get("uri"),
                    "type": p.get("type") or stock.get("trainType"),
                    "stockIdentifier": p.get("stockIdentifier"),
                }
                for p in train_parts
                if (p.get("image") or {}).get("uri") or p.get("type")
            ],
        }
        # Drop entirely empty results
        if not slim["parts"] and not slim["numberOfParts"]:
            self._composition_cache[train_number] = None
            return None
        self._composition_cache[train_number] = slim
        return slim

    async def _annotate_compositions(self, all_trips: list[dict], headers: dict) -> None:
        """Add a `composition` field to every leg with a known train number."""
        if not self.fetch_composition:
            return
        # Reset cache at the start of this refresh
        self._composition_cache = {}

        # Collect unique train numbers across all legs
        train_numbers: set[str] = set()
        for trip in all_trips:
            for leg in trip.get("legs") or []:
                num = (leg.get("product") or {}).get("number")
                if num:
                    train_numbers.add(str(num))

        if not train_numbers:
            return

        async def _fetch_and_store(num: str):
            comp = await self._fetch_journey_composition(num, headers)
            return num, comp

        results = await asyncio.gather(*(_fetch_and_store(n) for n in train_numbers))
        results_map = {n: c for n, c in results}

        for trip in all_trips:
            for leg in trip.get("legs") or []:
                num = (leg.get("product") or {}).get("number")
                if not num:
                    continue
                comp = results_map.get(str(num))
                if comp:
                    leg["composition"] = comp

    # ---- data fetch ----

    async def _async_update_data(self):
        """Fetch trips and pinned favourites from the NS API."""
        # Prune expired favourites first so we do not refetch them.
        self._expire_old_trips()

        if not self.api_key:
            raise UpdateFailed("No NS API key configured")

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {
            "fromStation": self.from_station,
            "toStation": self.to_station,
            "dateTime": datetime.now().isoformat(),
        }

        try:
            async with async_timeout.timeout(20):
                # 1) Standard trip query for the configured route.
                async with self._session.get(API_URL, headers=headers, params=params) as response:
                    if response.status != 200:
                        raise UpdateFailed(
                            f"NS travel advice API returned status {response.status}"
                        )
                    data = await response.json()
                    normal_trips = data.get("trips", []) or []

                # 2) Pinned favourites — fetched in parallel.
                # Trips that the API no longer recognises (400/404) are pruned.
                tracked_trips_data: list[dict] = []
                trips_to_remove: set[str] = set()

                async def _fetch_one(ctx: str):
                    try:
                        async with self._session.get(
                            TRIP_API_URL,
                            headers=headers,
                            params={"ctxRecon": ctx},
                        ) as resp:
                            if resp.status == 200:
                                return ("ok", ctx, await resp.json())
                            if resp.status in (400, 404):
                                return ("gone", ctx, None)
                            return ("skip", ctx, None)
                    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                        _LOGGER.debug("Failed to fetch favourite %s: %s", ctx, err)
                        return ("skip", ctx, None)

                if self.tracked_trips:
                    results = await asyncio.gather(
                        *(_fetch_one(c) for c in list(self.tracked_trips))
                    )
                    for status, ctx, payload in results:
                        if status == "ok" and payload is not None:
                            tracked_trips_data.append(payload)
                        elif status == "gone":
                            trips_to_remove.add(ctx)

                if trips_to_remove:
                    for ctx in trips_to_remove:
                        self.tracked_trips.pop(ctx, None)
                    await self._async_save_tracked()

                # 3) Merge — avoid duplicates by ctxRecon.
                normal_ctx_recons = {
                    t.get("ctxRecon") for t in normal_trips if t.get("ctxRecon")
                }
                all_trips = list(normal_trips)
                for tracked_trip in tracked_trips_data:
                    ctx = tracked_trip.get("ctxRecon")
                    if ctx and ctx not in normal_ctx_recons:
                        all_trips.append(tracked_trip)

                all_trips.sort(
                    key=lambda x: (
                        x.get("legs") or [{}]
                    )[0].get("origin", {}).get("plannedDateTime", "")
                )

                # Optional: annotate each leg with carriage composition.
                # Mutates legs in place by adding a `composition` key.
                if self.fetch_composition:
                    await self._annotate_compositions(all_trips, headers)

                return all_trips

        except UpdateFailed:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Could not reach NS API: {err}") from err
