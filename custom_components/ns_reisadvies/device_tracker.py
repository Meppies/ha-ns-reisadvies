"""Device tracker platform for NS Reisadvies (v2.18.0).

Publishes one GPS tracker per pinned favourite, so the train shows up on
Home Assistant's map and can drive zone triggers. Everything here is
gated on the hub option ``track_favourites_on_map``: with it off no
entities are created and the coordinator never polls in the background.

A favourite is a whole trip, which may involve several trains. The
tracker follows the leg the traveller is on at that moment, so at a
transfer the same entity moves to the next train rather than staying
with the one just left.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
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
from .coordinator import NSUpdateCoordinator, parse_iso
from .types import NSConfigEntry

_LOGGER = logging.getLogger(__name__)

# The coordinator does the fetching; the platform itself never polls.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up favourite trackers for every route subentry under the hub."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None or not runtime.coordinators:
        return False

    for subentry_id, subentry in (entry.subentries or {}).items():
        if subentry.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        coordinator = runtime.coordinators.get(subentry_id)
        if coordinator is None or not coordinator.track_favourites:
            continue

        from_st = subentry.data.get(CONF_FROM_STATION) or "?"
        to_st = subentry.data.get(CONF_TO_STATION) or "?"
        route_name = (subentry.data.get(CONF_ROUTE_NAME) or "").strip() or None
        # Same unique_id as the route's sensor, so the trackers land on
        # the device that already represents this route.
        if route_name:
            route_uid = f"{from_st}_{to_st}_{slugify(route_name)}".lower()
            route_slug = slugify(route_name)
        else:
            route_uid = f"{from_st}_{to_st}".lower()
            route_slug = f"{slugify(from_st)}_{slugify(to_st)}"

        manager = NSFavouriteTrackerManager(
            hass,
            coordinator,
            subentry_id=subentry_id,
            route_uid=route_uid,
            route_slug=route_slug,
            async_add_entities=async_add_entities,
        )
        entry.async_on_unload(manager.async_start())

    return True


class NSFavouriteTrackerManager:
    """Keeps one tracker entity per pinned favourite.

    Favourites come and go while Home Assistant runs — pinned from the
    card, unpinned by hand, or expired by the retention timer — so the
    entity set is maintained at runtime rather than fixed at setup.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: NSUpdateCoordinator,
        *,
        subentry_id: str,
        route_uid: str,
        route_slug: str,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._subentry_id = subentry_id
        self._route_uid = route_uid
        self._route_slug = route_slug
        self._async_add_entities = async_add_entities
        self._entities: dict[str, NSFavouriteTracker] = {}

    @callback
    def async_start(self) -> Any:
        """Create the current entities and follow changes. Returns an unsub."""
        unsub_coordinator = self.coordinator.async_add_listener(self._async_sync)
        unsub_favourites = self.coordinator.async_add_favourite_listener(self._async_sync)
        self._async_sync()

        @callback
        def _unsub() -> None:
            unsub_coordinator()
            unsub_favourites()

        return _unsub

    @callback
    def _async_sync(self) -> None:
        """Add trackers for new favourites, remove them for gone ones."""
        pinned = set(self.coordinator.tracked_trips)
        added: list[NSFavouriteTracker] = []
        for ctx in pinned - set(self._entities):
            tracker = NSFavouriteTracker(
                self.coordinator,
                ctx_recon=ctx,
                route_uid=self._route_uid,
                route_slug=self._route_slug,
            )
            self._entities[ctx] = tracker
            added.append(tracker)
        if added:
            try:
                self._async_add_entities(added, config_subentry_id=self._subentry_id)
            except TypeError:
                # HA < 2024.11 does not accept config_subentry_id.
                self._async_add_entities(added)

        for ctx in set(self._entities) - pinned:
            tracker = self._entities.pop(ctx)
            self.hass.async_create_task(tracker.async_remove(force_remove=True))


class NSFavouriteTracker(CoordinatorEntity[NSUpdateCoordinator], TrackerEntity):
    """GPS position of the train a pinned favourite is travelling on."""

    _attr_has_entity_name = True
    _attr_source_type = SourceType.GPS
    # Icon comes from icons.json (quality-scale rule icon-translations).
    # The per-favourite name is still set on the instance; _attr_name
    # takes precedence over any name translation for this key.
    _attr_translation_key = "favourite"

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        *,
        ctx_recon: str,
        route_uid: str,
        route_slug: str,
    ) -> None:
        super().__init__(coordinator)
        self._ctx = ctx_recon
        digest = hashlib.sha1(ctx_recon.encode("utf-8")).hexdigest()[:10]
        self._attr_unique_id = f"{route_uid}_fav_{digest}"

        # The name is fixed when the entity is created: a favourite is one
        # specific departure, so "Favourite 07:52 → Hilversum" stays true
        # for its whole life and the entity_id does not churn.
        label, slug = self._describe(coordinator, ctx_recon, digest)
        self._attr_name = label
        self._attr_suggested_object_id = f"ns_fav_{route_slug}_{slug}"

    @staticmethod
    def _describe(
        coordinator: NSUpdateCoordinator, ctx_recon: str, digest: str,
    ) -> tuple[str, str]:
        """Human label and entity_id slug for this favourite."""
        trip = coordinator.favourite_trip(ctx_recon)
        legs = [leg for leg in ((trip or {}).get("legs") or []) if isinstance(leg, dict)]
        if not legs:
            return f"NS favourite {digest[:6]}", digest[:6]
        origin = legs[0].get("origin") or {}
        destination = legs[-1].get("destination") or {}
        departure = parse_iso(origin.get("plannedDateTime"))
        clock = departure.strftime("%H:%M") if departure else ""
        to_name = destination.get("name") or ""
        label = " ".join(
            part for part in ("NS favourite", clock, f"→ {to_name}" if to_name else "")
            if part
        )
        slug = slugify(f"{clock}_{to_name}") or digest[:6]
        return label.strip(), slug

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
        return self.coordinator.favourite_positions.get(self._ctx) or {}

    @property
    def _position(self) -> dict[str, Any]:
        return self._record.get("position") or {}

    @property
    def available(self) -> bool:
        """Available while the favourite is pinned and the hub is healthy."""
        return bool(
            self.coordinator.last_update_success
            and self._ctx in self.coordinator.tracked_trips
        )

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
