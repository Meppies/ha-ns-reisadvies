"""NS Reisadvies integration.

v2 architecture: ONE hub config entry holds the integration-wide
options (api_key, scan interval, favourite retention, fetch
composition). Each route lives as a subentry under the hub
(from_station / to_station). Per-route coordinators are managed
in async_setup_entry below.

Legacy v1 installs (one ConfigEntry per route) are migrated to
this hub+subentries layout in async_migrate_entry. The migration
preserves sensor entity_ids by rewriting unique_id mappings in
the entity registry.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import time as _time
from datetime import timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components import lovelace, websocket_api
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.loader import async_get_integration

from .const import (
    DOMAIN,
    CONFIG_ENTRY_VERSION,
    SUBENTRY_TYPE_ROUTE,
    CONF_API_KEY,
    CONF_FROM_STATION,
    CONF_TO_STATION,
    CONF_SCAN_INTERVAL,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    CONF_LIVE_TRAIN_MAP,
    CONF_LIVE_MAP_REFRESH_SECONDS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
    DEFAULT_FETCH_COMPOSITION,
    DEFAULT_LIVE_TRAIN_MAP,
    DEFAULT_LIVE_MAP_REFRESH_SECONDS,
)
from .coordinator import NSUpdateCoordinator
from .types import NSConfigEntry, NSRuntimeData


# Hub-wide options keys — these are the entries that move from
# ConfigEntry.data (v2 layout) to ConfigEntry.options (v3 layout). Used
# by the v2→v3 migration and by async_setup_entry to read settings.
_OPTION_KEYS: tuple[str, ...] = (
    CONF_SCAN_INTERVAL,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    CONF_LIVE_TRAIN_MAP,
    CONF_LIVE_MAP_REFRESH_SECONDS,
)


def _option(entry: NSConfigEntry, key: str, default: Any) -> Any:
    """Read a hub option, preferring options over data.

    After the v2→v3 migration, configurable settings live on
    ``entry.options``. Older installs may still have them on
    ``entry.data`` if the migration hasn't run yet on a given boot —
    fall back so we never blow up on a half-migrated entry.
    """
    if entry.options and key in entry.options:
        return entry.options[key]
    if key in entry.data:
        return entry.data[key]
    return default

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CARD_URL = "/ns_reisadvies/ns-reisadvies-card.js"
RAIL_FILE = "rail.geojson"
RAIL_REFRESH_INTERVAL = timedelta(days=7)
RAIL_MAX_AGE_SECONDS = 7 * 24 * 3600


# ---------------------------------------------------------------------------
# Migration: v1 multi-entry → v2 single hub + subentries.
# ---------------------------------------------------------------------------


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older entry layouts up to the current schema.

    Migrations are idempotent and chained — each step lifts the entry
    one version forward.
    """
    if entry.version >= CONFIG_ENTRY_VERSION:
        return True

    _LOGGER.info(
        "Migrating NS Reisadvies entry %s from v%s to v%s",
        entry.entry_id, entry.version, CONFIG_ENTRY_VERSION,
    )

    # ---- v2 → v3 ----------------------------------------------------------
    # Move hub-wide configurable options from ConfigEntry.data (legacy
    # layout: everything in `data`) to ConfigEntry.options (correct
    # layout per the Bronze "ConfigEntry.data and ConfigEntry.options"
    # quality-scale rule). ConfigEntry.data should only carry the
    # credentials and immutable setup fields.
    if entry.version == 2:
        new_data: dict[str, Any] = dict(entry.data)
        new_options: dict[str, Any] = dict(entry.options or {})
        for key in _OPTION_KEYS:
            if key in new_data and key not in new_options:
                new_options[key] = new_data.pop(key)
        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, version=3,
        )
        _LOGGER.debug(
            "v2→v3 migration complete: moved %d option(s) to entry.options",
            len(new_options),
        )
        return True

    # ---- v1 → v2 (legacy multi-entry → hub + subentries) ------------------
    # Sort all v1 entries: oldest becomes the hub.
    legacy = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.version == 1
    ]
    legacy.sort(key=lambda e: e.entry_id)

    if not legacy:
        # No legacy entries — nothing to migrate. Returning True signals
        # success and HA stamps the new version automatically.
        return True

    primary = legacy[0]

    # Only the primary actually does the migration. For non-primary
    # legacy entries we just return True and let HA update the
    # version-marker; the primary will then remove them in its own
    # migrate_entry call.
    if entry.entry_id != primary.entry_id:
        return True

    # Build hub data from primary's options + data
    def _opt(e: ConfigEntry, key: str, default: Any) -> Any:
        if e.options and key in e.options:
            return e.options[key]
        if key in e.data:
            return e.data[key]
        return default

    hub_data = {
        CONF_API_KEY: _opt(primary, CONF_API_KEY, ""),
        CONF_SCAN_INTERVAL: int(_opt(primary, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        CONF_FAV_HOURS: int(_opt(primary, CONF_FAV_HOURS, DEFAULT_FAV_HOURS)),
        CONF_FETCH_COMPOSITION: bool(_opt(primary, CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION)),
    }

    # Build subentries from EVERY legacy entry, including primary
    subentries = []
    legacy_id_to_route: dict[str, tuple[str, str]] = {}
    for legacy_entry in legacy:
        from_st = legacy_entry.data.get(CONF_FROM_STATION)
        to_st = legacy_entry.data.get(CONF_TO_STATION)
        if not from_st or not to_st:
            continue
        unique_id = f"{from_st}_{to_st}".lower()
        subentries.append(
            ConfigSubentry(
                data={
                    CONF_FROM_STATION: from_st,
                    CONF_TO_STATION: to_st,
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=f"{from_st} -> {to_st}",
                unique_id=unique_id,
            )
        )
        legacy_id_to_route[legacy_entry.entry_id] = (from_st, to_st)

    # Update the entity registry: old sensor unique_id was the legacy
    # entry's entry_id. Map each to the new deterministic id so that
    # sensor.ns_<from>_<to> entity_ids stay the same.
    ent_reg = er.async_get(hass)
    for legacy_entry in legacy:
        route = legacy_id_to_route.get(legacy_entry.entry_id)
        if not route:
            continue
        new_uid = f"{route[0]}_{route[1]}".lower()
        for entity in er.async_entries_for_config_entry(ent_reg, legacy_entry.entry_id):
            try:
                ent_reg.async_update_entity(
                    entity.entity_id,
                    new_unique_id=new_uid,
                    config_entry_id=primary.entry_id,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Could not move entity %s to hub: %s", entity.entity_id, err)

    # Update primary into the hub: new title, data, subentries.
    # The version is stamped automatically when this function returns
    # True — no need to pass version= here.
    hass.config_entries.async_update_entry(
        primary,
        title="NS Reisadvies",
        data=hub_data,
        options={},
    )

    # Add subentries one by one — async_update_entry doesn't take
    # subentries directly, but async_add_subentry does.
    for sub in subentries:
        try:
            hass.config_entries.async_add_subentry(primary, sub)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not add subentry %s: %s", sub.title, err)

    # Schedule removal of the OTHER legacy entries; primary stays as hub.
    for legacy_entry in legacy[1:]:
        hass.async_create_task(
            hass.config_entries.async_remove(legacy_entry.entry_id)
        )

    return True


# ---------------------------------------------------------------------------
# Setup / unload.
# ---------------------------------------------------------------------------


async def _recover_subentries_from_storage(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """If the hub has no route subentries (e.g. because a v1->v2
    migration partially failed) but the per-route Store files are
    still on disk, reconstruct subentries from those file names.
    """
    if entry.subentries:
        return

    from .stations import STATIONS  # noqa: WPS433 — local import to avoid cycle
    station_lookup = {s.lower(): s for s in STATIONS}
    storage_dir = hass.config.path(".storage")

    try:
        files = await hass.async_add_executor_job(os.listdir, storage_dir)
    except Exception:  # noqa: BLE001
        return

    routes: list[tuple[str, str]] = []
    for fname in files:
        if not fname.startswith("ns_reisadvies_tracked_trips_"):
            continue
        rest = fname[len("ns_reisadvies_tracked_trips_"):]
        # Try splits matching known station names. Stations may
        # contain underscores after sanitisation; iterate possible
        # split points and verify both halves against the lookup.
        parts = rest.split("_")
        found = False
        for i in range(1, len(parts)):
            fr = "_".join(parts[:i]).replace("_", " ")
            to = "_".join(parts[i:]).replace("_", " ")
            if fr.lower() in station_lookup and to.lower() in station_lookup:
                routes.append((station_lookup[fr.lower()], station_lookup[to.lower()]))
                found = True
                break
        if not found and len(parts) == 2:
            # Last-resort: assume the simple two-part case
            routes.append((parts[0], parts[1]))

    if not routes:
        return

    _LOGGER.warning(
        "Hub has no subentries; reconstructing %d route(s) from storage", len(routes)
    )
    for fr, to in routes:
        try:
            sub = ConfigSubentry(
                data={CONF_FROM_STATION: fr, CONF_TO_STATION: to},
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=f"{fr} -> {to}",
                unique_id=f"{fr}_{to}".lower(),
            )
            hass.config_entries.async_add_subentry(entry, sub)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not recover subentry %s -> %s: %s", fr, to, err)


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up the hub: build a coordinator per route subentry.

    Per the Bronze quality-scale rule ``runtime-data``, all per-entry
    runtime state lives on ``entry.runtime_data`` (typed via
    ``NSRuntimeData``). The hub-wide registrations that are scoped to
    a single Home Assistant process — WebSocket commands, the rail-
    cache refresh schedule, the static path and Lovelace resource —
    still live in ``hass.data[DOMAIN]`` because they need to outlive
    a single entry reload (``single_config_entry: true`` ensures we
    only ever have one entry, but reloads still call setup again).
    """
    hass.data.setdefault(DOMAIN, {})
    runtime = NSRuntimeData()

    # Self-heal: if a previous (failed) migration left the hub without
    # subentries, try to rebuild them from the per-route Store files.
    await _recover_subentries_from_storage(hass, entry)

    # Hub-wide config: credentials live on entry.data, all configurable
    # settings live on entry.options (post-v2→v3 migration). The
    # _option() helper falls back to entry.data if a v2 install hasn't
    # been migrated yet.
    api_key = entry.data.get(CONF_API_KEY)
    scan_interval = int(_option(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    fav_hours = int(_option(entry, CONF_FAV_HOURS, DEFAULT_FAV_HOURS))
    fetch_composition = bool(
        _option(entry, CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION)
    )
    live_train_map = bool(_option(entry, CONF_LIVE_TRAIN_MAP, DEFAULT_LIVE_TRAIN_MAP))
    live_map_refresh = int(_option(
        entry, CONF_LIVE_MAP_REFRESH_SECONDS, DEFAULT_LIVE_MAP_REFRESH_SECONDS,
    ))

    runtime.live_train_map_enabled = live_train_map
    runtime.live_map_refresh_seconds = max(5, min(60, live_map_refresh))

    # Coordinator per subentry. Stored on runtime.coordinators so the
    # sensor platform can pick them up via entry.runtime_data.
    coordinators: dict[str, NSUpdateCoordinator] = {}
    for subentry_id, subentry in (entry.subentries or {}).items():
        if subentry.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        from_st = subentry.data.get(CONF_FROM_STATION)
        to_st = subentry.data.get(CONF_TO_STATION)
        if not from_st or not to_st:
            continue
        coordinator = NSUpdateCoordinator(
            hass,
            entry=entry,
            api_key=api_key,
            from_station=from_st,
            to_station=to_st,
            scan_interval_minutes=scan_interval,
            fav_hours=fav_hours,
            fetch_composition=fetch_composition,
        )
        await coordinator.async_load_tracked()
        # Use async_refresh (which never throws) instead of
        # async_config_entry_first_refresh: a transient NS API outage
        # (HTTP 5xx) on first boot would otherwise put the WHOLE entry in
        # setup_retry, so all our sensors disappear and the user's
        # Lovelace cards show "Configuration error" until NS recovers.
        # async_refresh logs the failure but keeps coordinator.data=None,
        # so the sensor exists in "No trips" state and the UI stays alive
        # while the periodic update retries on its own.
        await coordinator.async_refresh()
        coordinators[subentry_id] = coordinator

    runtime.coordinators = coordinators
    entry.runtime_data = runtime

    # Backfill: link existing entities to their subentry by unique_id.
    # Entities created before HA's subentry-aware async_add_entities have
    # config_subentry_id=None; this rewrites them so HA tracks the link
    # and the entity is shown under the right subentry in the UI.
    _backfill_entity_subentries(hass, entry)

    # WebSocket commands for the live-train map. Registered once per HA
    # (websocket_api.async_register_command rejects duplicates). We
    # track this via hass.data because the registration outlives the
    # entry's runtime_data.
    if not hass.data[DOMAIN].get("_ws_registered"):
        websocket_api.async_register_command(hass, _ws_track_train_start)
        websocket_api.async_register_command(hass, _ws_track_train_poll)
        websocket_api.async_register_command(hass, _ws_track_train_stop)
        hass.data[DOMAIN]["_ws_registered"] = True

    # Schedule the rail-cache refresh once per HA boot. Runs ~30s after
    # setup so the integration finishes booting first, then weekly.
    if not hass.data[DOMAIN].get("_rail_refresh_scheduled") and coordinators:
        hass.data[DOMAIN]["_rail_refresh_scheduled"] = True
        first_coord = next(iter(coordinators.values()))

        async def _periodic_rail_refresh(_now: Any = None) -> None:
            await _async_refresh_rail_cache(hass, first_coord)

        async_call_later(hass, 30, _periodic_rail_refresh)
        async_track_time_interval(
            hass, _periodic_rail_refresh, RAIL_REFRESH_INTERVAL,
        )

    # Static path + Lovelace card auto-registration (one-shot per HA).
    if not hass.data[DOMAIN].get("static_paths_registered"):
        path = hass.config.path("custom_components/ns_reisadvies/www")
        if os.path.isdir(path):
            await hass.http.async_register_static_paths([
                StaticPathConfig(
                    url_path="/ns_reisadvies",
                    path=path,
                    cache_headers=False,
                )
            ])
            hass.data[DOMAIN]["static_paths_registered"] = True

            try:
                integration = await async_get_integration(hass, DOMAIN)
                version = str(integration.version or "0")
            except Exception:  # noqa: BLE001
                version = "0"
            await _async_register_card_resource(hass, version)
            hass.data[DOMAIN]["card_url_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


# ---------------------------------------------------------------------------
# Live-train-map WebSocket commands.
# ---------------------------------------------------------------------------
#
# These commands let the card open a map dialog without polluting the
# entity registry. We use transient hass.states entries (no registry
# entry, just state-machine tombstones) so ha-map can plot them. On
# track_train_stop or session timeout, the states are removed.
#
# Session shape (entry.runtime_data.live_sessions[sid]):
#   {
#     "train_entity_id": "device_tracker.ns_reisadvies_train_<sid>",
#     "stop_entity_ids": ["device_tracker.ns_reisadvies_stop_<sid>_0", ...],
#     "train_number": "5710",
#     "cleanup": <CALLBACK>,
#   }


def _hub_entry(hass: HomeAssistant) -> NSConfigEntry | None:
    """Return the (single) NS Reisadvies hub config entry, or None.

    With ``single_config_entry: true`` set in the manifest, there is at
    most one entry; we return it whenever the integration is loaded.
    """
    for entry in hass.config_entries.async_entries(DOMAIN):
        return entry  # type: ignore[return-value]
    return None


def _runtime(hass: HomeAssistant) -> NSRuntimeData | None:
    """Return runtime_data of the loaded hub entry, or None if not up."""
    entry = _hub_entry(hass)
    if entry is None:
        return None
    return getattr(entry, "runtime_data", None)


def _live_sessions(hass: HomeAssistant) -> dict[str, dict]:
    """Return the per-HA live-train-map session map.

    Backed by ``entry.runtime_data.live_sessions`` so it is torn down on
    integration unload. If the entry isn't loaded yet (e.g. an early WS
    callback) we fall back to a process-local dict to avoid crashes.
    """
    runtime = _runtime(hass)
    if runtime is not None:
        return runtime.live_sessions
    return hass.data.setdefault(DOMAIN, {}).setdefault("_live_sessions", {})


def _any_coordinator(hass: HomeAssistant) -> NSUpdateCoordinator | None:
    """Return any per-route coordinator (they all share the api_key)."""
    runtime = _runtime(hass)
    if runtime is None:
        return None
    for coord in runtime.coordinators.values():
        return coord
    return None


def _resolve_stops(stops: list[dict], geo: dict[str, dict]) -> list[dict]:
    """Normalise the stop list the card sent, falling back to the
    /v2/stations geo cache only when the stop did not include lat/lng.

    NS' /v3/trips response already carries lat/lng on every leg.stops
    entry, so the cache is just a backstop for older HA cards or for
    callers that strip coordinates client-side. Each stop also keeps
    `passed` (derived by the card from actualDepartureDateTime) and
    `uicCode` so the WS handler can validate the train position.
    """
    by_name = {v["name"].casefold(): v for v in geo.values()}
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    def _passed_from_iso(value: str | None) -> bool:
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed < now

    out: list[dict] = []
    for s in stops or []:
        name = (s.get("name") or "").strip()
        uic = (s.get("uicCode") or s.get("code") or "").upper()
        lat = s.get("lat")
        lng = s.get("lng")
        if (lat is None or lng is None) and (uic in geo or name.casefold() in by_name):
            match = geo.get(uic) or by_name.get(name.casefold())
            if match:
                lat = match["lat"]
                lng = match["lng"]
                if not name:
                    name = match["name"]
        passed = bool(s.get("passed"))
        if not passed:
            passed = _passed_from_iso(
                s.get("actualDepartureDateTime")
                or s.get("plannedDepartureDateTime")
            )
        out.append({
            "name": name or uic,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "uicCode": uic,
            "passed": passed,
        })
    return out


def _set_train_state(
    hass: HomeAssistant, entity_id: str, friendly_name: str, pos: dict
) -> None:
    """Write a transient state representing the train's live position."""
    hass.states.async_set(
        entity_id,
        "moving",
        {
            "latitude": pos["lat"],
            "longitude": pos["lng"],
            "source_type": "gps",
            "gps_accuracy": 50,
            "icon": "mdi:train",
            "friendly_name": friendly_name,
            "speed": pos.get("speed"),
            "heading": pos.get("heading"),
            "last_seen": pos.get("ts"),
        },
        force_update=True,
    )


def _set_stop_state(
    hass: HomeAssistant, entity_id: str, name: str, lat: float, lng: float
) -> None:
    hass.states.async_set(
        entity_id,
        "station",
        {
            "latitude": lat,
            "longitude": lng,
            "source_type": "gps",
            "gps_accuracy": 50,
            "icon": "mdi:circle-medium",
            "friendly_name": name,
        },
    )


def _cleanup_session(hass: HomeAssistant, session_id: str) -> None:
    sessions = _live_sessions(hass)
    sess = sessions.pop(session_id, None)
    if not sess:
        return
    for ent in [sess.get("train_entity_id")] + (sess.get("stop_entity_ids") or []):
        if ent:
            hass.states.async_remove(ent)
    cancel = sess.get("cleanup")
    if cancel:
        try:
            cancel()
        except Exception:  # noqa: BLE001
            pass


def _arm_cleanup(hass: HomeAssistant, session_id: str, seconds: int = 600) -> None:
    """Schedule auto-cleanup if no poll arrives within `seconds`."""
    sessions = _live_sessions(hass)
    sess = sessions.get(session_id)
    if not sess:
        return
    cancel = sess.get("cleanup")
    if cancel:
        try:
            cancel()
        except Exception:  # noqa: BLE001
            pass

    @callback
    def _fire(_now: Any) -> None:
        _LOGGER.debug("Auto-cleaning live train session %s", session_id)
        _cleanup_session(hass, session_id)

    sess["cleanup"] = async_call_later(hass, seconds, _fire)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ns_reisadvies/track_train_start",
        vol.Required("train_number"): vol.Any(str, int),
        vol.Optional("stops", default=[]): list,
        vol.Optional("anchor"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def _ws_track_train_start(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    coord = _any_coordinator(hass)
    if coord is None:
        connection.send_error(msg["id"], "no_hub", "NS Reisadvies hub not loaded")
        return

    train_number = str(msg["train_number"])
    raw_stops: list[dict] = msg.get("stops") or []
    anchor_iso: str | None = msg.get("anchor") or None

    geo = await coord.async_fetch_stations_geo()
    # Start from the user's leg (always safe; comes with lat/lng and
    # actualDepartureDateTime baked in). Then try /v2/journey for the
    # FULL train run (incl. stops before the user's origin or after
    # their destination). Use it only if it actually has more stops —
    # /v2/journey returns 404 for some public NS-App keys, in which
    # case we keep the leg-derived list.
    leg_resolved = _resolve_stops(raw_stops, geo)
    journey_full = await coord.async_fetch_journey_route(train_number)
    if len(journey_full) > len(leg_resolved):
        # Merge: take the journey list, but copy passed-flags from the
        # leg's stops where they overlap (leg has fresher actual
        # departure data because it came from /v3/trips with the
        # user's planning context).
        leg_passed_by_uic = {
            s.get("uicCode"): s.get("passed") for s in leg_resolved if s.get("uicCode")
        }
        for js in journey_full:
            uic = js.get("uicCode")
            if uic and uic in leg_passed_by_uic:
                js["passed"] = bool(leg_passed_by_uic[uic] or js.get("passed"))
        resolved = journey_full
    else:
        resolved = leg_resolved
    plotted = [s for s in resolved if s.get("lat") is not None and s.get("lng") is not None]
    journey_stops = resolved

    # Live GPS position via ProRail's public ArcGIS NS_treinlocaties
    # service — same feed as treinposities.nl. Returns real lat/lng,
    # speed (km/h), heading (degrees) and a timestamp. Filters on the
    # ritnummer server-side so the wrong-train problem of /v1/trein
    # disappears.
    pos = await coord.async_fetch_arcgis_position(train_number)

    session_id = secrets.token_hex(6)
    train_entity_id = f"device_tracker.ns_reisadvies_train_{session_id}"
    stop_entity_ids: list[str] = []

    if pos:
        _set_train_state(hass, train_entity_id, f"Trein {train_number}", pos)

    for i, st in enumerate(plotted):
        eid = f"device_tracker.ns_reisadvies_stop_{session_id}_{i}"
        _set_stop_state(hass, eid, st["name"], st["lat"], st["lng"])
        stop_entity_ids.append(eid)

    _live_sessions(hass)[session_id] = {
        "train_entity_id": train_entity_id,
        "stop_entity_ids": stop_entity_ids,
        "train_number": train_number,
        "anchor": anchor_iso,
        "leg_points": [
            (s["lat"], s["lng"]) for s in resolved
            if s.get("lat") is not None and s.get("lng") is not None
        ],
    }
    _arm_cleanup(hass, session_id)

    connection.send_result(
        msg["id"],
        {
            "session_id": session_id,
            "train_entity_id": train_entity_id if pos else None,
            "stop_entity_ids": stop_entity_ids,
            "stops": resolved,
            "journey_stops": journey_stops,
            "train_position": pos,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ns_reisadvies/track_train_poll",
        vol.Required("session_id"): str,
    }
)
@websocket_api.async_response
async def _ws_track_train_poll(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    sessions = _live_sessions(hass)
    sess = sessions.get(msg["session_id"])
    if not sess:
        connection.send_error(msg["id"], "unknown_session", "Session not found")
        return
    coord = _any_coordinator(hass)
    if coord is None:
        connection.send_error(msg["id"], "no_hub", "NS Reisadvies hub not loaded")
        return

    pos = await coord.async_fetch_arcgis_position(sess["train_number"])
    if pos:
        _set_train_state(
            hass,
            sess["train_entity_id"],
            f"Trein {sess['train_number']}",
            pos,
        )
    _arm_cleanup(hass, msg["session_id"])
    connection.send_result(
        msg["id"], {"train_position": pos},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ns_reisadvies/track_train_stop",
        vol.Required("session_id"): str,
    }
)
@callback
def _ws_track_train_stop(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    _cleanup_session(hass, msg["session_id"])
    connection.send_result(msg["id"], {"ok": True})




def _backfill_entity_subentries(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set config_subentry_id on existing entities by matching unique_id.

    Older sensors created before HA's subentry-aware async_add_entities
    (or added via legacy migration) end up with config_subentry_id=None
    even though they conceptually belong to a subentry. This function
    finds them by unique_id and links them to the matching subentry.
    """
    ent_reg = er.async_get(hass)
    # Build a unique_id -> subentry_id map for this hub's route subentries.
    uid_to_subentry: dict[str, str] = {}
    for sub_id, sub in (entry.subentries or {}).items():
        if sub.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        from_st = sub.data.get(CONF_FROM_STATION)
        to_st = sub.data.get(CONF_TO_STATION)
        if not from_st or not to_st:
            continue
        uid_to_subentry[f"{from_st}_{to_st}".lower()] = sub_id

    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent.config_subentry_id:
            continue
        target = uid_to_subentry.get(ent.unique_id)
        if not target:
            continue
        try:
            ent_reg.async_update_entity(
                ent.entity_id, config_subentry_id=target
            )
            _LOGGER.debug(
                "Linked %s (uid=%s) to subentry %s",
                ent.entity_id, ent.unique_id, target,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Could not link %s to subentry %s: %s",
                ent.entity_id, target, err,
            )


async def _async_refresh_rail_cache(
    hass: HomeAssistant, coord: NSUpdateCoordinator, force: bool = False,
) -> None:
    """Download the full ProRail rail network if missing or > 7 days old.

    Stores it as plain GeoJSON next to the card.js so it can be served
    by the same static path. Roughly 5–10 MB on disk, browser-cacheable.
    """
    www_dir = hass.config.path("custom_components/ns_reisadvies/www")
    target = Path(www_dir) / RAIL_FILE
    if not force and target.exists():
        try:
            age = _time.time() - target.stat().st_mtime
        except OSError:
            age = RAIL_MAX_AGE_SECONDS + 1
        if age < RAIL_MAX_AGE_SECONDS:
            return
    data = await coord.async_fetch_full_rail_network()
    if not data:
        return

    def _write() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Compact JSON to keep the file small; GeoJSON parsers are fine
        # with no whitespace.
        target.write_text(
            json.dumps(data, separators=(",", ":")), encoding="utf-8",
        )

    try:
        await hass.async_add_executor_job(_write)
        _LOGGER.info(
            "NS Reisadvies: rail.geojson cached (%d features)",
            len(data.get("features", [])),
        )
    except OSError as err:
        _LOGGER.warning("NS Reisadvies: could not write rail cache: %s", err)


async def _async_register_card_resource(hass: HomeAssistant, version: str) -> None:
    """Register the Lovelace card via add_extra_js_url and Lovelace resources."""
    url = f"{CARD_URL}?v={version}"
    try:
        add_extra_js_url(hass, url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("add_extra_js_url failed: %s", err)

    try:
        lov_data = hass.data.get(lovelace.DOMAIN)
        if lov_data is None:
            return
        resources = getattr(lov_data, "resources", None)
        if resources is None and isinstance(lov_data, dict):
            resources = lov_data.get("resources")
        if resources is None:
            return
        if not resources.loaded:
            await resources.async_load()

        existing = next(
            (r for r in resources.async_items() if (r.get("url") or "").split("?")[0] == CARD_URL),
            None,
        )
        if existing:
            if existing.get("url") != url:
                await resources.async_update_item(
                    existing["id"], {"url": url, "res_type": existing.get("type", "module")}
                )
        else:
            await resources.async_create_item({"url": url, "res_type": "module"})
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not auto-register Lovelace resource (you may need to add %s manually): %s",
            url, err,
        )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the hub when global options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload the hub.

    HA clears ``entry.runtime_data`` automatically once the unload
    completes, so we only need to forward the unload to the sensor
    platform. The hub-wide registrations stored in ``hass.data[DOMAIN]``
    (WS commands, static paths, rail-cache schedule) are deliberately
    not torn down here — they were registered once for the lifetime of
    the HA process and re-registering on every reload would either
    error or leak listeners.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
