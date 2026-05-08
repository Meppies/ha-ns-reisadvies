"""DataUpdateCoordinator for the NS Reisadvies integration."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    API_URL,
    ARCGIS_TREINEN_URL,
    DOMAIN,
    JOURNEY_API_URL,
    PRORAIL_RAIL_URL,
    STATIONS_API_URL,
    STORAGE_KEY,
    STORAGE_VERSION,
    TRIP_API_URL,
    VIRTUAL_TRAIN_API_URL,
    VIRTUAL_TRAIN_VEHICLE_URL,
    VIRTUAL_TRAIN_VEHICLE_FALLBACK_URL,
)

if TYPE_CHECKING:
    from .types import NSConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_validate_api_key(hass: HomeAssistant, api_key: str) -> str | None:
    """Probe the NS API with the supplied key.

    Returns ``None`` on success, or a config-flow error code:

    * ``"invalid_auth"`` — key was rejected (HTTP 401/403).
    * ``"cannot_connect"`` — network failure or other 5xx.

    Used by the config flow to satisfy the Bronze quality-scale rule
    ``test-before-configure``: validate the credentials with the
    upstream service before creating the entry.
    """
    if not api_key or not api_key.strip():
        return "invalid_auth"
    session = async_get_clientsession(hass)
    headers = {"Ocp-Apim-Subscription-Key": api_key.strip()}
    try:
        async with async_timeout.timeout(15):
            # /v2/stations is the lightest authenticated endpoint NS
            # exposes — it's a static catalogue, no per-call cost, but
            # still requires the subscription key. Perfect for a probe.
            async with session.get(STATIONS_API_URL, headers=headers) as resp:
                if resp.status in (401, 403):
                    return "invalid_auth"
                if resp.status >= 500:
                    return "cannot_connect"
                if resp.status != 200:
                    _LOGGER.warning(
                        "NS API probe returned unexpected status %s", resp.status,
                    )
                    return "cannot_connect"
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.debug("NS API probe failed: %s", err)
        return "cannot_connect"
    return None

class NSUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches NS travel advice and manages favourites."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: NSConfigEntry | None = None,
        api_key: str,
        from_station: str,
        to_station: str,
        scan_interval_minutes: int = 5,
        fav_hours: int = 6,
        fetch_composition: bool = False,
    ) -> None:
        # The hub config entry; used to read/write
        # ``entry.runtime_data.stations_geo`` (the per-HA-boot stations
        # geo cache). Optional for back-compat with older callers /
        # tests that constructed a coordinator without an entry.
        self._entry = entry
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

        # Edge-detection for the Silver "log-when-unavailable" quality-
        # scale rule. ``None`` means we haven't observed an outcome yet;
        # otherwise it tracks the last refresh's success/failure and
        # we only emit a log line on transitions.
        self._was_available: bool | None = None

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
                            "/reisinformatie-api/api/v2/journey endpoint.",
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

        async def _fetch_and_store(num: str) -> tuple[str, dict[str, Any] | None]:
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

    def _note_unavailable(self, reason: str) -> None:
        """Log once when we transition into the unavailable state.

        Silver quality-scale rule ``log-when-unavailable``: log on the
        edge, not on every refresh, so the journal isn't spammed during
        a long upstream outage.
        """
        if self._was_available is False:
            return
        _LOGGER.warning(
            "NS Reisadvies (%s -> %s) is unavailable: %s",
            self.from_station, self.to_station, reason,
        )
        self._was_available = False

    def _note_available(self) -> None:
        """Log once when we recover from a previous outage."""
        if self._was_available is None:
            self._was_available = True
            return
        if self._was_available is False:
            _LOGGER.info(
                "NS Reisadvies (%s -> %s) is back online",
                self.from_station, self.to_station,
            )
        self._was_available = True

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch trips and pinned favourites from the NS API."""
        # Prune expired favourites first so we do not refetch them.
        self._expire_old_trips()

        if not self.api_key:
            self._note_unavailable("no API key configured")
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
                    if response.status in (401, 403):
                        # Silver rule ``reauthentication-flow``: bubble
                        # auth failures up so HA opens the reauth form.
                        self._note_unavailable(
                            f"NS API rejected the key (HTTP {response.status})"
                        )
                        raise ConfigEntryAuthFailed(
                            f"NS API rejected the API key (HTTP {response.status})"
                        )
                    if response.status != 200:
                        self._note_unavailable(
                            f"NS API returned HTTP {response.status}"
                        )
                        raise UpdateFailed(
                            f"NS travel advice API returned status {response.status}"
                        )
                    data = await response.json()
                    normal_trips = data.get("trips", []) or []

                # 2) Pinned favourites — fetched in parallel.
                # Trips that the API no longer recognises (400/404) are pruned.
                tracked_trips_data: list[dict] = []
                trips_to_remove: set[str] = set()

                async def _fetch_one(
                    ctx: str,
                ) -> tuple[str, str, dict[str, Any] | None]:
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

                self._note_available()
                return all_trips

        except (UpdateFailed, ConfigEntryAuthFailed):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            self._note_unavailable(f"network error: {err}")
            raise UpdateFailed(f"Could not reach NS API: {err}") from err

    # ---- live train map helpers ----
    #
    # These are NOT polled. They are called on-demand by WebSocket
    # commands when the user opens the map dialog in the card. The
    # stations geo lookup is cached on the hub's runtime_data so it is
    # fetched at most once per integration setup.

    async def async_fetch_stations_geo(self) -> dict[str, dict]:
        """Return a {code: {name, lat, lng}} map. Cached on runtime_data."""
        runtime = (
            getattr(self._entry, "runtime_data", None)
            if self._entry is not None
            else None
        )
        if runtime is not None and runtime.stations_geo:
            return runtime.stations_geo
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
        # /v2/stations payload shape: {"payload": [ {code, UICCode, namen:{lang,middel,kort}, land, lat, lng, ...}, ... ]}
        # We index by NS short code AND UIC code so callers can look up
        # stops returned by /v3/trips (uicCode) or /v2/journey (stationCode).
        payload = (data or {}).get("payload") or []
        for st in payload:
            code = (st.get("code") or "").upper()
            uic = str(st.get("UICCode") or st.get("uicCode") or "")
            if not code and not uic:
                continue
            namen = st.get("namen") or {}
            name = namen.get("lang") or namen.get("middel") or namen.get("kort") or code or uic
            lat = st.get("lat")
            lng = st.get("lng")
            if lat is None or lng is None:
                continue
            entry = {"name": name, "lat": float(lat), "lng": float(lng), "code": code, "uic": uic}
            if code:
                out[code] = entry
            if uic:
                out[uic] = entry
        if runtime is not None:
            runtime.stations_geo = out
        _LOGGER.debug("Stations geo cache: %d entries (code+UIC)", len(out))
        return out

    async def async_fetch_full_rail_network(self) -> dict | None:
        """Download every ProRail Spoorbaanhartlijn feature in NL.

        Returns a GeoJSON FeatureCollection or None on hard failure.
        Pages through the FeatureServer in chunks of 2000 — the server
        caps each request to that size — until exhausted.
        """
        features: list[dict] = []
        offset = 0
        page_size = 2000
        max_pages = 20  # safety cap (~40 000 features)
        while True:
            params = {
                "where": "1=1",
                "outSR": "4326",
                "outFields": "GEOCODE_NAAM",
                "f": "geojson",
                "resultOffset": str(offset),
                "resultRecordCount": str(page_size),
                "returnGeometry": "true",
            }
            try:
                async with async_timeout.timeout(60):
                    async with self._session.get(
                        PRORAIL_RAIL_URL, params=params,
                    ) as resp:
                        if resp.status != 200:
                            _LOGGER.warning(
                                "ProRail rail network fetch HTTP %s at offset %s",
                                resp.status, offset,
                            )
                            return None
                        page = await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.warning("ProRail rail network fetch failed: %s", err)
                return None
            page_feats = (page or {}).get("features") or []
            features.extend(page_feats)
            if len(page_feats) < page_size:
                break
            offset += page_size
            if offset >= page_size * max_pages:
                _LOGGER.warning(
                    "ProRail rail network: hit %d-page safety cap, stopping",
                    max_pages,
                )
                break
        if not features:
            return None
        _LOGGER.info(
            "ProRail rail network downloaded: %d features", len(features),
        )
        return {"type": "FeatureCollection", "features": features}

    async def async_fetch_arcgis_position(self, train_number: str) -> dict | None:
        """Live train GPS via ProRail's public ArcGIS NS_treinlocaties.

        Returns smooth lat/lng + speed (km/h) + heading (degrees) +
        epoch-ms timestamp, the same feed treinposities.nl uses. No NS
        API key required for this endpoint. The query filters on
        ``treinNummer`` so we get exactly the user's run, not a random
        rotation that shares the ritnummer.
        """
        if not train_number:
            return None
        try:
            target = int(str(train_number).strip())
        except (TypeError, ValueError):
            return None
        try:
            async with async_timeout.timeout(10):
                async with self._session.get(
                    ARCGIS_TREINEN_URL,
                    params={
                        "where": f"treinNummer={target}",
                        "outFields": "treinNummer,lat,lng,snelheid,richting,Tijd,Stationsnaam,type,ritId",
                        "f": "json",
                        "resultRecordCount": "1",
                    },
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.debug(
                            "ArcGIS treinlocaties %s -> HTTP %s",
                            target, resp.status,
                        )
                        return None
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("ArcGIS fetch %s failed: %s", target, err)
            return None

        feats = (data or {}).get("features") or []
        if not feats:
            return None
        attrs = feats[0].get("attributes") or {}
        lat = attrs.get("lat")
        lng = attrs.get("lng")
        if lat is None or lng is None:
            return None
        return {
            "lat": float(lat),
            "lng": float(lng),
            "speed": attrs.get("snelheid"),
            "heading": attrs.get("richting"),
            "ts_ms": attrs.get("Tijd"),
            "station_name": attrs.get("Stationsnaam") or None,
            "train_type": attrs.get("type"),
            "rit_id": attrs.get("ritId"),
            "source": "prorail-obis",
        }

    async def async_fetch_journey_route(self, train_number: str) -> list[dict]:
        """Return the FULL list of stops the given train makes today.

        Each stop includes name + lat/lng + a `passed` flag so the card
        can split the route polyline into yellow (already-travelled) and
        blue (still-to-go) segments.
        """
        if not train_number or not self.api_key:
            return []
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        try:
            async with async_timeout.timeout(15):
                async with self._session.get(
                    JOURNEY_API_URL,
                    headers=headers,
                    params={"train": str(train_number), "omitCrowdForecast": "true"},
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return []

        payload = (data or {}).get("payload") or {}
        stops_raw = payload.get("stops") or []
        if not stops_raw:
            return []

        geo = await self.async_fetch_stations_geo()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        def _passed(stop: dict) -> bool:
            # Trust an explicit status value first.
            status = (stop.get("status") or "").upper()
            if status in {"PASSED", "PASSING_PASSED", "DEPARTED"}:
                return True
            # Otherwise derive from the actual departure time. For the
            # destination there is no departure, so use actualArrival.
            for key in ("actualDepartureDateTime", "actualArrivalDateTime",
                        "plannedDepartureDateTime", "plannedArrivalDateTime"):
                ts = stop.get(key)
                if not ts:
                    continue
                try:
                    # NS uses ISO-8601 with offset. fromisoformat handles
                    # "+0200" since Python 3.11; otherwise normalise.
                    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if "Departure" in key:
                    return parsed < now
                # arrival of destination — only "passed" if we are well
                # past it.
                return parsed < now
            return False

        # Build a name lookup once so we can resolve stops whose codes
        # do not match the /v2/stations cache (rare but happens with
        # foreign or recently renamed stations).
        by_name = {v["name"].casefold(): v for v in geo.values()}

        out: list[dict] = []
        unresolved: list[str] = []
        for stop in stops_raw:
            station = stop.get("station") or {}
            uic = str(station.get("uicCode") or stop.get("uicCode") or "")
            code = (
                station.get("stationCode")
                or stop.get("stationCode")
                or station.get("code")
                or ""
            ).upper()
            stop_name = (
                station.get("name") or stop.get("name") or ""
            ).strip()
            geo_entry = (
                (geo.get(uic) if uic else None)
                or (geo.get(code) if code else None)
                or (by_name.get(stop_name.casefold()) if stop_name else None)
            )
            if not geo_entry:
                if stop_name or code or uic:
                    unresolved.append(stop_name or code or uic)
                continue
            out.append({
                "name": geo_entry["name"],
                "lat": geo_entry["lat"],
                "lng": geo_entry["lng"],
                "uicCode": uic,
                "code": code,
                "passed": _passed(stop),
                "status": (stop.get("status") or "").upper(),
            })
        if unresolved:
            _LOGGER.debug(
                "Train %s journey: %d stops resolved, %d skipped: %s",
                train_number, len(out), len(unresolved), unresolved,
            )
        return out

    async def async_fetch_live_train(
        self, train_number: str, anchor_iso: str | None = None
    ) -> dict | None:
        """Return the live GPS position for a single train.

        Primary: /virtual-train-api/vehicle?route=<ritnummer> — the same
        feed the NS App uses for the live train map. Returns smooth
        lat/lng plus speed (km/h) and heading. Falls back to
        /virtual-train-api/api/vehicle and finally to a station-based
        lookup via the composition endpoint.

        ``anchor_iso`` (ISO-8601 like "2026-04-30T08:25:00+0200") is
        passed as ``dateTime`` to /v1/trein/{nr} when the bulk endpoint
        is empty. NS uses it to disambiguate ritnummers reused across
        the day so we get the actual physical train the user is on
        rather than another rotation that happens to share the number.
        """
        if not train_number:
            return None
        if not self.api_key:
            return None
        bucket = self.hass.data.setdefault(DOMAIN, {})
        warned_once = bool(bucket.get("_live_train_warned"))
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        # First try with `route` filter (ritnummer); if the result is empty,
        # we'll retry without the filter so we can match client-side. The
        # bbox + radius are kept reasonable so we get a manageable response.
        base_params = {
            "lat": "52.10",
            "lng": "5.30",
            "radius": "300",  # km — covers all NL plus near border
            "limit": "100",
            "features": "drukte",
        }
        params = dict(base_params)
        params["route"] = str(train_number)

        async def _try(url: str, q: dict[str, Any]) -> dict[str, Any] | None:
            try:
                async with async_timeout.timeout(15):
                    async with self._session.get(
                        url, headers=headers, params=q,
                    ) as resp:
                        if resp.status != 200:
                            body = ""
                            try:
                                body = (await resp.text())[:300]
                            except Exception:  # noqa: BLE001
                                pass
                            return resp.status, body, None
                        return resp.status, "", await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                return 0, str(err), None

        status, body, data = await _try(VIRTUAL_TRAIN_VEHICLE_URL, params)
        if data is None:
            status, body, data = await _try(VIRTUAL_TRAIN_VEHICLE_FALLBACK_URL, params)

        if data is None:
            if not warned_once:
                bucket["_live_train_warned"] = True
                _LOGGER.warning(
                    "Live vehicle fetch %s -> HTTP %s. Body: %s",
                    train_number, status, body,
                )
            return await self._async_station_based_position(train_number)

        if isinstance(data, list):
            vehicles = data
        elif isinstance(data, dict):
            payload = data.get("payload")
            if isinstance(payload, dict):
                # Real shape from /virtual-train-api/vehicle:
                # {"payload": {"treinen": [...]}}
                vehicles = (
                    payload.get("treinen")
                    or payload.get("trains")
                    or payload.get("vehicles")
                    or []
                )
            elif isinstance(payload, list):
                vehicles = payload
            else:
                vehicles = (
                    data.get("treinen")
                    or data.get("vehicles")
                    or data.get("trains")
                    or []
                )
        else:
            vehicles = []

        # Keep only dict-shaped entries — defensive in case the API
        # returns a list of strings or other primitives.
        vehicles = [v for v in vehicles if isinstance(v, dict)]

        if not vehicles:
            # Empty with route filter — retry WITHOUT filter and match
            # client-side. Some NS API tiers return all trains; the
            # `route` param is then a no-op.
            status2, body2, data2 = await _try(
                VIRTUAL_TRAIN_VEHICLE_URL, base_params,
            )
            if data2 is None:
                status2, body2, data2 = await _try(
                    VIRTUAL_TRAIN_VEHICLE_FALLBACK_URL, base_params,
                )
            if isinstance(data2, dict):
                payload2 = data2.get("payload")
                if isinstance(payload2, dict):
                    vehicles = (
                        payload2.get("treinen")
                        or payload2.get("trains")
                        or payload2.get("vehicles")
                        or []
                    )
                elif isinstance(payload2, list):
                    vehicles = payload2
            elif isinstance(data2, list):
                vehicles = data2
            vehicles = [v for v in vehicles if isinstance(v, dict)]

        if not vehicles:
            if not warned_once:
                bucket["_live_train_warned"] = True
                snippet = str(data)[:400]
                _LOGGER.warning(
                    "Live vehicle fetch %s: empty. Raw response: %s",
                    train_number, snippet,
                )
            return await self._async_station_based_position(train_number, anchor_iso)

        target = str(train_number)
        match = None
        for v in vehicles:
            ride_id = str(
                v.get("route") or v.get("ritId") or v.get("ritnummer")
                or v.get("journeyId") or v.get("trainNumber") or ""
            )
            if ride_id == target:
                match = v
                break
        if not match and len(vehicles) == 1:
            # API filtered server-side: trust it.
            match = vehicles[0]
        if not match:
            if not warned_once:
                bucket["_live_train_warned"] = True
                # Show what keys are in the first vehicle so we can adapt.
                sample = vehicles[0] if vehicles else {}
                _LOGGER.warning(
                    "Live vehicle fetch %s: route filter found no match. "
                    "Got %d vehicles; sample keys: %s; sample: %s",
                    train_number, len(vehicles),
                    list(sample.keys()),
                    str(sample)[:400],
                )
            return await self._async_station_based_position(train_number, anchor_iso)

        lat = match.get("lat") or match.get("latitude")
        lng = match.get("lng") or match.get("lon") or match.get("longitude")
        if lat is None or lng is None:
            return await self._async_station_based_position(train_number, anchor_iso)
        return {
            "lat": float(lat),
            "lng": float(lng),
            "speed": match.get("snelheid") or match.get("speed"),
            "heading": match.get("richting") or match.get("heading"),
            "ts": match.get("tijd") or match.get("time"),
            "type": match.get("type") or match.get("categorie"),
            "source": "vehicle",
        }

    async def _async_station_based_position(
        self, train_number: str, anchor_iso: str | None = None,
    ) -> dict | None:
        """Fallback: derive a position from the train's current station
        via /v1/trein/{nr} (composition endpoint) + cached /v2/stations.

        ``anchor_iso`` is forwarded as the ``dateTime`` query parameter
        so NS picks the specific physical train running at that instant
        rather than whatever rotation currently happens to use the
        ritnummer.
        """
        if not self.api_key:
            return None
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        url = f"{VIRTUAL_TRAIN_API_URL}/{train_number}"
        params: dict[str, str] = {}
        if anchor_iso:
            params["dateTime"] = anchor_iso
        try:
            async with async_timeout.timeout(15):
                async with self._session.get(
                    url, headers=headers, params=params or None,
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None
        payload = (data or {}).get("payload") or data or {}
        station_code = (payload.get("station") or "").upper()
        if not station_code:
            return None
        geo = await self.async_fetch_stations_geo()
        match = geo.get(station_code)
        if not match:
            return None
        return {
            "lat": match["lat"],
            "lng": match["lng"],
            "station_code": station_code,
            "station_name": match["name"],
            "spoor": payload.get("spoor"),
            "speed": None,
            "heading": None,
            "source": "station",
        }
