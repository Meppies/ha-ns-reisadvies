"""NS Reisadvies sensor platform.

v2.9.0 layout:

* One DataUpdateCoordinator per route subentry, owned by the hub.
* One sensor per route. ``has_entity_name = True`` plus a translation
  key (``trips``) so the entity name is rendered as
  "<device name> <localised entity name>" — Bronze quality-scale rule
  ``has-entity-name``.
* Per-route DeviceInfo so each route is its own logical device under
  the hub. Required for the Gold ``devices`` rule, but already wired
  here because it pairs with ``has-entity-name``.
* Coordinators are read from ``entry.runtime_data`` (Bronze rule
  ``runtime-data``).

Unique IDs use ``f"{from}_{to}".lower()`` so they remain stable across
HA restarts and across the v1→v2→v3 migration (the entity registry was
rewritten in async_migrate_entry to point at this id).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)
from .coordinator import NSUpdateCoordinator
from .types import NSConfigEntry

_LOGGER = logging.getLogger(__name__)

# Quality-scale rule ``parallel-updates``: every entity already has its
# own coordinator that does the actual fetching, so the platform itself
# performs no parallel work — the value is informational here.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up sensors for every route subentry under the hub."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None or not runtime.coordinators:
        raise ConfigEntryNotReady("Waiting for NS Reisadvies hub")

    # Group sensors by subentry so we can pass config_subentry_id per add call
    by_subentry: dict[str, list[NSReisadviesSensor]] = {}
    for subentry_id, subentry in (entry.subentries or {}).items():
        if subentry.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        coord = runtime.coordinators.get(subentry_id)
        if coord is None:
            continue
        from_st = subentry.data.get(CONF_FROM_STATION) or "?"
        to_st = subentry.data.get(CONF_TO_STATION) or "?"
        # Custom route name (v2.15.0) — when supplied, used as the basis
        # for both the sensor's friendly name and its entity_id slug.
        route_name = (subentry.data.get(CONF_ROUTE_NAME) or "").strip() or None
        # unique_id mirrors the subentry's unique_id so existing entity
        # registry entries from v2.13.x / v2.14.x continue to match
        # for unnamed routes; named routes get their slug appended.
        if route_name:
            unique_id = f"{from_st}_{to_st}_{slugify(route_name)}".lower()
            # Short, readable entity_id derived from the name only:
            # `sensor.ns_werk` rather than `sensor.ns_hilversum_duivendrecht_werk`.
            suggested = f"ns_{slugify(route_name)}"
        else:
            unique_id = f"{from_st}_{to_st}".lower()
            suggested = f"ns_{slugify(from_st)}_{slugify(to_st)}"
        by_subentry.setdefault(subentry_id, []).append(
            NSReisadviesSensor(
                coord,
                from_station=from_st,
                to_station=to_st,
                route_name=route_name,
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


class NSReisadviesSensor(CoordinatorEntity[NSUpdateCoordinator], SensorEntity):
    """Sensor entity exposing NS travel advice for a configured route."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    # No _attr_name is the canonical "use the device name verbatim as
    # the entity friendly name" pattern when ``has_entity_name=True``.
    # The friendly name a user sees is therefore exactly the route
    # name (e.g. "Hilversum → Duivendrecht").
    _attr_name = None
    # ``translation_key`` is set so ``icons.json`` can map the entity
    # to ``mdi:train`` and so the entity is groupable for the Gold
    # ``entity-translations`` rule. The user-visible name still comes
    # from the device, not from translations.
    _attr_translation_key = "trips"
    # Recorder integration: don't persist the heavy `trips` JSON blob
    # in long-term state history. The full trips list (with legs,
    # stops, composition) easily exceeds Recorder's 16 384-byte
    # attribute size limit and would otherwise be silently dropped on
    # every state change with a noisy log warning. The Lovelace card
    # always reads the live state, so excluding `trips` from history
    # has no visible impact.
    _unrecorded_attributes = frozenset({"trips"})

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        *,
        from_station: str,
        to_station: str,
        route_name: str | None = None,
        unique_id: str,
        suggested_object_id: str | None = None,
    ) -> None:
        """Initialise the sensor.

        ``unique_id`` is deliberately the same as the route subentry's
        unique_id (``f"{from}_{to}".lower()`` for unnamed routes,
        ``f"{from}_{to}_{slug(name)}".lower()`` for named ones) so
        existing entity_ids are preserved across migrations.

        ``route_name`` (v2.15.0): when supplied, becomes the device's
        ``name`` (and therefore the sensor's friendly name, because
        ``has_entity_name=True`` + ``_attr_name=None`` reuses the device
        name verbatim). When not supplied the device name falls back to
        the legacy ``"<from> → <to>"`` shape.
        """
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        if suggested_object_id:
            self._attr_suggested_object_id = suggested_object_id
        # DeviceInfo per route. The device name doubles as the entity
        # friendly name (because _attr_name = None + has_entity_name).
        device_name = (
            route_name if route_name else f"{from_station} → {to_station}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
            manufacturer="NS",
            model="NS Reisadvies route",
            entry_type=None,
        )
        # Stored for the Lovelace card to surface the custom name even
        # when HA strips it from the device for translation reasons.
        self._route_name = route_name
        self._from_station = from_station
        self._to_station = to_station

    @property
    def native_value(self) -> str:
        """Return the planned departure of the next trip, or a placeholder."""
        if self.coordinator.data:
            try:
                value = self.coordinator.data[0]["legs"][0]["origin"][
                    "plannedDateTime"
                ]
                return str(value) if value else "Data available"
            except (KeyError, IndexError, TypeError):
                return "Data available"
        return "No trips"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Surface trips, tracked favourites, and hub-wide flags.

        Hub-wide flags are exposed so the Lovelace card can decide
        whether to render the live-train-map icon and how fast to poll
        the live position, without needing to call extra services.
        """
        tracked = getattr(self.coordinator, "tracked_trips", {}) or {}
        if isinstance(tracked, dict):
            tracked_list = list(tracked.keys())
        else:
            tracked_list = list(tracked)

        # Read flags from the hub entry's runtime_data. We look the entry
        # up by domain — there is at most one (single_config_entry: true).
        live_train_map_enabled = False
        live_map_refresh_seconds = 10
        for entry in self.coordinator.hass.config_entries.async_entries(DOMAIN):
            runtime = getattr(entry, "runtime_data", None)
            if runtime is not None:
                live_train_map_enabled = runtime.live_train_map_enabled
                live_map_refresh_seconds = runtime.live_map_refresh_seconds
                break

        return {
            "trips": self.coordinator.data or [],
            "tracked_trips": tracked_list,
            "live_train_map_enabled": live_train_map_enabled,
            "live_map_refresh_seconds": live_map_refresh_seconds,
            # v2.15.0: surface the route's components so the Lovelace
            # card can render a custom heading for routes that have a
            # name. ``route_name`` is None when the user hasn't given
            # the route a custom name — the card falls back to the
            # "<from> → <to>" shape in that case.
            "route_name": self._route_name,
            "from_station": self._from_station,
            "to_station": self._to_station,
            # v2.16.0: how many calendar days ahead the trip-search
            # anchor lives. 0 = today, 1 = tomorrow, 2+ = day after.
            # Card uses this to render a "Morgen" / "+N dagen" /
            # "<weekday> <date>" badge so the user knows the trips on
            # screen aren't for today. ``target_date`` carries the
            # literal ISO date so the card can localise the human form.
            "target_day_offset": getattr(
                self.coordinator, "_target_day_offset", 0,
            ),
            "target_date": getattr(
                self.coordinator, "_target_date", None,
            ),
            # Surface the active per-route filter so the card can pick
            # the right badge wording: a specific-date pin gets the
            # literal date, a weekday-filter without today selected
            # gets "<weekday> <date>", a time-only filter rolling past
            # midnight gets "morgen" / "over N dagen".
            "filter_days": list(
                getattr(self.coordinator, "filter_days", []) or []
            ),
            "filter_date": (
                fd.isoformat()
                if (fd := getattr(self.coordinator, "filter_date", None))
                is not None
                else None
            ),
        }

    async def async_track_trip(self, ctx_recon: str) -> None:
        """Pin a trip as a favourite.

        Silver quality-scale rule ``action-exceptions``: surface
        validation failures via ``ServiceValidationError`` so HA shows
        a clean message in the UI instead of silently no-opping.

        Gold rule ``exception-translations``: the error is raised with
        a translation key (declared in ``strings.json`` under
        ``exceptions``) so the message can be localised by HA.
        """
        if not ctx_recon or not str(ctx_recon).strip():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="empty_ctx_recon",
            )
        if not hasattr(self.coordinator, "track_trip"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="coordinator_unavailable",
            )
        self.coordinator.track_trip(ctx_recon)
        self.async_write_ha_state()

    async def async_untrack_trip(self, ctx_recon: str) -> None:
        """Unpin a previously favourited trip."""
        if not ctx_recon or not str(ctx_recon).strip():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="empty_ctx_recon",
            )
        if not hasattr(self.coordinator, "untrack_trip"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="coordinator_unavailable",
            )
        self.coordinator.untrack_trip(ctx_recon)
        self.async_write_ha_state()
