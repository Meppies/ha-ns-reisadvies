"""Device tracker platform for NS Reisadvies (v2.18.1).

Publishes one GPS tracker per route, which follows whichever pinned
favourite on that route is being travelled right now. Everything here is
gated on the hub option ``track_favourites_on_map``: with it off no
entities are created and the coordinator never polls in the background.

One entity per route rather than one per favourite (v2.18.0's design):
a favourite is a single dated departure, so an entity keyed on it is
born in the morning and gone by the evening, leaving a stale registry
entry behind and a different ``entity_id`` every day. Zone automations
need a name that still means something tomorrow, so the route is the
stable thing to name the entity after, and the trip it follows is an
attribute.

A favourite is a whole trip, which may involve several trains. The
tracker follows the leg the traveller is on at that moment, so at a
transfer it moves to the next train rather than staying with the one
just left.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
    SUBENTRY_TYPE_ROUTE,
)
from .coordinator import NSUpdateCoordinator
from .types import NSConfigEntry

_LOGGER = logging.getLogger(__name__)

# The coordinator does the fetching; the platform itself never polls.
PARALLEL_UPDATES = 0

# v2.18.0 gave every pinned favourite its own entity, keyed on a digest
# of its ctxRecon. Those entities cannot come back -- the trips they
# named have departed -- so their registry entries are removed on
# upgrade instead of lingering as `unavailable`.
_LEGACY_UNIQUE_ID = re.compile(r"_fav_[0-9a-f]{10}$")


def route_identity(data: Mapping[str, Any]) -> tuple[str, str, str]:
    """Stable (unique_id stem, entity_id slug, human label) for a route."""
    from_st = data.get(CONF_FROM_STATION) or "?"
    to_st = data.get(CONF_TO_STATION) or "?"
    route_name = (data.get(CONF_ROUTE_NAME) or "").strip() or None
    if route_name:
        # Same stem as the route's sensor, so the tracker sorts with it.
        return (
            f"{from_st}_{to_st}_{slugify(route_name)}".lower(),
            slugify(route_name),
            route_name,
        )
    return (
        f"{from_st}_{to_st}".lower(),
        f"{slugify(from_st)}_{slugify(to_st)}",
        f"{from_st} → {to_st}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up one favourite tracker per route subentry under the hub."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None or not runtime.coordinators:
        return False

    _async_drop_legacy_entities(hass, entry)

    for subentry_id, subentry in (entry.subentries or {}).items():
        if subentry.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        coordinator = runtime.coordinators.get(subentry_id)
        if coordinator is None or not coordinator.track_favourites:
            continue

        route_uid, route_slug, route_label = route_identity(subentry.data)
        tracker = NSFavouriteTracker(
            coordinator,
            route_uid=route_uid,
            route_slug=route_slug,
            route_label=route_label,
        )
        try:
            async_add_entities([tracker], config_subentry_id=subentry_id)
        except TypeError:
            # HA < 2024.11 does not accept config_subentry_id.
            async_add_entities([tracker])

    return True


@callback
def _async_drop_legacy_entities(hass: HomeAssistant, entry: NSConfigEntry) -> None:
    """Remove the per-favourite trackers v2.18.0 created."""
    registry = er.async_get(hass)
    entry_id = getattr(entry, "entry_id", None)
    if not entry_id:
        return
    for item in list(er.async_entries_for_config_entry(registry, entry_id)):
        if item.domain == "device_tracker" and _LEGACY_UNIQUE_ID.search(item.unique_id):
            _LOGGER.debug("Removing superseded favourite tracker %s", item.entity_id)
            registry.async_remove(item.entity_id)


class NSFavouriteTracker(CoordinatorEntity[NSUpdateCoordinator], TrackerEntity):
    """GPS position of the train a pinned favourite is travelling on."""

    _attr_has_entity_name = True
    _attr_source_type = SourceType.GPS
    # Icon comes from icons.json (quality-scale rule icon-translations).
    # The per-route name is still set on the instance; _attr_name takes
    # precedence over any name translation for this key.
    _attr_translation_key = "favourite"

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        *,
        route_uid: str,
        route_slug: str,
        route_label: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{route_uid}_favourite"
        self._attr_name = f"NS favourite {route_label}"
        self._attr_suggested_object_id = f"ns_favourite_{route_slug}"

    async def async_added_to_hass(self) -> None:
        """Follow position refreshes as well as coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_favourite_listener(
                self.async_write_ha_state,
            )
        )

    @property
    def entity_category(self) -> EntityCategory | None:
        """Primary, not diagnostic.

        ``BaseTrackerEntity`` defaults every tracker to the diagnostic
        category, which tucks it away in the UI. A train position is the
        point of this entity, so it belongs with the primary ones. The
        class attribute is typed as non-optional upstream, hence the
        property override.
        """
        return None

    @property
    def _record(self) -> dict[str, Any]:
        return self.coordinator.current_favourite() or {}

    @property
    def _position(self) -> dict[str, Any]:
        return self._record.get("position") or {}

    @property
    def available(self) -> bool:
        """Available whenever the hub is healthy.

        Deliberately not tied to whether a favourite is pinned: an
        automation that triggers on this entity should keep working
        between trips rather than going unavailable every evening.
        """
        return bool(self.coordinator.last_update_success)

    @property
    def latitude(self) -> float | None:
        value = self._position.get("lat")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def longitude(self) -> float | None:
        value = self._position.get("lng")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def location_accuracy(self) -> int:
        """Metres. The OBIS feed is good to roughly a train length."""
        return 50 if self._position else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Everything an automation might want to branch on."""
        record = self._record
        position = self._position
        product = record.get("product") or {}
        attributes: dict[str, Any] = {
            "phase": record.get("phase"),
            "en_route": bool(record.get("active")),
            "pinned_favourites": len(self.coordinator.tracked_trips),
            "favourite_ctx": record.get("ctx_recon"),
            "train_number": record.get("train_number") or None,
            "train_type": product.get("shortCategoryName") or product.get("displayName"),
            "operator": product.get("operatorName"),
            "leg_origin": record.get("origin"),
            "leg_destination": record.get("destination"),
            "direction": record.get("direction"),
            "planned_departure": record.get("departure"),
            "planned_arrival": record.get("arrival"),
            "trip_origin": record.get("trip_origin"),
            "trip_destination": record.get("trip_destination"),
            "position_updated": record.get("updated_at"),
        }
        if position:
            attributes["speed"] = position.get("speed")
            attributes["heading"] = position.get("heading")
            attributes["near_station"] = position.get("station_name")
            attributes["position_source"] = position.get("source")
            attributes["position_fresh"] = bool(record.get("position_fresh"))
        return attributes
