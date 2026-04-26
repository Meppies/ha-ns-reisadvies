"""NS Reisadvies sensor + track-services."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        raise ConfigEntryNotReady("Wachten op NS Coordinator")

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NSReisadviesSensor(coordinator, entry.title, entry.entry_id)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "track_trip", {"ctx_recon": cv.string}, "async_track_trip"
    )
    platform.async_register_entity_service(
        "untrack_trip", {"ctx_recon": cv.string}, "async_untrack_trip"
    )
    return True


class NSReisadviesSensor(CoordinatorEntity, SensorEntity):
    _attr_should_poll = False

    def __init__(self, coordinator, name: str, unique_id: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def native_value(self):
        if self.coordinator.data:
            try:
                return self.coordinator.data[0]["legs"][0]["origin"]["plannedDateTime"]
            except (KeyError, IndexError, TypeError):
                return "Data aanwezig"
        return "Geen ritten"

    @property
    def extra_state_attributes(self):
        tracked = getattr(self.coordinator, "tracked_trips", {}) or {}
        # Backwards compatible naar de card: blijft een lijst van ctxRecons
        if isinstance(tracked, dict):
            tracked_list = list(tracked.keys())
        else:
            tracked_list = list(tracked)
        return {
            "trips": self.coordinator.data or [],
            "tracked_trips": tracked_list,
        }

    async def async_track_trip(self, ctx_recon: str) -> None:
        if hasattr(self.coordinator, "track_trip"):
            self.coordinator.track_trip(ctx_recon)
            self.async_write_ha_state()

    async def async_untrack_trip(self, ctx_recon: str) -> None:
        if hasattr(self.coordinator, "untrack_trip"):
            self.coordinator.untrack_trip(ctx_recon)
            self.async_write_ha_state()
