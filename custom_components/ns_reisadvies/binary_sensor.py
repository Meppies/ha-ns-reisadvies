"""Binary sensors for NS Reisadvies (v2.28.0).

Yes-or-no facts an automation can use as a condition or a trigger as
they are: is my train cancelled, has my platform changed, is the train
standing at a station, is there trouble on my line. Each route gets
its own set, about its focus trip (a pinned favourite, else the next
departure); the installation gets one more for a national calamity.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SUBENTRY_TYPE_ROUTE
from .coordinator import NSUpdateCoordinator
from .route_entity import NSFocusEntity, route_ids
from .types import NSConfigEntry

# The coordinator does the fetching; the platform itself never polls.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NSFocusBinaryDescription(BinarySensorEntityDescription):
    """One yes-or-no about the focus trip, and where to read it."""

    value_fn: Callable[[NSUpdateCoordinator], bool | None]
    live: bool = False
    needs_disruptions: bool = False
    needs_travel_time: bool = False
    needs_composition: bool = False


def _focus(key: str) -> Callable[[NSUpdateCoordinator], bool | None]:
    def read(coordinator: NSUpdateCoordinator) -> bool | None:
        if not coordinator.focus:
            return None
        return bool(coordinator.focus.get(key))
    return read


def _live(key: str) -> Callable[[NSUpdateCoordinator], bool | None]:
    def read(coordinator: NSUpdateCoordinator) -> bool | None:
        if not coordinator.focus_live:
            return None
        return bool(coordinator.focus_live.get(key))
    return read


FOCUS_BINARY_SENSORS: tuple[NSFocusBinaryDescription, ...] = (
    NSFocusBinaryDescription(
        key="cancelled",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_focus("cancelled"),
    ),
    NSFocusBinaryDescription(
        key="platform_changed",
        value_fn=_focus("platform_changed"),
    ),
    NSFocusBinaryDescription(
        key="arrival_platform_changed",
        entity_registry_enabled_default=False,
        value_fn=_focus("arrival_platform_changed"),
    ),
    NSFocusBinaryDescription(
        key="time_to_leave",
        needs_travel_time=True,
        value_fn=_focus("time_to_leave"),
    ),
    NSFocusBinaryDescription(
        key="transfer_at_risk",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_focus("transfer_at_risk"),
    ),
    NSFocusBinaryDescription(
        key="shorter_train",
        device_class=BinarySensorDeviceClass.PROBLEM,
        needs_composition=True,
        value_fn=lambda c: (
            None if not c.focus or c.focus.get("shorter_train") is None
            else bool(c.focus.get("shorter_train"))
        ),
    ),
    NSFocusBinaryDescription(
        key="delayed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        value_fn=lambda c: (
            None if not c.focus else bool((c.focus.get("departure_delay") or 0) > 0)
        ),
    ),
    NSFocusBinaryDescription(
        key="at_station",
        live=True,
        value_fn=_live("at_station"),
    ),
    NSFocusBinaryDescription(
        key="moving",
        live=True,
        device_class=BinarySensorDeviceClass.MOVING,
        entity_registry_enabled_default=False,
        value_fn=_live("moving"),
    ),
    NSFocusBinaryDescription(
        key="route_disruption",
        device_class=BinarySensorDeviceClass.PROBLEM,
        needs_disruptions=True,
        value_fn=lambda c: bool(c.route_disruptions),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """One set per route, and one national calamity sensor."""
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
        entities = [
            NSFocusBinarySensor(
                coord, description,
                route_unique_id=unique_id, route_object_id=object_id,
            )
            for description in FOCUS_BINARY_SENSORS
            if (coord.watch_live or not description.live)
            and (coord.watch_disruptions or not description.needs_disruptions)
            and (coord.minutes_to_station > 0 or not description.needs_travel_time)
            and (coord.fetch_composition or not description.needs_composition)
        ]
        try:
            async_add_entities(entities, config_subentry_id=subentry_id)
        except TypeError:
            # HA < 2024.11 does not accept config_subentry_id.
            async_add_entities(entities)

    first = next(iter(runtime.coordinators.values()), None)
    if first is not None and first.watch_disruptions:
        async_add_entities([NSCalamityBinarySensor(first, hub_id=entry.entry_id)])
    return True


class NSFocusBinarySensor(NSFocusEntity, BinarySensorEntity):
    """A yes-or-no about the route's focus trip."""

    _platform_domain = "binary_sensor"
    entity_description: NSFocusBinaryDescription

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        description: NSFocusBinaryDescription,
        *,
        route_unique_id: str,
        route_object_id: str,
    ) -> None:
        self._live = description.live
        super().__init__(
            coordinator, description.key,
            route_unique_id=route_unique_id, route_object_id=route_object_id,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Just enough to say what it is about in a notification."""
        focus = self.focus
        if self._key == "platform_changed" and focus:
            return {
                "platform": focus.get("platform"),
                "planned_platform": focus.get("planned_platform"),
                "train": focus.get("train"),
            }
        if self._key == "at_station":
            return {"station": self.live.get("current_station")}
        if self._key == "transfer_at_risk" and focus:
            risky = [t for t in focus.get("transfer_list") or [] if t.get("at_risk")]
            first = risky[0] if risky else {}
            return {
                "station": first.get("station"),
                "minutes_left": first.get("margin"),
                "planned_minutes": first.get("planned_margin"),
                "next_train": first.get("next_train"),
                "departure_platform": first.get("departure_platform"),
            }
        if self._key == "shorter_train" and focus:
            return {
                "carriages": focus.get("carriages"),
                "planned_carriages": focus.get("planned_carriages"),
                "train": focus.get("train"),
            }
        if self._key == "time_to_leave" and focus:
            return {
                "leave_at": focus["leave_at"].isoformat() if focus.get("leave_at") else None,
                "minutes_to_station": self.coordinator.minutes_to_station,
                "train": focus.get("train"),
            }
        if self._key == "route_disruption":
            items = self.coordinator.route_disruptions
            return {
                "count": len(items),
                "title": items[0].get("title") if items else None,
                "summary": items[0].get("summary") if items else None,
            }
        return None


class NSCalamityBinarySensor(CoordinatorEntity[NSUpdateCoordinator], BinarySensorEntity):
    """Whether NS has a calamity announcement out, anywhere.

    Calamities are rare and national — a power failure, a nationwide
    stop — which is exactly when a household wants to be told whatever
    line they normally take.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "calamity"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: NSUpdateCoordinator, *, hub_id: str) -> None:
        super().__init__(coordinator)
        self.entity_id = "binary_sensor.ns_calamity"
        self._attr_unique_id = f"{hub_id}_calamity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub_id}_hub")},
            name="NS Reisadvies",
            manufacturer="NS",
        )

    @property
    def _calamities(self) -> list[dict[str, Any]]:
        return [d for d in self.coordinator.disruptions if d.get("type") == "CALAMITY"]

    @property
    def is_on(self) -> bool:
        return bool(self._calamities)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self._calamities
        return {
            "count": len(items),
            "title": items[0].get("title") if items else None,
            "summary": items[0].get("summary") if items else None,
            "url": items[0].get("url") if items else None,
        }
