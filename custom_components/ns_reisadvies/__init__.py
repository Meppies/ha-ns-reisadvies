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

import logging
import os
import secrets
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components import lovelace, websocket_api
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later
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
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
    DEFAULT_FETCH_COMPOSITION,
    DEFAULT_LIVE_TRAIN_MAP,
)
from .coordinator import NSUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CARD_URL = "/ns_reisadvies/ns-reisadvies-card.js"


# ---------------------------------------------------------------------------
# Migration: v1 multi-entry → v2 single hub + subentries.
# ---------------------------------------------------------------------------


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Lift legacy flat entries into the hub+subentries layout."""
    if entry.version >= CONFIG_ENTRY_VERSION:
        return True

    _LOGGER.info("Migrating NS Reisadvies entry %s from v%s to v%s",
                 entry.entry_id, entry.version, CONFIG_ENTRY_VERSION)

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the hub: build a coordinator per route subentry."""
    hass.data.setdefault(DOMAIN, {})

    # Self-heal: if a previous (failed) migration left the hub without
    # subentries, try to rebuild them from the per-route Store files.
    await _recover_subentries_from_storage(hass, entry)

    # Hub-wide config
    api_key = entry.data.get(CONF_API_KEY)
    scan_interval = int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    fav_hours = int(entry.data.get(CONF_FAV_HOURS, DEFAULT_FAV_HOURS))
    fetch_composition = bool(entry.data.get(CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION))
    live_train_map = bool(entry.data.get(CONF_LIVE_TRAIN_MAP, DEFAULT_LIVE_TRAIN_MAP))

    # Make live_train_map flag visible to the sensor platform via hass.data
    # so it can expose it in extra_state_attributes (used by the card to
    # decide whether to render the map icon).
    hass.data[DOMAIN]["_live_train_map_enabled"] = live_train_map

    # Coordinator per subentry. We store them in hass.data keyed by
    # subentry_id so the sensor platform can pick them up.
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

    hass.data[DOMAIN][entry.entry_id] = coordinators

    # Backfill: link existing entities to their subentry by unique_id.
    # Entities created before HA's subentry-aware async_add_entities have
    # config_subentry_id=None; this rewrites them so HA tracks the link
    # and the entity is shown under the right subentry in the UI.
    _backfill_entity_subentries(hass, entry)

    # WebSocket commands for the live-train map. Registered once per HA.
    if "_ws_registered" not in hass.data[DOMAIN]:
        websocket_api.async_register_command(hass, _ws_track_train_start)
        websocket_api.async_register_command(hass, _ws_track_train_poll)
        websocket_api.async_register_command(hass, _ws_track_train_stop)
        hass.data[DOMAIN]["_ws_registered"] = True

    # Static path + Lovelace card auto-registration (one-shot per HA).
    if "static_paths_registered" not in hass.data[DOMAIN]:
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
# Session shape (hass.data[DOMAIN]["_live_sessions"][sid]):
#   {
#     "train_entity_id": "device_tracker.ns_reisadvies_train_<sid>",
#     "stop_entity_ids": ["device_tracker.ns_reisadvies_stop_<sid>_0", ...],
#     "train_number": "5710",
#     "cleanup": <CALLBACK>,
#   }


def _live_sessions(hass: HomeAssistant) -> dict[str, dict]:
    return hass.data.setdefault(DOMAIN, {}).setdefault("_live_sessions", {})


def _any_coordinator(hass: HomeAssistant) -> NSUpdateCoordinator | None:
    """Return any per-route coordinator (they all share the api_key)."""
    bucket = hass.data.get(DOMAIN, {})
    for value in bucket.values():
        if isinstance(value, dict):
            for coord in value.values():
                if isinstance(coord, NSUpdateCoordinator):
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
    def _fire(_now):  # noqa: ANN001
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

    # Position is computed client-side from leg.stops + wall clock —
    # see _interpolateTrainPos() in the card. NS' /v1/trein/{ritnummer}
    # silently returns a different physical train when ritnummers are
    # reused (and the dateTime anchor turned out not to disambiguate),
    # so calling it here just feeds the card a misleading fallback.
    # We keep `train_position: None` and let the card interpolate.
    pos = None

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

    # Same as on start: don't fetch /v1/trein at all — the card derives
    # position client-side from leg.stops + wall clock.
    pos = None
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the hub."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
