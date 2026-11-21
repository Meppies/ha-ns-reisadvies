"""Event entities for NS Reisadvies (v2.28.0).

One per route. Every time something happens to the route's focus trip
or its line, this entity records it — and the same thing is fired on
the event bus as ``ns_reisadvies_event`` for automations that prefer
listening there. In the automation editor it is a plain state trigger
on the entity, with the kind of event in its ``event_type`` attribute.

What it reports:

* ``platform_changed`` — the same train, another platform;
* ``delay_changed`` — the expected departure moved;
* ``cancelled`` — the train will not run;
* ``departed`` / ``arrived`` — from the train's position where NS
  reports one, from the clock where it does not;
* ``disruption_started`` / ``disruption_ended`` — on this route.

Old and new are only compared for the *same* trip, so the focus moving
on to the next train is never mistaken for a change.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SUBENTRY_TYPE_ROUTE
from .coordinator import NSUpdateCoordinator
from .route_entity import NSFocusEntity, route_ids
from .types import NSConfigEntry

PARALLEL_UPDATES = 0

EVENT_TYPES = [
    "platform_changed",
    "delay_changed",
    "cancelled",
    "departed",
    "arrived",
    "disruption_started",
    "disruption_ended",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """One event entity per route."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None or not runtime.coordinators:
        return False
    for subentry_id, subentry in (entry.subentries or {}).items():
        if subentry.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        coord = runtime.coordinators.get(subentry_id)
        if coord is None:
            continue
        unique_id, object_id, *_ = route_ids(subentry.data)
        entity = NSJourneyEvent(coord, route_unique_id=unique_id, route_object_id=object_id)
        try:
            async_add_entities([entity], config_subentry_id=subentry_id)
        except TypeError:
            async_add_entities([entity])
    return True


class NSJourneyEvent(NSFocusEntity, EventEntity):
    """What just happened to the route's train or line."""

    _platform_domain = "event"
    _attr_event_types = EVENT_TYPES

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        *,
        route_unique_id: str,
        route_object_id: str,
    ) -> None:
        super().__init__(
            coordinator, "journey",
            route_unique_id=route_unique_id, route_object_id=route_object_id,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_event_listener(self._on_event))

    @callback
    def _on_event(self, kind: str, data: dict[str, Any]) -> None:
        if kind not in EVENT_TYPES:
            return
        self._trigger_event(kind, data)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """An event entity's state is its last event, not the refresh."""
