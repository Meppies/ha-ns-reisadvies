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
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
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
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)
from ._departure import next_departure, summary_line
from ._dienstkaartje import current_leg, trains_of
from .coordinator import NSUpdateCoordinator
from .types import NSConfigEntry

_LOGGER = logging.getLogger(__name__)

# Dienstkaartje publishes Dutch wall-clock times without a zone.
_DUTCH_CLOCK = ZoneInfo("Europe/Amsterdam")

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
    by_subentry: dict[str, list[SensorEntity]] = {}
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
        # v2.20.0: the delay and next-train sensors sit on the same route
        # device and read the same (filtered) coordinator data.
        by_subentry[subentry_id].extend(
            [
                NSReisadviesDelaySensor(
                    coord, route_unique_id=unique_id, route_object_id=suggested,
                ),
                NSReisadviesNextTrainSensor(
                    coord, route_unique_id=unique_id, route_object_id=suggested,
                ),
            ]
        )
        # v2.25.0: what NS says is wrong with the line this route uses.
        if coord.watch_disruptions:
            by_subentry[subentry_id].append(
                NSReisadviesRouteDisruptionSensor(
                    coord, route_unique_id=unique_id, route_object_id=suggested,
                )
            )

    for subentry_id, sensors in by_subentry.items():
        try:
            async_add_entities(sensors, config_subentry_id=subentry_id)
        except TypeError:
            # HA < 2024.11 does not accept config_subentry_id on async_add_entities.
            async_add_entities(sensors)

    # One national disruption sensor for the whole installation. It
    # belongs to the hub, so it is added without a subentry, and any
    # coordinator will do: they all read the same shared feed.
    first_coord = next(iter(runtime.coordinators.values()), None)
    if first_coord is not None and first_coord.watch_disruptions:
        async_add_entities(
            [NSReisadviesNationalDisruptionSensor(
                first_coord, hub_id=entry.entry_id,
            )]
        )

    # v2.27.0: one sensor per person followed on Dienstkaartje. These
    # belong to the hub as well — a colleague is not a property of a
    # route — and exist only while the option is on and they are named.
    if first_coord is not None and first_coord.watch_dienstkaartje:
        followed = [
            NSReisadviesStaffSensor(first_coord, hub_id=entry.entry_id, username=name)
            for name in first_coord.dienstkaartje_users
        ]
        if followed:
            async_add_entities(followed)

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
            # v2.25.0: set the entity_id outright. Home Assistant does
            # not read ``_attr_suggested_object_id`` — it derives the
            # id from the device name and the *translated* entity name,
            # which is how a Dutch instance ended up with
            # sensor.<route>_vertraging. Setting entity_id is the
            # supported way for an integration to propose one, and the
            # registry still wins for an entity that already exists.
            self._attr_suggested_object_id = suggested_object_id
            self.entity_id = f"sensor.{suggested_object_id}"
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
            "filter_train_types": list(
                getattr(self.coordinator, "filter_train_types", []) or []
            ),
            # What this route actually runs, before filtering — the
            # place to look up the code of a regional operator.
            "available_train_types": list(
                getattr(self.coordinator, "available_train_types", []) or []
            ),
            "filter_date": (
                fd.isoformat()
                if (fd := getattr(self.coordinator, "filter_date", None))
                is not None
                else None
            ),
            # v2.16.18: machine-readable categorisation of the most
            # recent refresh failure. Power users can read this in
            # Developer Tools → States to know exactly why the sensor
            # is unavailable without scraping the HA logs. The card can
            # also use it to render a small badge ("auth issue —
            # reauthenticate") next to the route name.
            #
            # Values: "none" / "auth" / "quota_exceeded" /
            #         "api_unavailable" / "network"
            "last_error_category": getattr(
                self.coordinator, "_last_error_category", "none",
            ),
            # Epoch seconds the current outage started — None when
            # healthy. Lets a card render "down for X minutes" badges.
            "outage_started_at": getattr(
                self.coordinator, "_outage_started_at", None,
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


class _NSDepartureSensorBase(CoordinatorEntity[NSUpdateCoordinator], SensorEntity):
    """Shared base: a sensor on the route device about its next departure."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _unique_id_suffix: str = ""

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        *,
        route_unique_id: str,
        route_object_id: str | None = None,
    ) -> None:
        """Attach to the route's device (identifiers only, so it merges).

        ``route_object_id`` is the trips sensor's suggested entity_id, so
        these sensors sit beside it as ``sensor.ns_werk_delay`` rather
        than taking an id from the translated entity name, which would
        differ per Home Assistant language.
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{route_unique_id}_{self._unique_id_suffix}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, route_unique_id)})
        if route_object_id:
            object_id = f"{route_object_id}_{self._unique_id_suffix}"
            self._attr_suggested_object_id = object_id
            self.entity_id = f"sensor.{object_id}"

    @property
    def _departure(self) -> dict[str, Any] | None:
        return next_departure(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Train, planned/expected time, track and status of the next trip."""
        info = self._departure
        if info is None:
            return {}
        return {key: value for key, value in info.items() if key != "delay"}


def _disruption_attributes(items: list[dict[str, Any]]) -> dict[str, Any]:
    """What an automation needs to say something useful out loud.

    The titles and the first summary are what a notification reads
    from; the ids are there so an automation can tell a new disruption
    from one it has already announced.
    """
    first = items[0] if items else None
    return {
        "titles": [item["title"] for item in items],
        "types": sorted({item["type"] for item in items}),
        "ids": [item["id"] for item in items],
        "summary": first["summary"] if first else None,
        "title": first["title"] if first else None,
        "type": first["type"] if first else None,
        "cause": first.get("cause") if first else None,
        "expected_until": first.get("expected_until") if first else None,
        "advices": first.get("advices") if first else [],
        "stations": (
            [station["name"] for station in first.get("stations") or []]
            if first else []
        ),
        "worst_impact": max(
            (int(item["impact"]) for item in items
             if isinstance(item.get("impact"), (int, float))),
            default=None,
        ),
        "disruptions": items,
    }


class NSReisadviesRouteDisruptionSensor(
    CoordinatorEntity[NSUpdateCoordinator], SensorEntity,
):
    """How many NS disruptions touch this route right now.

    A disruption counts when one of the stations on the stretch NS
    names is a station this route's journeys call at or pass through —
    not just the two ends, because the trouble is usually in between.
    A calamity, which NS publishes without a stretch, always counts.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "disruptions"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        *,
        route_unique_id: str,
        route_object_id: str | None = None,
    ) -> None:
        """Sit on the route's device, beside its trips sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{route_unique_id}_disruptions"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, route_unique_id)})
        if route_object_id:
            self._attr_suggested_object_id = f"{route_object_id}_disruptions"
            self.entity_id = f"sensor.{route_object_id}_disruptions"

    @property
    def native_value(self) -> int:
        """The number of disruptions on this route."""
        return len(self.coordinator.route_disruptions)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Titles, cause, advice and the affected stations."""
        return _disruption_attributes(self.coordinator.route_disruptions)


