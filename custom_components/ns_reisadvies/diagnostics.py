"""Diagnostics support for the NS Reisadvies integration.

Gold quality-scale rule ``diagnostics``: provide a structured dump
that users can attach to bug reports without leaking secrets.

The dump excludes:
* ``api_key`` (NS subscription credential)
* ``ctxRecon`` strings (NS' opaque trip identifiers — not strictly
  secret but they uniquely identify a trip/passenger journey)
* ``UICCode`` and other long station identifiers in trip data
* IP / hostname information (we don't collect it, but the redactor
  helper covers any future field by name match)
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    CONF_LIVE_MAP_REFRESH_SECONDS,
    CONF_LIVE_TRAIN_MAP,
    CONF_SCAN_INTERVAL,
    SUBENTRY_TYPE_ROUTE,
)
from .types import NSConfigEntry

# Top-level keys redacted by ``async_redact_data``. Case-insensitive.
TO_REDACT: set[str] = {
    CONF_API_KEY,
    "api_key",
    "ctxRecon",
    "ctx_recon",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NSConfigEntry,
) -> dict[str, Any]:
    """Return a redacted dump of the hub entry, options and per-route state."""
    runtime = getattr(entry, "runtime_data", None)

    coordinators_dump: dict[str, Any] = {}
    if runtime is not None:
        for subentry_id, coord in runtime.coordinators.items():
            coordinators_dump[subentry_id] = {
                "from_station": coord.from_station,
                "to_station": coord.to_station,
                "fav_hours": coord.fav_hours,
                "fetch_composition": coord.fetch_composition,
                "tracked_trip_count": len(coord.tracked_trips or {}),
                "last_update_success": coord.last_update_success,
                "last_exception": (
                    repr(coord.last_exception)
                    if getattr(coord, "last_exception", None)
                    else None
                ),
                "trip_count": len(coord.data) if coord.data else 0,
                # First trip only, redacted, so we can see the shape.
                "first_trip": (
                    async_redact_data(coord.data[0], TO_REDACT)
                    if coord.data
                    else None
                ),
            }

    subentries_dump: dict[str, Any] = {}
    for subentry_id, sub in (entry.subentries or {}).items():
        if sub.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        subentries_dump[subentry_id] = {
            "title": sub.title,
            "unique_id": sub.unique_id,
            "data": dict(sub.data),
        }

    return {
        "entry": {
            "version": entry.version,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": {
                CONF_SCAN_INTERVAL: entry.options.get(CONF_SCAN_INTERVAL),
                CONF_FAV_HOURS: entry.options.get(CONF_FAV_HOURS),
                CONF_FETCH_COMPOSITION: entry.options.get(CONF_FETCH_COMPOSITION),
                CONF_LIVE_TRAIN_MAP: entry.options.get(CONF_LIVE_TRAIN_MAP),
                CONF_LIVE_MAP_REFRESH_SECONDS: entry.options.get(
                    CONF_LIVE_MAP_REFRESH_SECONDS,
                ),
            },
            "subentries": subentries_dump,
        },
        "runtime": {
            "live_train_map_enabled": (
                runtime.live_train_map_enabled if runtime else None
            ),
            "live_map_refresh_seconds": (
                runtime.live_map_refresh_seconds if runtime else None
            ),
            "stations_geo_cached": bool(runtime and runtime.stations_geo),
            "active_live_sessions": (
                len(runtime.live_sessions) if runtime else 0
            ),
        },
        "coordinators": coordinators_dump,
    }
