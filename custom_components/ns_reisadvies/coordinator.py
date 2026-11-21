"""DataUpdateCoordinator for the NS Reisadvies integration."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import (
    date as _dt_date,
    datetime,
    time as _dt_time,
    timedelta,
    timezone,
)
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from ._filter import (
    apply_train_type_filter,
    apply_window_filter,
    compute_target_datetime,
    parse_iso,
    train_types_in,
)
from ._dienstkaartje import (
    annotate_trips,
    clean_username,
    parse_follow_list,
    parse_list,
    parse_profile,
)
from ._disruptions import (
    affecting,
    disruption_language,
    parse_disruptions,
    station_keys_of,
)
from ._focus import (
    departure_facts,
    disruption_events,
    focus_trip,
    following_trip,
    journey_events,
    last_trip,
    live_facts,
    summary,
)
from ._live import parse_journey, run_window, vehicle_index
from .const import (
    API_URL,
    ARCGIS_BACKOFF_MINUTES,
    ARCGIS_FAILURES_BEFORE_BACKOFF,
    ARCGIS_TREINEN_URL,
    DIENSTKAARTJE_API_URL,
    DIENSTKAARTJE_BACKOFF_MINUTES,
    DIENSTKAARTJE_CACHE_SECONDS,
    DIENSTKAARTJE_MAX_FOLLOWED,
    DIENSTKAARTJE_SWEEP_CACHE_SECONDS,
    DIENSTKAARTJE_SWEEP_MAX_PAGES,
    DIENSTKAARTJE_SWEEP_MAX_PEOPLE,
    DISRUPTIONS_API_URL,
    DISRUPTIONS_CACHE_SECONDS,
    FOCUS_TICK_SECONDS,
    LAST_TRAIN_REFRESH_MINUTES,
    SERVICE_DAY_ROLLOVER_HOUR,
    LIVE_GRACE_MINUTES,
    LIVE_LEAD_MINUTES,
    FAV_RUN_LOOKAROUND_HOURS,
    JOURNEY_CACHE_SECONDS,
    VEHICLE_CACHE_SECONDS,
    FILTER_EXTRA_SEARCHES,
    FILTER_MIN_RESULTS,
    DEFAULT_FAV_TRACK_SECONDS,
    DOMAIN,
    FAV_TRACK_GRACE_MINUTES,
    FAV_TRACK_LEAD_MINUTES,
    FAV_TRACK_SECONDS_MAX,
    FAV_TRACK_SECONDS_MIN,
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

# NS keeps Dutch time; the service day rolls over on the Dutch clock.
_DUTCH_CLOCK = ZoneInfo("Europe/Amsterdam")


def _parse_time(value: str | None) -> _dt_time | None:
    """Parse a "HH:MM" string into a ``time`` object, or return None."""
    if not value:
        return None
    try:
        parts = str(value).split(":")
        return _dt_time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def _parse_date(value: str | None) -> _dt_date | None:
    """Parse a "YYYY-MM-DD" string into a ``date`` object, or return None."""
    if not value:
        return None
    try:
        return _dt_date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


# v2.16.14: characters that NS APIM rejects with HTTP 401 the moment they
# end up in the ``Ocp-Apim-Subscription-Key`` header. Copy-paste from the
# NS Apportal account page sometimes silently appends a zero-width space
# (`​`), a non-breaking space (` `), a BOM (`﻿`), or a
# stray newline. Python's ``str.strip()`` only handles the ASCII subset,
# so any of those characters survive and the auth header is malformed.
# We strip them explicitly here, in one place, used both by the probe in
# ``async_validate_api_key`` and by the storage→coordinator path in
# ``__init__.py``.
_API_KEY_INVISIBLE = (
    "​"  # zero-width space
    "‌"  # zero-width non-joiner
    "‍"  # zero-width joiner
    "﻿"  # BOM / zero-width no-break space
    " "  # non-breaking space
    " "  # line separator
    " "  # paragraph separator
)


def sanitize_api_key(value: Any) -> str:
    """Return the API key with whitespace + invisible characters stripped.

    Always returns a ``str`` — ``None`` and non-string values produce
    ``""``. Idempotent so it's safe to call on already-clean keys.
    """
    if not isinstance(value, str):
        return ""
    cleaned = value.strip().strip(_API_KEY_INVISIBLE).strip()
    # Strip any remaining ASCII control characters (CR, LF, NUL, TAB)
    # that survived the .strip() because they're embedded mid-string.
    return "".join(ch for ch in cleaned if ord(ch) >= 0x20 or ch in (" ",))


async def async_validate_api_key(hass: HomeAssistant, api_key: str) -> str | None:
    """Probe the NS API with the supplied key.

    Returns ``None`` on success, or a config-flow error code:

    * ``"invalid_auth"`` — key was rejected (HTTP 401/403).
    * ``"cannot_connect"`` — network failure or other 5xx.

    Used by the config flow to satisfy the Bronze quality-scale rule
    ``test-before-configure``: validate the credentials with the
    upstream service before creating the entry.
    """
    cleaned = sanitize_api_key(api_key)
    if not cleaned:
        return "invalid_auth"
    session = async_get_clientsession(hass)
    headers = {"Ocp-Apim-Subscription-Key": cleaned}
    # v2.16.15: probe via /v3/trips (Ns-App product) instead of
    # /v2/stations. NS Apportal sells separate subscription products
    # per endpoint family — "Ns-App" covers /reisinformatie-api/v3/*
    # but NOT /v2/stations (that's the standalone "Stationsdata"
    # product). A user who only subscribes to Ns-App (the typical
    # setup for trip planning) would see their valid key rejected by
    # the probe even though it works fine for the actual coordinator
    # polls. Probing the same endpoint the coordinator uses guarantees
    # the validation matches reality.
    params = {"fromStation": "ASD", "toStation": "UT"}
    try:
        async with async_timeout.timeout(15):
            async with session.get(API_URL, headers=headers, params=params) as resp:
                if resp.status in (401, 403):
                    # v2.16.16: read + log the NS APIM error body so we
                    # know whether the rejection is "subscription not
                    # found", "subscription suspended", "key revoked",
                    # "rate limited", etc. NS' diagnostic message lives
                    # in the response payload, not the headers.
                    try:
                        body = (await resp.text())[:500]
                    except Exception:  # noqa: BLE001
                        body = "<could not read body>"
                    _LOGGER.warning(
                        "NS API probe rejected key — HTTP %s; key length=%d; "
                        "url=%s; subscription header sent=%s; response body: %s",
                        resp.status,
                        len(cleaned),
                        API_URL,
                        bool(headers.get("Ocp-Apim-Subscription-Key")),
                        body,
                    )
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

class NSUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
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
        track_favourites: bool = False,
        favourite_track_seconds: int = DEFAULT_FAV_TRACK_SECONDS,
        disruptions: bool = True,
        dienstkaartje: bool = False,
        dienstkaartje_users: list[str] | str | None = None,
        live_sensors: bool = True,
        minutes_to_station: int = 0,
        filter_days: list[int] | None = None,
        filter_time: str | None = None,
        filter_window_minutes: int = 0,
        filter_date: str | None = None,
        filter_train_types: list[str] | None = None,
    ) -> None:
        # The hub config entry; used to read/write
        # ``entry.runtime_data.stations_geo`` (the per-HA-boot stations
        # geo cache). Optional for back-compat with older callers /
        # tests that constructed a coordinator without an entry.
        self._entry = entry
        # v2.16.14: defensive sanitisation against zero-width / BOM /
        # NBSP characters that survive copy-paste from the NS Apportal
        # account page and otherwise yield silent HTTP 401s.
        self.api_key = sanitize_api_key(api_key)
        self.from_station = from_station
        self.to_station = to_station
        self.fav_hours = fav_hours
        self.fetch_composition = fetch_composition

        # v2.18.0: favourite tracking. ``track_favourites`` gates every
        # part of this — with the option off nothing is polled, no
        # entities are created and the interval is never scheduled.
        self.track_favourites = bool(track_favourites)
        # v2.25.0: NS's disruptions, nationally and for this route.
        # Filled on every refresh so the sensors follow the same
        # cadence as the trips they belong to.
        self.watch_disruptions = bool(disruptions)
        self.disruptions: list[dict[str, Any]] = []
        self.route_disruptions: list[dict[str, Any]] = []
        # v2.27.0: Dienstkaartje. Off unless the user switches it on,
        # and then only for the people they name: nothing is fetched
        # about anyone else, and a profile is read exactly as its owner
        # publishes it.
        self.watch_dienstkaartje = bool(dienstkaartje)
        # Each entry is a username and, where the user wrote one after
        # a colon, their own label for what that person does.
        self.dienstkaartje_follow = parse_follow_list(dienstkaartje_users)[
            :DIENSTKAARTJE_MAX_FOLLOWED
        ]
        self.dienstkaartje_users = [
            entry["username"] for entry in self.dienstkaartje_follow
        ]
        self.dienstkaartje: list[dict[str, Any]] = []
        # v2.28.0: the one trip the automation sensors describe — a
        # pinned favourite, else the next departure — and what is known
        # about its train right now. ``focus`` comes from the planner,
        # ``focus_live`` from NS's vehicle feed and the train's own run.
        self.watch_live = bool(live_sensors)
        self.minutes_to_station = max(0, min(120, int(minutes_to_station or 0)))
        # The trip after the focus (what to take if you miss yours) and
        # the last trip of the service day.
        self.following: dict[str, Any] = {}
        self.last_train: dict[str, Any] = {}
        self._last_train_at: float | None = None
        self._last_train_day: str | None = None
        self._last_consumers = 0
        self.focus: dict[str, Any] = {}
        self.focus_source: str | None = None
        self.focus_live: dict[str, Any] = {}
        self._focus_consumers = 0
        self._live_consumers = 0
        self._focus_unsub: Any = None
        self._events_fired: set[str] = set()
        self._focus_primed = False
        self._route_disruption_ids: set[str] | None = None
        self._event_listeners: list[Any] = []
        self.favourite_track_seconds = max(
            FAV_TRACK_SECONDS_MIN,
            min(FAV_TRACK_SECONDS_MAX, int(favourite_track_seconds or DEFAULT_FAV_TRACK_SECONDS)),
        )
        # ctx_recon -> {"active", "leg", "position", "updated_at", ...}
        self.favourite_positions: dict[str, dict[str, Any]] = {}
        self._fav_listeners: list[Any] = []
        self._fav_unsub: Any = None

        # Per-route filter (v2.14.0). Stored as parsed Python types so
        # _async_update_data can pass them straight to compute_target_datetime
        # without re-parsing on every refresh.
        self.filter_days: list[int] = list(filter_days or [])
        self.filter_time: _dt_time | None = _parse_time(filter_time)
        self.filter_window_minutes: int = max(0, min(360, int(filter_window_minutes or 0)))
        self.filter_date: _dt_date | None = _parse_date(filter_date)
        # v2.19.0: NS category codes this route accepts, upper case and
        # de-duplicated with the user's order kept. Empty = every type.
        self.filter_train_types: list[str] = list(
            dict.fromkeys(
                str(t).strip().upper()
                for t in (filter_train_types or [])
                if str(t).strip()
            )
        )
        # Every code seen in the last fetch, before filtering, so the
        # sensor can report what this route actually runs.
        self.available_train_types: list[str] = []

        # v2.16.0: how many calendar days the trip-search anchor
        # advances. 0 = today; 1 = tomorrow; 2+ = day after that.
        # Updated each refresh in _async_update_data and surfaced via
        # the sensor's ``target_day_offset`` attribute so the card can
        # render a "Tomorrow" / "+N days" badge.
        # ``_target_date`` is the matching ISO date string (YYYY-MM-DD)
        # so the card can show the literal day for date- or weekday-
        # filtered routes (e.g. "Reizen voor maandag 11 mei").
        self._target_day_offset: int = 0
        self._target_date: str | None = None

        # Central in-memory store for pinned favourites.
        # Mapping: ctx_recon -> epoch seconds at which it was pinned.
        self.tracked_trips: dict[str, float] = {}

        # Train composition cache: train_number -> dict (per refresh).
        # Cleared at the start of each _async_update_data run so that
        # the same train fetched twice in one refresh hits the cache.
        self._composition_cache: dict[str, dict[str, Any] | None] = {}
        # Whether the first composition error of the current refresh has
        # already been logged at warning level. Reset per refresh.
        self._composition_warned: bool = False

        # Edge-detection for the Silver "log-when-unavailable" quality-
        # scale rule. ``None`` means we haven't observed an outcome yet;
        # otherwise it tracks the last refresh's success/failure and
        # we only emit a log line on transitions.
        self._was_available: bool | None = None

        # v2.16.18: machine-readable categorisation of the most recent
        # refresh failure, surfaced as a sensor attribute so the user
        # (and the Lovelace card) can show a useful indicator without
        # having to grep the HA logs.
        #
        #   "none"             — last refresh succeeded
        #   "auth"             — HTTP 401/403 (key revoked, wrong product)
        #   "quota_exceeded"   — HTTP 429 (rate-limited by NS APIM)
        #   "api_unavailable"  — HTTP 5xx or other non-2xx from NS
        #   "network"          — aiohttp ClientError / TimeoutError
        self._last_error_category: str = "none"

        # v2.16.18: timestamp of the FIRST refresh failure of the current
        # outage streak — None when healthy. Exposed via the sensor's
        # ``outage_started_at`` attribute so a card can render "down
        # for X minutes" badges.
        self._outage_started_at: float | None = None

        # Persistent storage so favourites survive a Home Assistant restart.
        self._store: Store[dict[str, Any]] = Store(
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

    # ---- favourite tracking (v2.18.0) ----
    #
    # A pinned favourite is a specific trip, which may be made up of
    # several legs on different trains. The tracker follows the leg the
    # traveller is on right now, so at a transfer the same entity moves
    # to the next train instead of sticking with the one just left.

    def favourite_trip(self, ctx_recon: str) -> dict[str, Any] | None:
        """Return the pinned trip for ``ctx_recon`` from the last refresh."""
        for trip in self.data or []:
            if trip.get("ctxRecon") == ctx_recon:
                return trip
        return None

    @staticmethod
    def leg_window(leg: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
        """Actual (or planned) departure and arrival of a leg."""
        origin = leg.get("origin") or {}
        dest = leg.get("destination") or {}
        dep = parse_iso(origin.get("actualDateTime") or origin.get("plannedDateTime"))
        arr = parse_iso(dest.get("actualDateTime") or dest.get("plannedDateTime"))
        return dep, arr

    def favourite_state(
        self, ctx_recon: str, now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Describe what a favourite's tracker should show right now.

        Returns None when the trip is not in the current data set (the
        favourite was pinned for a day that has rolled over, say), so the
        caller can leave the entity unavailable rather than invent a
        position. Otherwise:

        * ``active`` — the traveller is on a train at this moment, which
          is the only case where a position is fetched at all;
        * ``leg`` — the active leg, or the next one when the trip has not
          started, or the last one when it is over;
        * ``phase`` — ``upcoming`` / ``en_route`` / ``arrived``.
        """
        trip = self.favourite_trip(ctx_recon)
        if trip is None:
            return None
        moment = now or datetime.now(timezone.utc)
        lead = timedelta(minutes=FAV_TRACK_LEAD_MINUTES)
        grace = timedelta(minutes=FAV_TRACK_GRACE_MINUTES)

        legs = [leg for leg in (trip.get("legs") or []) if isinstance(leg, dict)]
        upcoming: dict[str, Any] | None = None
        for leg in legs:
            dep, arr = self.leg_window(leg)
            if dep is None or arr is None:
                continue
            if dep - lead <= moment <= arr + grace:
                return {
                    "trip": trip, "leg": leg, "active": True, "phase": "en_route",
                    "departure": dep, "arrival": arr,
                }
            if upcoming is None and moment < dep - lead:
                upcoming = leg

        if upcoming is not None:
            dep, arr = self.leg_window(upcoming)
            return {
                "trip": trip, "leg": upcoming, "active": False, "phase": "upcoming",
                "departure": dep, "arrival": arr,
            }
        last = legs[-1] if legs else None
        dep, arr = self.leg_window(last) if last else (None, None)
        return {
            "trip": trip, "leg": last, "active": False, "phase": "arrived",
            "departure": dep, "arrival": arr,
        }

    def _worth_following(
        self, state: dict[str, Any], moment: datetime,
    ) -> bool:
        """Whether a pinned trip is close enough in time to look at.

        A favourite pinned for tomorrow morning must not keep the feed
        busy all night, so nothing is fetched outside a few hours around
        the trip itself. Inside that span the train's own run decides.
        """
        reach = timedelta(hours=FAV_RUN_LOOKAROUND_HOURS)
        for key in ("departure", "arrival"):
            when = state.get(key)
            if isinstance(when, datetime) and abs(when - moment) <= reach:
                return True
        return False

    async def _async_train_is_running(
        self, train_number: str, moment: datetime,
    ) -> bool | None:
        """Whether this train is somewhere on its own run right now.

        Returns None when NS will not say — an older key gets a 404 on
        the journey endpoint — so the caller can fall back to the
        traveller's own travel window.
        """
        start, end = await self.async_journey_run(train_number)
        if start is None or end is None:
            return None
        grace = timedelta(minutes=FAV_TRACK_GRACE_MINUTES)
        return start - grace <= moment <= end + grace

    async def async_refresh_favourite_positions(
        self, now: datetime | None = None,
    ) -> None:
        """Fetch a GPS fix for every pinned favourite whose train runs.

        A train is followed for as long as its own run lasts, not just
        while the traveller is on board: it is already worth seeing
        while it approaches the departure station from wherever it
        started, and it stays worth seeing as it carries on past the
        arrival station. Outside a few hours around the trip nothing is
        fetched at all, and the national vehicle feed behind this is one
        shared request however many favourites are pinned.
        """
        if not self.track_favourites:
            if self.favourite_positions:
                self.favourite_positions.clear()
                self._notify_favourite_listeners()
            return

        moment = now or datetime.now(timezone.utc)
        pinned = list(self.tracked_trips)
        for ctx in list(self.favourite_positions):
            if ctx not in pinned:
                self.favourite_positions.pop(ctx, None)

        for ctx in pinned:
            state = self.favourite_state(ctx, moment)
            if state is None:
                self.favourite_positions.pop(ctx, None)
                continue
            leg = state.get("leg") or {}
            product = leg.get("product") or {}
            train_number = str(product.get("number") or "")
            position: dict[str, Any] | None = None
            running = False
            if train_number and self._worth_following(state, moment):
                on_its_run = await self._async_train_is_running(
                    train_number, moment,
                )
                # Without a journey to go on, fall back to the
                # traveller's own window, which is what v2.20.0 and
                # earlier used on its own.
                running = bool(state["active"]) if on_its_run is None else on_its_run
                if running:
                    dep = state.get("departure")
                    position = await self.async_fetch_train_position(
                        train_number,
                        anchor_iso=dep.isoformat() if isinstance(dep, datetime) else None,
                    )
            previous = self.favourite_positions.get(ctx) or {}
            self.favourite_positions[ctx] = {
                "ctx_recon": ctx,
                "active": state["active"],
                "phase": state["phase"],
                "train_running": running,
                "train_number": train_number,
                "product": product,
                "origin": (leg.get("origin") or {}).get("name"),
                "destination": (leg.get("destination") or {}).get("name"),
                "direction": leg.get("direction"),
                "departure": state["departure"].isoformat() if state["departure"] else None,
                "arrival": state["arrival"].isoformat() if state["arrival"] else None,
                "trip_origin": self._trip_endpoint(state["trip"], first=True),
                "trip_destination": self._trip_endpoint(state["trip"], first=False),
                # Keep the last known fix while the train is between
                # reports; drop it once the run is over so a train that
                # finished for the day does not linger on the map.
                "position": position or (previous.get("position") if running else None),
                "position_fresh": position is not None,
                "updated_at": moment.isoformat(),
            }
        self._notify_favourite_listeners()

    def current_favourite(self) -> dict[str, Any] | None:
        """The favourite this route's tracker should report.

        A trip already under way wins over one that has not left yet,
        and within the same phase the earliest departure does. Returns
        None when nothing is pinned, which leaves the tracker without
        coordinates rather than removing it.

        A trip the traveller has finished still counts while its train
        is on its way to the next station — that is the whole point of
        following the train rather than the journey — but it gives way
        to any trip still to come.
        """
        if not self.favourite_positions:
            return None
        rank = {"en_route": 0, "upcoming": 1, "arrived": 2}

        def sort_key(record: dict[str, Any]) -> tuple[int, float]:
            phase = str(record.get("phase") or "")
            departure = parse_iso(record.get("departure"))
            stamp = departure.timestamp() if departure else float("inf")
            return (rank.get(phase, 3), stamp)

        best = min(self.favourite_positions.values(), key=sort_key)
        if sort_key(best)[0] < 2:
            return best
        return best if best.get("train_running") else None

    @staticmethod
    def _trip_endpoint(trip: dict[str, Any], *, first: bool) -> str | None:
        """Name of the trip's first origin or final destination."""
        legs = [leg for leg in (trip.get("legs") or []) if isinstance(leg, dict)]
        if not legs:
            return None
        leg = legs[0] if first else legs[-1]
        side = leg.get("origin") if first else leg.get("destination")
        name = (side or {}).get("name")
        return str(name) if name else None

    @callback
    def async_add_favourite_listener(self, update: Any) -> Any:
        """Register a callback fired after every favourite-position refresh."""
        self._fav_listeners.append(update)

        @callback
        def _remove() -> None:
            if update in self._fav_listeners:
                self._fav_listeners.remove(update)

        return _remove

    @callback
    def _notify_favourite_listeners(self) -> None:
        for update in list(self._fav_listeners):
            update()

    @callback
    def async_start_favourite_tracking(self) -> None:
        """Schedule the background position refresh (idempotent)."""
        if self._fav_unsub is not None or not self.track_favourites:
            return
        self._fav_unsub = async_track_time_interval(
            self.hass,
            self._async_favourite_tick,
            timedelta(seconds=self.favourite_track_seconds),
        )

    @callback
    def async_stop_favourite_tracking(self) -> None:
        """Cancel the background refresh and forget the last fixes."""
        if self._fav_unsub is not None:
            self._fav_unsub()
            self._fav_unsub = None
        if self.favourite_positions:
            self.favourite_positions.clear()
            self._notify_favourite_listeners()

    async def _async_favourite_tick(self, now: datetime) -> None:
        """Interval callback — kept thin so it is trivially testable."""
        await self.async_refresh_favourite_positions(now)

    # ---- the focus trip: automation sensors and events (v2.28.0) ----

    @callback
    def async_add_focus_consumer(
        self, *, live: bool = False, last_train: bool = False,
    ) -> Any:
        """Register an entity that reads the focus trip.

        The minute tick only runs while something is listening, and NS
        is only asked for a position while something that shows one is
        enabled: a live sensor switched off in the entity settings is
        never added to Home Assistant, never registers here, and so
        never costs a request.
        """
        self._focus_consumers += 1
        if live:
            self._live_consumers += 1
        if last_train:
            self._last_consumers += 1
        self._async_schedule_focus_tick()

        @callback
        def _remove() -> None:
            self._focus_consumers = max(0, self._focus_consumers - 1)
            if live:
                self._live_consumers = max(0, self._live_consumers - 1)
            if last_train:
                self._last_consumers = max(0, self._last_consumers - 1)
            if self._focus_consumers == 0:
                self.async_stop_focus_tick()

        return _remove

    @callback
    def _async_schedule_focus_tick(self) -> None:
        if self._focus_unsub is not None or self._focus_consumers == 0:
            return
        self._focus_unsub = async_track_time_interval(
            self.hass, self._async_focus_tick, timedelta(seconds=FOCUS_TICK_SECONDS),
        )

    @callback
    def async_stop_focus_tick(self) -> None:
        """Cancel the minute tick (on unload, or when nobody listens)."""
        if self._focus_unsub is not None:
            self._focus_unsub()
            self._focus_unsub = None

    @callback
    def async_add_event_listener(self, update: Any) -> Any:
        """Register a callback for journey and disruption events."""
        self._event_listeners.append(update)

        @callback
        def _remove() -> None:
            if update in self._event_listeners:
                self._event_listeners.remove(update)

        return _remove

    @callback
    def _fire(self, kind: str, data: dict[str, Any]) -> None:
        """Tell automations: on the bus, and to the route's event entity."""
        payload = {
            **data,
            "type": kind,
            "route": f"{self.from_station} → {self.to_station}",
            "from_station": self.from_station,
            "to_station": self.to_station,
        }
        self.hass.bus.async_fire(f"{DOMAIN}_event", payload)
        for listener in list(self._event_listeners):
            listener(kind, payload)

    def _refresh_focus(
        self, trips: list[dict[str, Any]] | None, now: datetime,
        live: dict[str, Any] | None = None,
    ) -> None:
        """Choose the focus trip, describe it, and fire what changed.

        When the focus moves on — the next train left, so the one after
        it is next now — the trip it moved away from is looked at once
        more with fresh data, so its departure is still reported.
        """
        previous = self.focus
        previous_live = self.focus_live
        trip, source = focus_trip(trips, list(self.tracked_trips or {}), now)
        facts = departure_facts(trip, now, self.minutes_to_station)
        self.following = summary(following_trip(trips, facts), now)
        current_live = live if live is not None else (
            previous_live if facts.get("identity") == previous.get("identity") else {}
        )

        if previous.get("identity") and previous.get("identity") != facts.get("identity"):
            for old in trips or []:
                old_facts = departure_facts(old, now)
                if old_facts.get("identity") == previous.get("identity"):
                    for kind, data in journey_events(
                        previous, old_facts, previous_live, None,
                        self._events_fired, now,
                    ):
                        self._fire(kind, data)
                    break

        happened = journey_events(
            previous, facts, previous_live, current_live, self._events_fired, now,
        )
        # The first look after Home Assistant starts is not news: a
        # train that already left while it was down is remembered as
        # having left, but nobody is told it just did.
        if self._focus_primed:
            for kind, data in happened:
                self._fire(kind, data)
        self._focus_primed = True

        self.focus = facts
        self.focus_source = source
        self.focus_live = current_live or {}
        # Forget events for trips that are long gone; one day is plenty.
        if len(self._events_fired) > 500:
            self._events_fired.clear()

    def _live_window_open(self, now: datetime) -> bool:
        """Whether the focus train is close enough to be worth a request."""
        departure = self.focus.get("departure")
        arrival = self.focus.get("arrival")
        if not isinstance(departure, datetime) or not isinstance(arrival, datetime):
            return False
        return (
            departure - timedelta(minutes=LIVE_LEAD_MINUTES)
            <= now
            <= arrival + timedelta(minutes=LIVE_GRACE_MINUTES)
        )

    async def async_refresh_focus_live(self, now: datetime | None = None) -> None:
        """One minute tick: recount the clock, and place the train.

        The planner's facts are recomputed every time — that is what
        makes "minutes to departure" count down and the clock-based
        events fire on time — but NS is only asked where the train is
        when a live entity is enabled, the option is on, and the train
        is within half an hour of the traveller's departure or still on
        their stretch.
        """
        moment = now or datetime.now(timezone.utc)
        trips = self.data if isinstance(self.data, list) else []
        self._refresh_focus(trips, moment)

        live: dict[str, Any] = {}
        number = self.focus.get("train_number")
        if (
            self.watch_live and self._live_consumers > 0 and number
            and not self.focus.get("cancelled") and self._live_window_open(moment)
        ):
            departure = self.focus.get("departure")
            position = await self.async_fetch_train_position(
                str(number),
                anchor_iso=departure.isoformat() if isinstance(departure, datetime) else None,
            )
            stops = await self.async_journey_stops(str(number)) if position else []
            live = live_facts(stops, position, self.focus, moment)
        self._refresh_focus(trips, moment, live)
        self.async_update_listeners()

    async def _async_focus_tick(self, now: datetime) -> None:
        """Interval callback — kept thin so it is trivially testable."""
        await self.async_refresh_focus_live(now)
        await self.async_refresh_last_train(now)

    @staticmethod
    def service_day_end(now: datetime) -> datetime:
        """When NS's current service day ends: four the next morning.

        A train at half past midnight still belongs to the evening
        before, so "today's last train" is the last one before the
        rollover, on the Dutch clock whatever Home Assistant runs in.
        """
        local = now.astimezone(_DUTCH_CLOCK)
        day = local.date()
        if local.hour < SERVICE_DAY_ROLLOVER_HOUR:
            day -= timedelta(days=1)
        return datetime(
            day.year, day.month, day.day, SERVICE_DAY_ROLLOVER_HOUR,
            tzinfo=_DUTCH_CLOCK,
        ) + timedelta(days=1)

    async def async_refresh_last_train(self, now: datetime | None = None) -> None:
        """Look up the last trip of the service day, at most hourly.

        One planner request, "arrive by" the end of the service day, so
        NS answers with the last trips that still get there — however
        early a quiet line stops. The route's own train-type filter
        applies, so a route kept to intercities gets the last
        intercity. Only asked while the sensor that shows it is enabled.
        """
        if self._last_consumers == 0:
            return
        moment = now or datetime.now(timezone.utc)
        ends = self.service_day_end(moment)
        day = ends.date().isoformat()
        fresh = (
            self._last_train_at is not None
            and time.monotonic() - self._last_train_at < LAST_TRAIN_REFRESH_MINUTES * 60
            and self._last_train_day == day
        )
        if fresh:
            return
        trips, problem = await self.async_search_trips(
            self.from_station, self.to_station,
            when=(ends - timedelta(minutes=1)).isoformat(),
            arrival=True,
            train_types=list(self.filter_train_types or []) or None,
            extras=False,
        )
        self._last_train_at = time.monotonic()
        self._last_train_day = day
        if problem is None or problem == "no_match":
            self.last_train = summary(last_trip(trips, ends), moment)
        self.async_update_listeners()

    def _refresh_route_disruptions(self) -> None:
        """Fire for disruptions that started or ended on this route."""
        for kind, data in disruption_events(
            self._route_disruption_ids, self.route_disruptions,
        ):
            self._fire(kind, data)
        self._route_disruption_ids = {
            str(item.get("id")) for item in self.route_disruptions if item.get("id")
        }

    # ---- composition (train carriages) ----

    async def _fetch_journey_composition(self, train_number: str, headers: dict[str, Any]) -> dict[str, Any] | None:
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
        planned_stock = origin_stop.get("plannedStock") or {}
        train_parts = stock.get("trainParts") or []
        # v2.28.0: the stock NS planned and the stock it runs, at every
        # stop. A train is shortened or lengthened along its run, so
        # what matters to a traveller is the stop where they board;
        # this map lets each leg read its own, and stays off the
        # attributes (it is dropped when the leg is annotated).
        by_uic: dict[str, dict[str, Any]] = {}
        for stop in stops:
            actual = stop.get("actualStock") or {}
            planned = stop.get("plannedStock") or {}
            uic = str((stop.get("stop") or {}).get("uicCode") or "")
            if uic and (actual or planned):
                by_uic[uic] = {
                    "numberOfParts": actual.get("numberOfParts") or planned.get("numberOfParts"),
                    "numberOfSeats": actual.get("numberOfSeats") or planned.get("numberOfSeats"),
                    "plannedNumberOfParts": planned.get("numberOfParts"),
                    "plannedNumberOfSeats": planned.get("numberOfSeats"),
                    "significantChange": bool(actual.get("hasSignificantChange")),
                }
        slim = {
            "trainType": stock.get("trainType"),
            "numberOfParts": stock.get("numberOfParts") or len(train_parts) or None,
            "numberOfSeats": stock.get("numberOfSeats"),
            "numberOfFirstClassSeats": stock.get("numberOfFirstClassSeats"),
            "plannedNumberOfParts": planned_stock.get("numberOfParts"),
            "plannedNumberOfSeats": planned_stock.get("numberOfSeats"),
            "significantChange": bool(stock.get("hasSignificantChange")),
            "shorter": bool(stock.get("hasSignificantChange")) or False,
            "_by_uic": by_uic,
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

    async def _annotate_compositions(
        self,
        all_trips: list[dict[str, Any]],
        headers: dict[str, Any],
        *,
        reset: bool = True,
    ) -> None:
        """Add a `composition` field to every leg with a known train number.

        ``reset`` clears the per-refresh cache first, which is what a
        route refresh wants. A one-off search rides along on whatever
        the last refresh already fetched instead, so looking a journey
        up does not cost a round trip per train that is already known.
        """
        if not self.fetch_composition:
            return
        if reset:
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
                    # The run's own figures, then the boarding stop's,
                    # where NS gives them: that is the train the
                    # traveller actually gets on.
                    own = {k: v for k, v in comp.items() if k != "_by_uic"}
                    uic = str((leg.get("origin") or {}).get("uicCode") or "")
                    at_stop = (comp.get("_by_uic") or {}).get(uic)
                    if at_stop:
                        own.update({k: v for k, v in at_stop.items() if v is not None})
                    leg["composition"] = own

    # ---- data fetch ----

    @staticmethod
    def _last_departure_iso(trips: list[dict[str, Any]]) -> str | None:
        """Planned departure of the latest trip in the list, if any."""
        stamps = [
            str(
                ((trip.get("legs") or [{}])[0].get("origin") or {})
                .get("plannedDateTime")
                or ""
            )
            for trip in trips
        ]
        stamps = [s for s in stamps if s]
        return max(stamps) if stamps else None

    async def _async_search_more(
        self,
        headers: dict[str, str],
        params: dict[str, str],
        trips: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Ask NS for later trips until enough survive the filter.

        NS answers a search with a handful of trips, so a route that
        only accepts intercities can be left with one row out of six.
        Each extra search starts a minute after the latest trip already
        in hand, which is the same forward paging the user would get by
        scrolling in the NS app.

        Best-effort by design: any error or timeout simply stops the
        loop and leaves the trips already fetched untouched, because a
        thin list is a far better outcome than a failed refresh.
        """
        if not self.filter_train_types:
            return trips

        merged = list(trips)
        for _ in range(FILTER_EXTRA_SEARCHES):
            if len(apply_train_type_filter(merged, self.filter_train_types)) >= (
                FILTER_MIN_RESULTS
            ):
                break
            last_iso = self._last_departure_iso(merged)
            anchor = parse_iso(last_iso)
            if anchor is None:
                break
            next_params = dict(params)
            next_params["dateTime"] = (anchor + timedelta(minutes=1)).isoformat()
            try:
                async with async_timeout.timeout(10):
                    async with self._session.get(
                        API_URL, headers=headers, params=next_params,
                    ) as response:
                        if response.status != 200:
                            _LOGGER.debug(
                                "Train-type filter: follow-up search -> HTTP %s",
                                response.status,
                            )
                            break
                        payload = await response.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.debug("Train-type filter: follow-up search failed: %s", err)
                break

            known = {t.get("ctxRecon") for t in merged if t.get("ctxRecon")}
            fresh = [
                trip
                for trip in (payload.get("trips") or [])
                if trip.get("ctxRecon") not in known
            ]
            if not fresh:
                break
            merged.extend(fresh)
        return merged

    def _note_unavailable(self, reason: str) -> None:
        """Log once when we transition into the unavailable state.

        Silver quality-scale rule ``log-when-unavailable``: log on the
        edge, not on every refresh, so the journal isn't spammed during
        a long upstream outage.

        Also stamps ``_outage_started_at`` on the first failure of a
        streak so the prolonged-outage Repair check (Gold rule
        ``repair-issues``) knows how long we've been down.
        """
        if self._outage_started_at is None:
            self._outage_started_at = time.time()
        if self._was_available is False:
            return
        _LOGGER.warning(
            "NS Reisadvies (%s -> %s) is unavailable: %s",
            self.from_station, self.to_station, reason,
        )
        self._was_available = False

    def _note_available(self) -> None:
        """Log once when we recover from a previous outage.

        Also resets ``_outage_started_at`` and ``_last_error_category``
        so the sensor attribute reflects a healthy poll.
        """
        # Reset outage tracking unconditionally — every successful run
        # ends whatever streak was in flight.
        self._outage_started_at = None
        self._last_error_category = "none"
        if self._was_available is None:
            self._was_available = True
            return
        if self._was_available is False:
            _LOGGER.info(
                "NS Reisadvies (%s -> %s) is back online",
                self.from_station, self.to_station,
            )
        self._was_available = True

    # v2.16.18: ``_REPAIR_OUTAGE_THRESHOLD_SECONDS`` + the Repair-issue
    # lifecycle were removed in v2.16.22 because the
    # ``homeassistant.helpers.issue_registry`` imports they relied on
    # tripped pytest-homeassistant-custom-component's AsyncMock
    # auto-wrapping and broke CI in ways that turned out hard to
    # isolate. The ``_last_error_category`` + ``outage_started_at``
    # sensor attributes (the main user-value) are kept, so a card or
    # automation can still surface "down for X minutes — category Y"
    # without us needing the in-app Repairs widget.

    def _maybe_raise_outage_repair(self) -> None:
        """No-op placeholder.

        Kept as a hook in case we wire it back up to ``issue_registry``
        once the test-infra interaction has been figured out. Today it
        does nothing — the per-route ``last_error_category`` +
        ``outage_started_at`` sensor attributes already cover the
        observable side.
        """
        return

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch trips and pinned favourites from the NS API."""
        # Prune expired favourites first so we do not refetch them.
        self._expire_old_trips()

        if not self.api_key:
            self._last_error_category = "auth"
            self._note_unavailable("no API key configured")
            self._maybe_raise_outage_repair()
            raise UpdateFailed("No NS API key configured")

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        # If the route declares a per-route filter (days / time / date),
        # compute the next valid moment and use it as the NS trip-search
        # anchor. Falls back to "now" when the filter would be entirely
        # in the past for a specific-date pin or when nothing is set.
        now_dt = datetime.now()
        target_dt = compute_target_datetime(
            now_dt,
            days=self.filter_days,
            target_time=self.filter_time,
            window_minutes=self.filter_window_minutes,
            specific_date=self.filter_date,
        ) or now_dt
        # v2.16.1: provisional offset/date — refined below using the
        # first visible trip so unfiltered routes also surface a
        # "trips for tomorrow" badge when the next train physically
        # leaves after midnight.
        self._target_day_offset = (target_dt.date() - now_dt.date()).days
        self._target_date = target_dt.date().isoformat()
        # v2.19.2: once a window is open the anchor itself may already
        # lie in the past (17:30 ±90 min, checked at 18:20). Searching
        # from the anchor would return only trains that have left, and
        # the stale-trip pass below would then empty the list although
        # trains still run inside the window. Search from "now" in that
        # case; the window filter still works from ``target_dt``.
        search_dt = max(target_dt, now_dt)
        params = {
            "fromStation": self.from_station,
            "toStation": self.to_station,
            "dateTime": search_dt.isoformat(),
        }

        try:
            # A filtered route may run up to two follow-up searches
            # inside this block, so it gets a correspondingly larger
            # budget. Unfiltered routes keep the old 20 seconds.
            async with async_timeout.timeout(
                40 if self.filter_train_types else 20
            ):
                # 1) Standard trip query for the configured route.
                async with self._session.get(API_URL, headers=headers, params=params) as response:
                    if response.status in (401, 403):
                        # v2.16.17: log the NS APIM body so we know the
                        # rejection reason (subscription not found,
                        # suspended, wrong product, rate-limited, etc).
                        try:
                            body = (await response.text())[:500]
                        except Exception:  # noqa: BLE001
                            body = "<could not read body>"
                        _LOGGER.warning(
                            "NS coordinator rejected — HTTP %s; key length=%d; "
                            "url=%s; from=%s to=%s; body: %s",
                            response.status,
                            len(self.api_key or ""),
                            API_URL,
                            self.from_station,
                            self.to_station,
                            body,
                        )
                        # Silver rule ``reauthentication-flow``: bubble
                        # auth failures up so HA opens the reauth form.
                        self._last_error_category = "auth"
                        self._note_unavailable(
                            f"NS API rejected the key (HTTP {response.status})"
                        )
                        self._maybe_raise_outage_repair()
                        raise ConfigEntryAuthFailed(
                            f"NS API rejected the API key (HTTP {response.status})"
                        )
                    if response.status == 429:
                        self._last_error_category = "quota_exceeded"
                        self._note_unavailable(
                            "NS API returned HTTP 429 (rate-limited)"
                        )
                        self._maybe_raise_outage_repair()
                        raise UpdateFailed(
                            "NS travel advice API returned HTTP 429 "
                            "(quota exceeded — slow polling down or wait)"
                        )
                    if response.status != 200:
                        self._last_error_category = "api_unavailable"
                        self._note_unavailable(
                            f"NS API returned HTTP {response.status}"
                        )
                        self._maybe_raise_outage_repair()
                        raise UpdateFailed(
                            f"NS travel advice API returned status {response.status}"
                        )
                    data = await response.json()
                    normal_trips = data.get("trips", []) or []

                # 1b) v2.19.0: top the list up when a train-type filter
                # would otherwise leave only a row or two.
                normal_trips = await self._async_search_more(
                    headers, params, normal_trips,
                )

                # 2) Pinned favourites — fetched in parallel.
                # Trips that the API no longer recognises (400/404) are pruned.
                tracked_trips_data: list[dict[str, Any]] = []
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
                    tracked_ctx = tracked_trip.get("ctxRecon")
                    if tracked_ctx and tracked_ctx not in normal_ctx_recons:
                        all_trips.append(tracked_trip)

                # v2.16.24: NS' /v3/trips happily keeps returning a
                # trip for ~10–15 minutes after it has already departed,
                # which cluttered the card with trains the user could
                # never catch. Drop any trip whose actual (or planned)
                # departure is more than one minute in the past — UNLESS
                # the trip is pinned as a favourite. Pinned trips remain
                # visible until the dedicated favourite-retention
                # timer (``_expire_old_trips``) removes them, matching
                # the documented "Favourite retention (hours)" option.
                now_utc = datetime.now(timezone.utc)
                _stale_after_dep = timedelta(minutes=1)

                def _has_departed(trip: dict[str, Any]) -> bool:
                    legs = trip.get("legs") or []
                    if not legs:
                        return False
                    origin = (legs[0] or {}).get("origin") or {}
                    # Prefer the actual (possibly delayed) departure;
                    # fall back to the planned one. NS' timestamps are
                    # timezone-aware ISO strings ("...+02:00").
                    iso = origin.get("actualDateTime") or origin.get(
                        "plannedDateTime"
                    )
                    if not iso:
                        return False
                    try:
                        dep_dt = datetime.fromisoformat(
                            str(iso).replace("Z", "+00:00")
                        )
                    except (TypeError, ValueError):
                        return False
                    # v2.16.26: production always sees aware datetimes
                    # (NS sends "+02:00" stamps; ``datetime.now(utc)``
                    # is aware). Tests patch ``datetime.now`` with a
                    # naive value, which would crash the comparison
                    # below. Skip the stale-trip check entirely if
                    # either side is naive — better than risking a
                    # false-positive filter under an unknown timezone.
                    if dep_dt.tzinfo is None or now_utc.tzinfo is None:
                        return False
                    return dep_dt + _stale_after_dep < now_utc

                pinned_ctx = set(self.tracked_trips or {})
                all_trips = [
                    t for t in all_trips
                    if t.get("ctxRecon") in pinned_ctx or not _has_departed(t)
                ]

                all_trips.sort(
                    key=lambda x: (
                        x.get("legs") or [{}]
                    )[0].get("origin", {}).get("plannedDateTime", "")
                )

                # v2.19.0: train-type filter. Runs before the window
                # filter so a "time set, window 0" route picks the
                # closest *allowed* train instead of filtering the one
                # train the window already settled on. Pinned
                # favourites survive whatever their type, exactly as
                # they survive the stale-trip pass above.
                self.available_train_types = train_types_in(all_trips)
                if self.filter_train_types:
                    allowed = apply_train_type_filter(
                        all_trips, self.filter_train_types,
                    )
                    allowed_ctx = {
                        t.get("ctxRecon") for t in allowed if t.get("ctxRecon")
                    }
                    all_trips = [
                        t for t in all_trips
                        if t.get("ctxRecon") in allowed_ctx
                        or t.get("ctxRecon") in pinned_ctx
                    ]

                # Per-route filter: keep only trips matching the
                # requested window. Skipped entirely when the route
                # declares no filter (preserves the v2.13.x behaviour
                # of "show whatever NS gives us around now").
                if (
                    self.filter_days
                    or self.filter_time is not None
                    or self.filter_date is not None
                    or self.filter_window_minutes > 0
                ):
                    # v2.16.0: when a *Time of day* filter is set with
                    # window=0 the user is asking for one specific
                    # train — surface the single closest match (with
                    # tie-break: ≤ anchor wins, then shorter duration).
                    # Days-only / specific-date / window>0 routes keep
                    # the previous "show every trip in window" shape.
                    pick_single = (
                        self.filter_time is not None
                        and self.filter_window_minutes == 0
                    )
                    all_trips = apply_window_filter(
                        all_trips,
                        target_dt,
                        self.filter_window_minutes,
                        pick_single=pick_single,
                    )

                # v2.16.1: refine the day-offset to the date of the
                # first trip we are actually going to render. This
                # makes the "Reizen voor morgen" badge appear on
                # routes without any filter when NS hands us trips
                # that physically depart after midnight (typical
                # late-evening case: now=23:55, next train 00:30).
                first_iso: str | None = None
                for trip in all_trips:
                    legs = trip.get("legs") or []
                    if not legs:
                        continue
                    iso = (legs[0] or {}).get("origin", {}).get(
                        "plannedDateTime"
                    )
                    if iso:
                        first_iso = str(iso)
                        break
                if first_iso:
                    try:
                        first_dt = datetime.fromisoformat(
                            first_iso.replace("Z", "+00:00")
                        )
                    except (TypeError, ValueError):
                        first_dt = None
                    if first_dt is not None:
                        # ``plannedDateTime`` is timezone-aware; use the
                        # wall-clock date in that zone so the comparison
                        # against ``now_dt.date()`` (local) is right for
                        # the user.
                        first_date = first_dt.date()
                        self._target_day_offset = (
                            first_date - now_dt.date()
                        ).days
                        self._target_date = first_date.isoformat()

                # Optional: annotate each leg with carriage composition.
                # Mutates legs in place by adding a `composition` key.
                if self.fetch_composition:
                    await self._annotate_compositions(all_trips, headers)

                # v2.25.0: what NS says is wrong with the line this
                # route travels. National news (a calamity) always
                # counts; a stretch of railway counts when one of its
                # stations is on this journey, the ones passed through
                # along the way included.
                if self.watch_disruptions:
                    self.disruptions = await self.async_fetch_disruptions()
                    self.route_disruptions = affecting(
                        self.disruptions, station_keys_of(all_trips),
                    )
                else:
                    self.disruptions = []
                    self.route_disruptions = []

                # v2.28.0: the focus trip and its events, and the
                # disruptions that started or ended on this route.
                self._refresh_focus(all_trips, datetime.now(timezone.utc))
                if self.watch_disruptions:
                    self._refresh_route_disruptions()

                # v2.27.0: the people the user follows on Dienstkaartje,
                # and which of this route's trains they are on. Only the
                # named ones are asked after; nobody else is looked up
                # unless the user presses the button on a card.
                if self.watch_dienstkaartje and self.dienstkaartje_users:
                    self.dienstkaartje = (
                        await self.async_fetch_dienstkaartje_followed()
                    )
                    annotate_trips(all_trips, self.dienstkaartje)
                else:
                    self.dienstkaartje = []

                self._note_available()
                return all_trips

        except (UpdateFailed, ConfigEntryAuthFailed):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            self._last_error_category = "network"
            self._note_unavailable(f"network error: {err}")
            self._maybe_raise_outage_repair()
            raise UpdateFailed(f"Could not reach NS API: {err}") from err

    # ---- live train map helpers ----
    #
    # These are NOT polled. They are called on-demand by WebSocket
    # commands when the user opens the map dialog in the card. The
    # stations geo lookup is cached on the hub's runtime_data so it is
    # fetched at most once per integration setup.

    async def async_fetch_stations_geo(self) -> dict[str, dict[str, Any]]:
        """Return a {code: {name, lat, lng}} map. Cached on runtime_data."""
        runtime: Any = None
        if self._entry is not None:
            runtime = getattr(self._entry, "runtime_data", None)
        if runtime is not None and runtime.stations_geo:
            cached: dict[str, dict[str, Any]] = runtime.stations_geo
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

        out: dict[str, dict[str, Any]] = {}
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

    async def async_fetch_full_rail_network(self) -> dict[str, Any] | None:
        """Download every ProRail Spoorbaanhartlijn feature in NL.

        Returns a GeoJSON FeatureCollection or None on hard failure.
        Pages through the FeatureServer in chunks of 2000 — the server
        caps each request to that size — until exhausted.
        """
        features: list[dict[str, Any]] = []
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

    async def async_fetch_disruptions(
        self, language: str | None = None,
    ) -> list[dict[str, Any]]:
        """Every disruption NS is publishing right now.

        One national request serves every route and every open card,
        so it is fetched once per ``DISRUPTIONS_CACHE_SECONDS`` and
        shared, the same way the vehicle feed is.

        NS writes these texts itself, and writes them twice: ask with
        ``Accept-Language: en`` and the situation, the cause, the
        period, the phase and most of the advice come back in English.
        Those are the only two it publishes, so everything that is not
        Dutch is asked for in English rather than left to NS, which
        answers a German or French reader in Dutch. The cache is per
        language, because a Dutch sensor and an English card can both
        be asking.
        """
        if not self.api_key:
            return []
        lang = disruption_language(language or self.hass.config.language)
        bucket = self._shared()
        cache = bucket.get("_disruptions")
        if not isinstance(cache, dict):
            cache = {}
            bucket["_disruptions"] = cache
        entry = cache.get(lang)
        if isinstance(entry, dict):
            age = time.monotonic() - float(entry.get("at") or 0)
            if age < DISRUPTIONS_CACHE_SECONDS:
                fresh: list[dict[str, Any]] = entry.get("items") or []
                return fresh

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Accept-Language": lang,
        }
        items: list[dict[str, Any]] = []
        try:
            async with async_timeout.timeout(20):
                async with self._session.get(
                    DISRUPTIONS_API_URL,
                    headers=headers,
                    params={"isActive": "true"},
                ) as resp:
                    if resp.status == 200:
                        items = parse_disruptions(await resp.json())
                    else:
                        _LOGGER.debug("Disruptions -> HTTP %s", resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Disruptions failed: %s", err)

        cache[lang] = {"at": time.monotonic(), "items": items}
        return items

    # ---- Dienstkaartje (railway staff publishing their own shift) ----

    def _dienstkaartje_resting(self) -> bool:
        """Whether the site asked to be left alone for a while.

        A 429 is the one thing a hobby server can say about load, so it
        is taken at its word: nothing is asked of it until the backoff
        has run out, and the cards show what was last known instead.
        """
        until = self._shared().get("_dk_backoff_until")
        if not isinstance(until, (int, float)):
            return False
        return time.monotonic() < float(until)

    def _dienstkaartje_rest(self) -> None:
        self._shared()["_dk_backoff_until"] = (
            time.monotonic() + DIENSTKAARTJE_BACKOFF_MINUTES * 60
        )
        _LOGGER.warning(
            "Dienstkaartje asked us to slow down (HTTP 429); leaving it alone "
            "for %d minutes", DIENSTKAARTJE_BACKOFF_MINUTES,
        )

    async def _dienstkaartje_get(
        self, url: str, params: dict[str, str] | None = None,
    ) -> Any | None:
        """One GET, with the manners this API deserves."""
        if self._dienstkaartje_resting():
            return None
        try:
            async with async_timeout.timeout(20):
                async with self._session.get(
                    url,
                    params=params or None,
                    headers={"Accept": "application/json"},
                ) as resp:
                    if resp.status == 429:
                        self._dienstkaartje_rest()
                        return None
                    if resp.status in (401, 403):
                        # A private or password-protected profile. Not
                        # an error: the owner said no.
                        _LOGGER.debug("Dienstkaartje %s is not public", url)
                        return None
                    if resp.status == 404:
                        _LOGGER.debug("Dienstkaartje %s does not exist", url)
                        return None
                    if resp.status != 200:
                        _LOGGER.debug("Dienstkaartje %s -> HTTP %s", url, resp.status)
                        return None
                    return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Dienstkaartje %s failed: %s", url, err)
            return None

    async def async_fetch_dienstkaartje(
        self, username: str, *, date: str | None = None,
    ) -> dict[str, Any] | None:
        """One person's shift, shared between routes and cards.

        Train numbers only. The site will also hand over the route of
        each leg — a few hundred coordinate pairs — and there is no
        reason to take it: NS's journey and vehicle feeds and the
        ProRail network already draw trains here, and a number is all
        it takes to ask them.
        """
        name = clean_username(username)
        if not name:
            return None
        key = f"{name.casefold()}|{date or ''}"
        bucket = self._shared()
        cache = bucket.get("_dienstkaartje")
        if not isinstance(cache, dict):
            cache = {}
            bucket["_dienstkaartje"] = cache
        entry = cache.get(key)
        if isinstance(entry, dict):
            age = time.monotonic() - float(entry.get("at") or 0)
            if age < DIENSTKAARTJE_CACHE_SECONDS:
                known: dict[str, Any] | None = entry.get("profile")
                return known

        params: dict[str, str] = {}
        if date:
            params["date"] = date
        payload = await self._dienstkaartje_get(
            f"{DIENSTKAARTJE_API_URL}/{quote(name, safe='')}", params,
        )
        profile = parse_profile(payload) if payload is not None else None
        if payload is None and isinstance(entry, dict):
            # Nothing came back (resting, or a hiccup): keep what was
            # last known rather than blanking the card.
            stale: dict[str, Any] | None = entry.get("profile")
            return stale
        cache[key] = {"at": time.monotonic(), "profile": profile}
        return profile

    async def async_fetch_dienstkaartje_followed(self) -> list[dict[str, Any]]:
        """The people the user follows, as far as they publish anything."""
        if not self.watch_dienstkaartje or not self.dienstkaartje_follow:
            return []
        followed = self.dienstkaartje_follow[:DIENSTKAARTJE_MAX_FOLLOWED]
        profiles = await asyncio.gather(*(
            self.async_fetch_dienstkaartje(entry["username"]) for entry in followed
        ))
        out: list[dict[str, Any]] = []
        for entry, profile in zip(followed, profiles):
            if not profile:
                continue
            # The role is the user's label, not the site's, so it is
            # attached here rather than read out of the answer. The
            # cached profile is shared, so this makes a copy.
            out.append({**profile, "role": entry.get("role")})
        return out

    async def async_sweep_dienstkaartje(self) -> list[dict[str, Any]]:
        """Everyone on a shift right now, for the on-demand check.

        This is the expensive one — a page of the list, then a request
        per person — so it only runs when the user presses the button
        on a card, the answer is shared for five minutes, and it stops
        after a few pages however many people are out there.
        """
        if not self.watch_dienstkaartje:
            return []
        bucket = self._shared()
        entry = bucket.get("_dienstkaartje_sweep")
        if isinstance(entry, dict):
            age = time.monotonic() - float(entry.get("at") or 0)
            if age < DIENSTKAARTJE_SWEEP_CACHE_SECONDS:
                fresh: list[dict[str, Any]] = entry.get("profiles") or []
                return fresh

        people: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(DIENSTKAARTJE_SWEEP_MAX_PAGES):
            params = {"cursor": cursor} if cursor else None
            payload = await self._dienstkaartje_get(DIENSTKAARTJE_API_URL, params)
            if payload is None:
                break
            page, cursor = parse_list(payload)
            people.extend(page)
            if not cursor or len(people) >= DIENSTKAARTJE_SWEEP_MAX_PEOPLE:
                break

        names = [person["username"] for person in people][
            :DIENSTKAARTJE_SWEEP_MAX_PEOPLE
        ]
        profiles = [
            profile
            for profile in await asyncio.gather(*(
                self.async_fetch_dienstkaartje(name) for name in names
            ))
            if profile
        ]
        if profiles or not isinstance(entry, dict):
            bucket["_dienstkaartje_sweep"] = {
                "at": time.monotonic(), "profiles": profiles,
            }
        return profiles

    async def async_search_trips(
        self,
        from_station: str,
        to_station: str,
        *,
        via: str | None = None,
        when: str | None = None,
        arrival: bool = False,
        train_types: list[str] | None = None,
        extras: bool = True,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """One-off journey search, for the search card.

        Deliberately separate from the route refresh: it touches none
        of the coordinator's own state, keeps no favourites and updates
        no sensor. A traveller looking something up on a platform gets
        an answer and nothing else changes.

        Returns the trips and, when something went wrong, a short
        reason to put in front of the user.
        """
        if not self.api_key:
            return [], "no_api_key"
        if not from_station or not to_station:
            return [], "missing_station"

        params: dict[str, str] = {
            "fromStation": from_station,
            "toStation": to_station,
        }
        if via:
            params["viaStation"] = via
        if when:
            params["dateTime"] = when
        if arrival:
            params["searchForArrival"] = "true"

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        try:
            async with async_timeout.timeout(20):
                async with self._session.get(
                    API_URL, headers=headers, params=params,
                ) as response:
                    if response.status in (401, 403):
                        return [], "rejected"
                    if response.status == 400:
                        return [], "unknown_station"
                    if response.status != 200:
                        _LOGGER.debug(
                            "Search %s -> %s returned HTTP %s",
                            from_station, to_station, response.status,
                        )
                        return [], "unavailable"
                    data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Search %s -> %s failed: %s", from_station, to_station, err)
            return [], "unavailable"

        trips = [t for t in (data or {}).get("trips") or [] if isinstance(t, dict)]
        if train_types:
            trips = apply_train_type_filter(trips, train_types)
            if not trips:
                return [], "no_match"
        # The carriages, when the hub is set to fetch them: a search
        # result should show what a route's own card shows. Filtering
        # comes first so nothing is fetched for a trip about to be
        # dropped.
        if not extras:
            # The last-train lookup wants times, not carriages.
            return trips, None
        await self._annotate_compositions(trips, headers, reset=False)
        # And the people the user follows, on the same terms.
        if self.watch_dienstkaartje and self.dienstkaartje_users:
            annotate_trips(trips, await self.async_fetch_dienstkaartje_followed())
        return trips, None

    def _shared(self) -> dict[str, Any]:
        """The bucket every route coordinator in this install shares.

        Live positions and journeys are properties of a train, not of a
        route, so two routes that happen to use the same train fetch it
        once between them.
        """
        bucket: dict[str, Any] = self.hass.data.setdefault(DOMAIN, {})
        return bucket

    async def async_fetch_vehicles(self) -> dict[str, dict[str, Any]]:
        """Every train NS currently reports a GPS position for.

        Requested without the ``lat``/``lng``/``radius`` parameters the
        NS App sends. Those are interpreted in metres, so asking for a
        radius of 300 around a point in the middle of the country —
        which is what this integration did until v2.21.0 — returns an
        empty list, and live positions quietly vanished from the map.
        Unfiltered, the whole country is roughly 40 kB, fetched once per
        ``VEHICLE_CACHE_SECONDS`` and shared by every route and every
        open map.
        """
        if not self.api_key:
            return {}
        bucket = self._shared()
        cached = self._cached_vehicles(bucket)
        if cached is not None:
            return cached
        lock = bucket.get("_vehicles_lock")
        if not isinstance(lock, asyncio.Lock):
            lock = bucket["_vehicles_lock"] = asyncio.Lock()
        async with lock:
            # Another tick may have filled the cache while we queued.
            cached = self._cached_vehicles(bucket)
            if cached is not None:
                return cached
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            index: dict[str, dict[str, Any]] = {}
            for url in (
                VIRTUAL_TRAIN_VEHICLE_URL,
                VIRTUAL_TRAIN_VEHICLE_FALLBACK_URL,
            ):
                try:
                    async with async_timeout.timeout(15):
                        async with self._session.get(url, headers=headers) as resp:
                            if resp.status != 200:
                                _LOGGER.debug(
                                    "Vehicle feed %s -> HTTP %s", url, resp.status,
                                )
                                continue
                            payload = await resp.json()
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    _LOGGER.debug("Vehicle feed %s failed: %s", url, err)
                    continue
                index = vehicle_index(payload)
                if index:
                    break
            # An empty result is cached too: a feed that is down should
            # not be asked again on every single lookup.
            bucket["_vehicles"] = {"at": time.monotonic(), "by_ride": index}
            return index

    @staticmethod
    def _cached_vehicles(
        bucket: dict[str, Any],
    ) -> dict[str, dict[str, Any]] | None:
        """The shared vehicle index while it is still fresh."""
        entry = bucket.get("_vehicles")
        if not isinstance(entry, dict):
            return None
        if time.monotonic() - float(entry.get("at") or 0) >= VEHICLE_CACHE_SECONDS:
            return None
        index: dict[str, dict[str, Any]] = entry.get("by_ride") or {}
        return index

    async def async_fetch_vehicle_position(
        self, train_number: str,
    ) -> dict[str, Any] | None:
        """This train's GPS fix from NS's own live vehicle feed."""
        if not train_number:
            return None
        vehicles = await self.async_fetch_vehicles()
        fix: dict[str, Any] | None = vehicles.get(str(train_number).strip())
        return fix

    async def async_fetch_train_position(
        self, train_number: str, anchor_iso: str | None = None,
    ) -> dict[str, Any] | None:
        """The best position available for one train.

        NS's own vehicle feed first, because it is national and shared;
        ProRail's ArcGIS feed second, in case it ever answers again; and
        the station-based estimate last, so a train that reports no GPS
        at all still appears somewhere truthful.
        """
        position = await self.async_fetch_vehicle_position(train_number)
        if position is None:
            position = await self.async_fetch_arcgis_position(train_number)
        if position is None:
            position = await self._async_station_based_position(
                train_number, anchor_iso,
            )
        return position

    async def async_journey_stops(self, train_number: str) -> list[dict[str, Any]]:
        """The train's complete run for today, parsed and cached.

        Everything the live map needs beyond the traveller's own leg:
        the stations before they board, the ones after they get out, and
        the times NS reports at each of them.
        """
        if not train_number or not self.api_key:
            return []
        key = str(train_number).strip()
        cache = self._shared().setdefault("_journeys", {})
        entry = cache.get(key)
        if isinstance(entry, dict):
            age = time.monotonic() - float(entry.get("at") or 0)
            if age < JOURNEY_CACHE_SECONDS:
                fresh: list[dict[str, Any]] = entry.get("stops") or []
                return fresh

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        stops: list[dict[str, Any]] = []
        try:
            async with async_timeout.timeout(15):
                async with self._session.get(
                    JOURNEY_API_URL,
                    headers=headers,
                    params={"train": key, "omitCrowdForecast": "true"},
                ) as resp:
                    if resp.status == 200:
                        stops = parse_journey(await resp.json())
                    else:
                        _LOGGER.debug(
                            "Journey %s -> HTTP %s", key, resp.status,
                        )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Journey %s failed: %s", key, err)

        now = time.monotonic()
        cache[key] = {"at": now, "stops": stops}
        # Keep the cache from growing for the rest of the day: anything
        # nobody asked about for a while can go.
        for stale in [
            k for k, v in cache.items()
            if isinstance(v, dict)
            and now - float(v.get("at") or 0) > JOURNEY_CACHE_SECONDS * 10
        ]:
            cache.pop(stale, None)
        return stops

    async def async_journey_run(
        self, train_number: str,
    ) -> tuple[datetime | None, datetime | None]:
        """When this train starts its run and when it finishes it."""
        return run_window(await self.async_journey_stops(train_number))

    async def async_fetch_arcgis_position(self, train_number: str) -> dict[str, Any] | None:
        """Live train GPS via ProRail's public ArcGIS NS_treinlocaties.

        Returns smooth lat/lng + speed (km/h) + heading (degrees) +
        epoch-ms timestamp. No NS API key required for this endpoint.
        The query filters on ``treinNummer`` so we get exactly the
        user's run, not a random rotation that shares the ritnummer.

        This is the second source, behind NS's own vehicle feed: the
        service has been answering "Error invoking service" for a while,
        and it answers with that error inside an HTTP 200, so a failure
        is recognised from the body rather than the status. After a few
        of them the feed is left alone for ``ARCGIS_BACKOFF_MINUTES``
        rather than costing a request per train per tick.
        """
        if not train_number:
            return None
        try:
            target = int(str(train_number).strip())
        except (TypeError, ValueError):
            return None
        bucket = self._shared()
        blocked = bucket.get("_arcgis_quiet_until")
        if blocked is not None and time.monotonic() < float(blocked):
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
                        self._note_arcgis_failure(bucket, f"HTTP {resp.status}")
                        return None
                    data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("ArcGIS fetch %s failed: %s", target, err)
            self._note_arcgis_failure(bucket, str(err))
            return None

        error = (data or {}).get("error")
        if error:
            self._note_arcgis_failure(bucket, str(error)[:120])
            return None
        bucket["_arcgis_failures"] = 0
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

    @staticmethod
    def _note_arcgis_failure(bucket: dict[str, Any], reason: str) -> None:
        """Count a failed ArcGIS call and go quiet after a few."""
        failures = int(bucket.get("_arcgis_failures") or 0) + 1
        bucket["_arcgis_failures"] = failures
        if failures < ARCGIS_FAILURES_BEFORE_BACKOFF:
            return
        bucket["_arcgis_quiet_until"] = (
            time.monotonic() + ARCGIS_BACKOFF_MINUTES * 60
        )
        bucket["_arcgis_failures"] = 0
        _LOGGER.debug(
            "ArcGIS positions unavailable (%s); pausing it for %d minutes",
            reason, ARCGIS_BACKOFF_MINUTES,
        )

    async def _async_station_based_position(
        self, train_number: str, anchor_iso: str | None = None,
    ) -> dict[str, Any] | None:
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
