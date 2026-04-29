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
    STATIONS_API_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
    TRIP_API_URL,
    VIRTUAL_TRAIN_API_URL,
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
        # Whether the first composition error of the current refresh has
        # already been logged at warning level. Reset per refresh.
        self._composition_warned: bool = False

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
                    # First failure of the run is logged at warning level
                    # so the user can see access/rate-limit problems
                    # without having to enable debug logging.
                    if not self._composition_warned:
                        self._composition_warned = True
                        _LOGGER.warning(
                            "Journey composition fetch failed: HTTP %s for train %s. "
                            "Check that your NS API key has access to the "
                            "/reisinformatie-api/api/v3/journey endpoint.",
                            resp.status, train_number,
                        )
                    else:
                        _LOGGER.debug(
                            "Journey composition fetch %s -> HTTP %s",
                            train_number, resp.status,
                        )
                    self._composition_cache[train_number] = None
                    return None
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            if not self._composition_warned:
                self._composition_warned = True
                _LOGGER.warning(
                    "Journey composition fetch failed for train %s: %s",
                    train_number, err,
                )
            else:
                _LOGGER.debug(
                    "Journey composition fetch %s failed: %s", train_number, err
                )
            self._composition_cache[train_number] = None
            return None

        # /v2/journey returns composition per-stop, not at the payload
        # root. Pick the origin stop (status=ORIGIN, falls back to the
        # first stop) and read its actualStock or plannedStock.
        payload = (data or {}).get("payload") or {}
        stops = payload.get("stops") or []
        origin_stop = next((s for s in stops if s.get("status") == "ORIGIN"), None) or (stops[0] if stops else {})
        stock = origin_stop.get("actualStock") or origin_stop.get("plannedStock") or {}
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
        # Reset cache and warning gate at the start of this refresh
        self._composition_cache = {}
        self._composition_warned = False

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

    # ---- live train map helpers ----
    #
    # These are NOT polled. They are called on-demand by WebSocket
    # commands when the user opens the map dialog in the card. The
    # stations geo lookup is cached in hass.data[DOMAIN]["_stations_geo"]
    # so it is fetched at most once per HA boot.

    async def async_fetch_stations_geo(self) -> dict[str, dict]:
        """Return a {code: {name, lat, lng}} map. Cached on hass.data."""
        bucket = self.hass.data.setdefault(DOMAIN, {})
        cached = bucket.get("_stations_geo")
        if cached:
            return cached
        if not self.api_key:
            return {}
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        try:
            async with async_timeout.timeout(20):
                async with self._session.get(STATIONS_API_URL, headers=headers) as resp:
                    if resp.status != 200:
                        _LOGGER.warning(
                            "Stations API returned status %s", resp.status,
                        )
                        return {}
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Stations API unreachable: %s", err)
            return {}

        out: dict[str, dict] = {}
        # /v2/stations payload shape: {"payload": [ {code, namen:{lang,middel,kort}, land, lat, lng, ...}, ... ]}
        payload = (data or {}).get("payload") or []
        for st in payload:
            code = (st.get("code") or "").upper()
            if not code:
                continue
            namen = st.get("namen") or {}
            name = namen.get("lang") or namen.get("middel") or namen.get("kort") or code
            lat = st.get("lat")
            lng = st.get("lng")
            if lat is None or lng is None:
                continue
            out[code] = {"name": name, "lat": float(lat), "lng": float(lng)}
        bucket["_stations_geo"] = out
        _LOGGER.debug("Stations geo cache: %d entries", len(out))
        return out

    async def async_fetch_live_train(self, train_number: str) -> dict | None:
        """Fetch the live position of a single train.

        The per-train endpoint /virtual-train-api/v1/trein/{nr} returns
        composition + current-station info but NO GPS coordinates. The
        bulk endpoint /virtual-train-api/v1/trein (no number) returns
        an array of every currently moving train with lat/lng/speed/
        heading. We fetch the bulk feed (cached briefly to avoid hitting
        the API per poll) and filter by ritnummer.
        """
        if not train_number:
            return None
        if not self.api_key:
            return None
        all_trains = await self._async_fetch_live_trains_bulk()
        if not all_trains:
            return None
        target = str(train_number)
        match = next(
            (
                t for t in all_trains
                if str(t.get("ritnummer") or t.get("treinNummer") or "") == target
            ),
            None,
        )
        if not match:
            return None
        lat = match.get("lat") or match.get("latitude")
        lng = match.get("lng") or match.get("lon") or match.get("longitude")
        if lat is None or lng is None:
            return None
        return {
            "lat": float(lat),
            "lng": float(lng),
            "speed": match.get("snelheid") or match.get("speed"),
            "heading": match.get("richting") or match.get("heading"),
            "ts": match.get("tijd") or match.get("time"),
            "type": match.get("type") or match.get("categorie"),
        }

    async def _async_fetch_live_trains_bulk(self) -> list[dict]:
        """Fetch every active train, with a 5s in-memory cache.

        Cache is kept on hass.data so all per-route coordinators share
        it — a 10s polling interval from the card therefore translates
        to one bulk API call per ~10s regardless of how many maps are
        open.
        """
        bucket = self.hass.data.setdefault(DOMAIN, {})
        cached = bucket.get("_live_trains_cache")
        now = time.time()
        if cached and now - cached.get("ts", 0) < 5:
            return cached.get("data") or []

        warned_once = bool(bucket.get("_live_train_warned"))
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        try:
            async with async_timeout.timeout(15):
                async with self._session.get(
                    VIRTUAL_TRAIN_API_URL, headers=headers
                ) as resp:
                    if resp.status != 200:
                        body = ""
                        try:
                            body = (await resp.text())[:400]
                        except Exception:  # noqa: BLE001
                            pass
                        if not warned_once:
                            bucket["_live_train_warned"] = True
                            _LOGGER.warning(
                                "Virtual train bulk fetch returned HTTP %s. "
                                "Check that your NS API key is subscribed to "
                                "the 'Ns-App' (Virtual Train API) product. "
                                "Body: %s",
                                resp.status, body,
                            )
                        bucket["_live_trains_cache"] = {"ts": now, "data": []}
                        return []
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            if not warned_once:
                bucket["_live_train_warned"] = True
                _LOGGER.warning("Virtual train bulk fetch failed: %s", err)
            return []

        # Response shape can be either a bare list, {"payload": [...]}
        # or {"treinen": [...]}. Be liberal.
        if isinstance(data, list):
            trains = data
        elif isinstance(data, dict):
            trains = (
                data.get("payload")
                or data.get("treinen")
                or data.get("trains")
                or []
            )
        else:
            trains = []
        if not trains and not warned_once:
            bucket["_live_train_warned"] = True
            snippet = str(data)[:400]
            _LOGGER.warning(
                "Virtual train bulk fetch: 200 OK but no train list found. "
                "Response shape: %s",
                snippet,
            )
        bucket["_live_trains_cache"] = {"ts": now, "data": trains}
        return trains
