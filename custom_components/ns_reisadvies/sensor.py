"""NS Reisadvies sensors and tracking services.

v2: one sensor per route subentry under the hub. The unique_id is
`f"{from}_{to}".lower()` so it remains stable across HA restarts and
across the v1→v2 migration (the entity registry is rewritten in
async_migrate_entry to point at this id).
"""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, SUBENTRY_TYPE_ROUTE, CONF_FROM_STATION, CONF_TO_STATION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up sensors for every route subentry under the hub."""
    coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinators is None:
        raise ConfigEntryNotReady("Waiting for NS Reisadvies hub")

    # Group sensors by subentry so we can pass config_subentry_id per add call
    by_subentry: dict[str, list[NSReisadviesSensor]] = {}
    for subentry_id, subentry in (entry.subentries or {}).items():
        if subentry.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        coord = coordinators.get(subentry_id)
        if coord is None:
            continue
        from_st = subentry.data.get(CONF_FROM_STATION) or "?"
        to_st = subentry.data.get(CONF_TO_STATION) or "?"
        unique_id = f"{from_st}_{to_st}".lower()
        # Suggested entity_id slug: ns_<from>_<to> with HA slugify (handles spaces,
        # diacritics, etc). Existing entities keep their registry entity_id; this
        # only kicks in for newly registered routes.
        suggested = f"ns_{slugify(from_st)}_{slugify(to_st)}"
        by_subentry.setdefault(subentry_id, []).append(
            NSReisadviesSensor(
                coord,
                name=subentry.title or f"NS {from_st} -> {to_st}",
                unique_id=unique_id,
                suggested_object_id=suggested,
            )
        )

    for subentry_id, sensors in by_subentry.items():
        try:
            async_add_entities(sensors, config_subentry_id=subentry_id)
        except TypeError:
            # HA < 2024.11 does not accept config_subentry_id on async_add_entities.
            async_add_entities(sensors)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "track_trip", {"ctx_recon": cv.string}, "async_track_trip"
    )
    platform.async_register_entity_service(
        "untrack_trip", {"ctx_recon": cv.string}, "async_untrack_trip"
    )
    return True


class NSReisadviesSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity exposing NS travel advice for a configured route."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        name: str,
        unique_id: str,
        suggested_object_id: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        if suggested_object_id:
            self._attr_suggested_object_id = suggested_object_id

    @property
    def native_value(self):
        if self.coordinator.data:
            try:
                return self.coordinator.data[0]["legs"][0]["origin"]["plannedDateTime"]
            except (KeyError, IndexError, TypeError):
                return "Data available"
        return "No trips"

    @property
    def extra_state_attributes(self):
        tracked = getattr(self.coordinator, "tracked_trips", {}) or {}
        if isinstance(tracked, dict):
            tracked_list = list(tracked.keys())
        else:
            tracked_list = list(tracked)
        # Hub-wide flags exposed so the Lovelace card can decide whether
        # to render optional UI (e.g. the live train map icon) without
        # having to call extra services.
        bucket = self.coordinator.hass.data.get(DOMAIN, {})
        return {
            "trips": self.coordinator.data or [],
            "tracked_trips": tracked_list,
            "live_train_map_enabled": bool(
                bucket.get("_live_train_map_enabled", False)
            ),
            "live_map_refresh_seconds": int(
                bucket.get("_live_map_refresh_seconds", 10)
            ),
        }

    async def async_track_trip(self, ctx_recon: str) -> None:
        if hasattr(self.coordinator, "track_trip"):
            self.coordinator.track_trip(ctx_recon)
            self.async_write_ha_state()

    async def async_untrack_trip(self, ctx_recon: str) -> None:
        if hasattr(self.coordinator, "untrack_trip"):
            self.coordinator.untrack_trip(ctx_recon)
            self.async_write_ha_state()