class NSReisadviesNationalDisruptionSensor(
    CoordinatorEntity[NSUpdateCoordinator], SensorEntity,
):
    """Every disruption NS is publishing, wherever it is.

    One per installation rather than one per route, for a dashboard
    badge or a notification about the country as a whole.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "national_disruptions"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_object_id = "ns_disruptions"

    def __init__(self, coordinator: NSUpdateCoordinator, *, hub_id: str) -> None:
        """Belong to the hub, not to any one route."""
        super().__init__(coordinator)
        self.entity_id = "sensor.ns_disruptions"
        self._attr_unique_id = f"{hub_id}_national_disruptions"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub_id}_hub")},
            name="NS Reisadvies",
            manufacturer="NS",
        )

    @property
    def native_value(self) -> int:
        """The number of active disruptions in the country."""
        return len(self.coordinator.disruptions)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The same detail as the route sensor, nationally."""
        items = self.coordinator.disruptions
        attributes = _disruption_attributes(items)
        for kind in ("DISRUPTION", "MAINTENANCE", "CALAMITY"):
            attributes[kind.lower()] = sum(
                1 for item in items if item["type"] == kind
            )
        return attributes


class NSReisadviesStaffSensor(CoordinatorEntity[NSUpdateCoordinator], SensorEntity):
    """Which train someone followed on Dienstkaartje is working.

    The state is the train number they are on at this moment, ``idle``
    while they are on a shift but between trains, and ``off_duty``
    when there is no shift — so an automation can say "when dad's
    train is 1537" or simply "when dad starts work".

    Everything here comes from that person's own profile and goes no
    further than it does: with their train numbers hidden the sensor
    says nothing about trains, and with their times hidden it carries
    no times.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "staff_shift"

    def __init__(
        self, coordinator: NSUpdateCoordinator, *, hub_id: str, username: str,
    ) -> None:
        super().__init__(coordinator)
        self._username = username
        slug = slugify(username)
        self._attr_unique_id = f"{hub_id}_dienstkaartje_{slug}"
        self._attr_name = f"Dienstkaartje {username}"
        self.entity_id = f"sensor.ns_dienstkaartje_{slug}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub_id}_hub")},
            name="NS Reisadvies",
            manufacturer="NS",
        )

    @property
    def _profile(self) -> dict[str, Any] | None:
        for profile in self.coordinator.dienstkaartje:
            if profile["username"].casefold() == self._username.casefold():
                return profile
        return None

    @property
    def available(self) -> bool:
        """Available whenever the hub is: a quiet day is not a fault."""
        return bool(self.coordinator.last_update_success)

    @property
    def native_value(self) -> str:
        profile = self._profile
        if not profile or not profile.get("on_shift"):
            return "off_duty"
        # Dienstkaartje writes Dutch wall clock without a zone, so the
        # comparison is made in that zone whatever Home Assistant is
        # set to: an installation in Berlin or London must not think
        # the shift is an hour out.
        now = dt_util.utcnow().astimezone(_DUTCH_CLOCK).strftime("%Y-%m-%d %H:%M:%S")
        leg = current_leg(profile, now) if profile.get("shows_train_numbers") else None
        if leg and leg.get("service_number"):
            return str(leg["service_number"])
        # On a shift, but between trains — or working a shift whose
        # train numbers its owner keeps to themselves.
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        profile = self._profile
        if not profile:
            return {"username": self._username, "on_shift": False}
        shows_times = bool(profile.get("shows_times"))
        attributes: dict[str, Any] = {
            "username": profile["username"],
            "avatar": profile.get("avatar"),
            # The user's own label from the follow list, if they wrote
            # one: Dienstkaartje itself knows no such thing.
            "role": profile.get("role"),
            "on_shift": bool(profile.get("on_shift")),
            "shift_start": profile.get("shift_start") if shows_times else None,
            "shift_end": profile.get("shift_end") if shows_times else None,
            "shows_train_numbers": bool(profile.get("shows_train_numbers")),
            "trains": sorted(trains_of(profile)),
            "legs": [
                {
                    "train": leg.get("service_number"),
                    "from": leg.get("departure_station"),
                    "to": leg.get("arrival_station"),
                    "departure": leg.get("departure_time") if shows_times else None,
                    "arrival": leg.get("arrival_time") if shows_times else None,
                }
                for leg in profile.get("legs") or []
            ] if profile.get("shows_train_numbers") else [],
        }
        return attributes


class NSReisadviesDelaySensor(_NSDepartureSensorBase):
    """Delay of the route's next trip in minutes (0 when on time).

    ``status`` (``on_time`` / ``delayed`` / ``cancelled``) is an attribute,
    so an automation can trigger on a delay or a cancellation directly.
    """

    _attr_translation_key = "delay"
    _unique_id_suffix = "delay"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    # A delay is a measurement, so Home Assistant keeps long-term
    # statistics: how late this route runs over a week or a month.
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Minutes of delay, or None without a trip."""
        info = self._departure
        return None if info is None else info["delay"]


class NSReisadviesNextTrainSensor(_NSDepartureSensorBase):
    """The route's next train as one short line: ``IC 08:09 +4, spoor 3``."""

    _attr_translation_key = "next_train"
    _unique_id_suffix = "next_train"

    @property
    def native_value(self) -> str | None:
        """The summary line, in HA's language (Dutch or English)."""
        return summary_line(self._departure, self.hass.config.language)
