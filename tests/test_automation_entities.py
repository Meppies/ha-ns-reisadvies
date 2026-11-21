"""Sensors, binary sensors and events for automations (v2.28.0).

Everything here describes one trip per route — a pinned favourite,
else the next departure — and the tests check three things: that the
right trip is described, that NS is only asked where the train is
when something needs it, and that events fire for real changes only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant, callback

from custom_components.ns_reisadvies import binary_sensor as bs_platform
from custom_components.ns_reisadvies import event as event_platform
from custom_components.ns_reisadvies.binary_sensor import (
    FOCUS_BINARY_SENSORS,
    NSCalamityBinarySensor,
    NSFocusBinarySensor,
)
from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
    SUBENTRY_TYPE_ROUTE,
)
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator
from custom_components.ns_reisadvies.event import EVENT_TYPES, NSJourneyEvent
from custom_components.ns_reisadvies.route_entity import route_ids
from custom_components.ns_reisadvies.sensor import (
    FOCUS_SENSORS,
    ROUTE_DISRUPTION_SENSORS,
    NSFocusSensor,
    NSRouteDisruptionDetailSensor,
)


def _coord(hass: HomeAssistant, **kw) -> NSUpdateCoordinator:
    defaults = {"api_key": "k", "from_station": "Hilversum", "to_station": "Amersfoort Centraal"}
    defaults.update(kw)
    coord = NSUpdateCoordinator(hass, **defaults)
    coord._store = MagicMock()
    coord._store.async_save = AsyncMock()
    return coord


def _at(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _trip(ctx: str, dep: int, arr: int, *, track: str = "3", delay: int = 0,
          status: str = "NORMAL", number: str = "1537") -> dict:
    return {
        "ctxRecon": ctx,
        "status": status,
        "legs": [{
            "product": {"number": number, "shortCategoryName": "IC",
                        "displayName": "NS Intercity"},
            "direction": "Deventer",
            "origin": {"name": "Hilversum", "uicCode": "8400320",
                       "plannedDateTime": _at(dep), "actualDateTime": _at(dep + delay),
                       "plannedTrack": "3", "actualTrack": track},
            "destination": {"name": "Amersfoort Centraal", "uicCode": "8400055",
                            "plannedDateTime": _at(arr), "actualDateTime": _at(arr + delay)},
            "crowdForecast": "LOW",
        }],
    }


STOPS = [
    {"name": "Hilversum", "uicCode": "8400320", "lat": 52.2270, "lng": 5.1810, "status": "ORIGIN"},
    {"name": "Baarn", "uicCode": "8400080", "lat": 52.2110, "lng": 5.2870, "status": "PASSING"},
    {"name": "Amersfoort Centraal", "uicCode": "8400055", "lat": 52.1533, "lng": 5.3736,
     "status": "DESTINATION"},
]


def _events(hass: HomeAssistant) -> list:
    seen: list = []

    @callback
    def _heard(event) -> None:
        seen.append(event.data)

    hass.bus.async_listen("ns_reisadvies_event", _heard)
    return seen


# --------------------------------------------------------------------
# the coordinator side
# --------------------------------------------------------------------

async def test_the_focus_is_the_next_departure_without_a_favourite(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord._refresh_focus([_trip("A", 8, 20), _trip("B", 38, 50)], datetime.now(timezone.utc))
    assert coord.focus["identity"] == "A" and coord.focus_source == "next"
    assert coord.focus["platform"] == "3"


async def test_a_pinned_favourite_takes_the_focus(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.tracked_trips = {"B": 0.0}
    coord._refresh_focus([_trip("A", 8, 20), _trip("B", 38, 50)], datetime.now(timezone.utc))
    assert coord.focus["identity"] == "B" and coord.focus_source == "favourite"


async def test_the_first_look_is_not_news(hass: HomeAssistant) -> None:
    """A restart mid-journey must not announce a departure."""
    seen = _events(hass)
    coord = _coord(hass)
    coord.tracked_trips = {"A": 0.0}
    coord._refresh_focus([_trip("A", -10, 20)], datetime.now(timezone.utc))
    await hass.async_block_till_done()
    assert seen == []
    # ...and it is remembered, so the next look does not fire it either.
    coord._refresh_focus([_trip("A", -10, 20)], datetime.now(timezone.utc))
    await hass.async_block_till_done()
    assert seen == []


async def test_a_platform_change_is_fired_on_the_bus_and_to_listeners(
    hass: HomeAssistant,
) -> None:
    seen = _events(hass)
    coord = _coord(hass)
    heard: list = []
    remove = coord.async_add_event_listener(lambda kind, data: heard.append(kind))
    now = datetime.now(timezone.utc)
    coord._refresh_focus([_trip("A", 8, 20, track="3")], now)
    coord._refresh_focus([_trip("A", 8, 20, track="5")], now)
    await hass.async_block_till_done()
    assert [e["type"] for e in seen] == ["platform_changed"]
    assert seen[0]["platform"] == "5" and seen[0]["previous_platform"] == "3"
    assert seen[0]["route"] == "Hilversum → Amersfoort Centraal"
    assert heard == ["platform_changed"]
    remove()
    remove()  # twice is harmless
    coord._refresh_focus([_trip("A", 8, 20, track="7")], now)
    assert heard == ["platform_changed"]


async def test_the_focus_moving_on_still_reports_the_departure(
    hass: HomeAssistant,
) -> None:
    """The next train left, so the one after it is next now — and the
    one that left still gets its "departed"."""
    seen = _events(hass)
    coord = _coord(hass)
    now = datetime.now(timezone.utc)
    trips = [_trip("A", 1, 20), _trip("B", 31, 50)]
    coord._refresh_focus(trips, now)
    assert coord.focus["identity"] == "A"
    later = now + timedelta(minutes=3)
    coord._refresh_focus(trips, later)
    await hass.async_block_till_done()
    assert coord.focus["identity"] == "B"
    assert [e["type"] for e in seen] == ["departed"]
    assert seen[0]["train_number"] == "1537"


async def test_disruptions_on_the_route_are_announced_once_they_change(
    hass: HomeAssistant,
) -> None:
    seen = _events(hass)
    coord = _coord(hass)
    coord.route_disruptions = [{"id": "X", "type": "DISRUPTION", "title": "T"}]
    coord._refresh_route_disruptions()  # first look: not news
    coord.route_disruptions = [{"id": "X", "type": "DISRUPTION", "title": "T"},
                               {"id": "Y", "type": "MAINTENANCE", "title": "U"}]
    coord._refresh_route_disruptions()
    coord.route_disruptions = []
    coord._refresh_route_disruptions()
    await hass.async_block_till_done()
    assert [(e["type"], e["id"]) for e in seen] == [
        ("disruption_started", "Y"), ("disruption_ended", "X"), ("disruption_ended", "Y"),
    ]
    # The kind of disruption has its own key; "type" names the event.
    assert seen[0]["disruption_type"] == "MAINTENANCE"


async def test_nobody_listening_means_no_tick(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    assert coord._focus_unsub is None
    remove = coord.async_add_focus_consumer()
    assert coord._focus_unsub is not None
    other = coord.async_add_focus_consumer(live=True)
    assert coord._live_consumers == 1
    other()
    assert coord._live_consumers == 0 and coord._focus_unsub is not None
    remove()
    assert coord._focus_unsub is None and coord._focus_consumers == 0
    coord.async_stop_focus_tick()  # idempotent


async def _ticked(hass: HomeAssistant, coord: NSUpdateCoordinator, trips: list) -> None:
    coord.data = trips
    coord.async_fetch_train_position = AsyncMock(
        return_value={"lat": 52.2190, "lng": 5.2340, "speed": 117.0, "heading": 101.0},
    )
    coord.async_journey_stops = AsyncMock(return_value=STOPS)
    await coord.async_refresh_focus_live()


async def test_the_train_is_only_asked_for_when_a_live_entity_listens(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    remove = coord.async_add_focus_consumer()  # a departure sensor: no live
    await _ticked(hass, coord, [_trip("A", 8, 20)])
    coord.async_fetch_train_position.assert_not_awaited()
    assert coord.focus_live == {}
    remove()


async def test_a_live_entity_gets_the_train_inside_the_window(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    # The pinned trip left two minutes ago; the train is past Hilversum.
    coord.tracked_trips = {"A": 0.0}
    remove = coord.async_add_focus_consumer(live=True)
    await _ticked(hass, coord, [_trip("A", -2, 10)])
    coord.async_fetch_train_position.assert_awaited_once()
    live = coord.focus_live
    assert live["speed"] == 117.0
    assert live["next_station"] == "Amersfoort Centraal"
    assert 0 < live["progress"] < 100
    remove()


async def test_no_request_far_from_the_trip_or_with_the_option_off(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    remove = coord.async_add_focus_consumer(live=True)
    await _ticked(hass, coord, [_trip("A", 120, 140)])  # two hours away
    coord.async_fetch_train_position.assert_not_awaited()
    remove()

    off = _coord(hass, live_sensors=False)
    remove = off.async_add_focus_consumer(live=True)
    await _ticked(hass, off, [_trip("A", 8, 20)])
    off.async_fetch_train_position.assert_not_awaited()
    remove()

    cancelled = _coord(hass)
    remove = cancelled.async_add_focus_consumer(live=True)
    await _ticked(hass, cancelled, [_trip("A", 8, 20, status="CANCELLED")])
    cancelled.async_fetch_train_position.assert_not_awaited()
    remove()


async def test_no_times_means_no_window(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.focus = {"departure": None, "arrival": None}
    assert coord._live_window_open(datetime.now(timezone.utc)) is False


async def test_the_tick_callback_refreshes(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.async_refresh_focus_live = AsyncMock()
    await coord._async_focus_tick(datetime.now(timezone.utc))
    coord.async_refresh_focus_live.assert_awaited_once()


async def test_the_event_memory_does_not_grow_forever(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._events_fired = {f"x{n}" for n in range(600)}
    coord._refresh_focus([], datetime.now(timezone.utc))
    assert coord._events_fired == set()


async def test_a_refresh_describes_the_focus_and_announces_disruptions(
    hass: HomeAssistant,
) -> None:
    from custom_components.ns_reisadvies._disruptions import parse_disruptions
    coord = _coord(hass)
    coord.async_fetch_disruptions = AsyncMock(return_value=parse_disruptions([]))
    coord._session = MagicMock()
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value={"trips": [_trip("A", 30, 50)]})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    coord._session.get = MagicMock(return_value=response)
    await coord._async_update_data()
    assert coord.focus["identity"] == "A"
    assert coord._route_disruption_ids == set()


# --------------------------------------------------------------------
# the entities
# --------------------------------------------------------------------

def _sensor(coord, key):
    description = next(d for d in FOCUS_SENSORS if d.key == key)
    return NSFocusSensor(coord, description, route_unique_id="r", route_object_id="ns_werk")


def _binary(coord, key):
    description = next(d for d in FOCUS_BINARY_SENSORS if d.key == key)
    return NSFocusBinarySensor(coord, description, route_unique_id="r",
                               route_object_id="ns_werk")


async def test_focus_sensors_read_the_focus(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.last_update_success = True
    coord._refresh_focus([_trip("A", 8, 20, delay=2, track="5")], datetime.now(timezone.utc))
    departure = _sensor(coord, "departure")
    assert departure.entity_id == "sensor.ns_werk_departure"
    assert departure.unique_id == "r_departure"
    assert departure.native_value == coord.focus["departure"]
    attributes = departure.extra_state_attributes
    assert attributes["train"] == "IC 1537" and attributes["focus"] == "next"
    assert attributes["delay"] == 2
    assert _sensor(coord, "platform").native_value == "5"
    assert _sensor(coord, "platform").extra_state_attributes is None
    assert _sensor(coord, "crowd").native_value == "low"
    assert _sensor(coord, "train_type").native_value == "NS Intercity"
    assert _sensor(coord, "departure").available is True


async def test_unexpected_crowding_is_not_an_enum_value(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.focus = {"crowd": "unknown"}
    assert _sensor(coord, "crowd").native_value is None


async def test_live_sensors_are_unknown_without_a_train(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    for key in ("speed", "next_station", "progress", "remaining_distance"):
        assert _sensor(coord, key).native_value is None
    coord.focus_live = {"speed": 88.0, "next_station": "Baarn", "progress": 42.0,
                        "remaining_km": 7.5, "heading": 90, "current_station": None}
    assert _sensor(coord, "speed").native_value == 88.0
    assert _sensor(coord, "remaining_distance").native_value == 7.5


async def test_the_important_sensors_are_on_and_the_rest_off() -> None:
    enabled = {d.key for d in FOCUS_SENSORS if d.entity_registry_enabled_default}
    assert enabled == {"departure", "arrival", "platform", "arrival_platform",
                       "leave_at", "following_departure", "last_departure",
                       "next_station", "speed", "progress"}
    live = {d.key for d in FOCUS_SENSORS if d.live}
    assert live == {"next_station", "current_station", "speed", "heading",
                    "progress", "remaining_distance"}
    assert not any(d.entity_registry_enabled_default for d in ROUTE_DISRUPTION_SENSORS)


async def test_focus_entities_register_and_unregister(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    sensor = _sensor(coord, "speed")
    sensor.hass = hass
    sensor.entity_id = "sensor.ns_werk_speed"
    await sensor.async_added_to_hass()
    assert coord._live_consumers == 1
    await sensor.async_will_remove_from_hass()
    for remove in sensor._on_remove or []:
        remove()
    assert coord._live_consumers == 0


async def test_route_disruption_details(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.route_disruptions = [
        {"id": "1", "type": "DISRUPTION", "extra_travel_time": None},
        {"id": "2", "type": "MAINTENANCE", "extra_travel_time": "+30 min"},
        {"id": "3", "type": "MAINTENANCE"},
    ]

    def detail(key):
        description = next(d for d in ROUTE_DISRUPTION_SENSORS if d.key == key)
        return NSRouteDisruptionDetailSensor(coord, description, route_unique_id="r",
                                             route_object_id="ns_werk")

    assert detail("unplanned_disruptions").native_value == 1
    assert detail("engineering_works").native_value == 2
    assert detail("extra_travel_time").native_value == "+30 min"
    sensor = detail("engineering_works")
    sensor.hass = hass
    sensor.entity_id = "sensor.ns_werk_engineering_works"
    await sensor.async_added_to_hass()
    assert coord._focus_consumers == 0  # read off the refresh, no tick


async def test_binary_sensors(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    assert _binary(coord, "cancelled").is_on is None
    assert _binary(coord, "at_station").is_on is None
    coord._refresh_focus([_trip("A", 8, 20, track="5", delay=3, status="CANCELLED")],
                         datetime.now(timezone.utc))
    assert _binary(coord, "cancelled").is_on is True
    assert _binary(coord, "delayed").is_on is True
    changed = _binary(coord, "platform_changed")
    assert changed.entity_id == "binary_sensor.ns_werk_platform_changed"
    assert changed.is_on is True
    assert changed.extra_state_attributes == {
        "platform": "5", "planned_platform": "3", "train": "IC 1537",
    }
    coord.focus_live = {"at_station": True, "moving": False, "current_station": "Baarn"}
    assert _binary(coord, "at_station").is_on is True
    assert _binary(coord, "at_station").extra_state_attributes == {"station": "Baarn"}
    assert _binary(coord, "moving").is_on is False
    assert _binary(coord, "moving").extra_state_attributes is None
    assert _binary(coord, "delayed").extra_state_attributes is None
    coord.focus = {}
    assert _binary(coord, "delayed").is_on is None

    route = _binary(coord, "route_disruption")
    assert route.is_on is False
    assert route.extra_state_attributes == {"count": 0, "title": None, "summary": None}
    coord.route_disruptions = [{"id": "1", "title": "Weesp", "summary": "Storing"}]
    assert route.is_on is True and route.extra_state_attributes["title"] == "Weesp"


async def test_the_national_calamity_sensor(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    sensor = NSCalamityBinarySensor(coord, hub_id="hub")
    assert sensor.entity_id == "binary_sensor.ns_calamity"
    assert sensor.is_on is False
    assert sensor.extra_state_attributes["count"] == 0
    coord.disruptions = [{"type": "DISRUPTION"},
                         {"type": "CALAMITY", "title": "Stroomstoring", "summary": "S",
                          "url": "https://ns.nl/x"}]
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["url"] == "https://ns.nl/x"


async def test_the_event_entity_records_what_happened(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    entity = NSJourneyEvent(coord, route_unique_id="r", route_object_id="ns_werk")
    entity.hass = hass
    entity.entity_id = "event.ns_werk_journey"
    entity.async_write_ha_state = MagicMock()
    await entity.async_added_to_hass()
    assert entity.event_types == EVENT_TYPES
    coord._fire("platform_changed", {"platform": "5"})
    assert entity.state_attributes["event_type"] == "platform_changed"
    assert entity.state_attributes["platform"] == "5"
    entity.async_write_ha_state.assert_called_once()
    # Something it does not know is ignored, and a refresh is not an event.
    entity._on_event("something_else", {})
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_called_once()


# --------------------------------------------------------------------
# setting the platforms up
# --------------------------------------------------------------------

def _entry(coords: dict, routes: dict) -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "hub"
    entry.runtime_data = MagicMock(coordinators=coords)
    subentries = {}
    for key, data in routes.items():
        sub = MagicMock()
        sub.subentry_type = SUBENTRY_TYPE_ROUTE
        sub.data = data
        subentries[key] = sub
    other = MagicMock()
    other.subentry_type = "something_else"
    subentries["other"] = other
    subentries["orphan"] = MagicMock(subentry_type=SUBENTRY_TYPE_ROUTE, data={})
    entry.subentries = subentries
    return entry


ROUTE = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Amersfoort Centraal"}


async def test_binary_sensor_setup(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    added: list = []
    entry = _entry({"a": coord}, {"a": ROUTE})
    assert await bs_platform.async_setup_entry(
        hass, entry, lambda entities, **kw: added.append((list(entities), kw)),
    )
    route, hub = added
    assert route[1] == {"config_subentry_id": "a"}
    assert isinstance(hub[0][0], NSCalamityBinarySensor)

    # Without composition there is no "shorter train", and without a
    # walking time no "time to leave".
    assert "shorter_train" not in {e._key for e in route[0]}
    assert "time_to_leave" not in {e._key for e in route[0]}
    rich = _coord(hass, minutes_to_station=8, fetch_composition=True)
    added.clear()
    await bs_platform.async_setup_entry(
        hass, _entry({"a": rich}, {"a": ROUTE}),
        lambda entities, **kw: added.append((list(entities), kw)),
    )
    assert {e._key for e in added[0][0]} == {d.key for d in FOCUS_BINARY_SENSORS}

    # Without live sensors or disruptions, those are left out.
    quiet = _coord(hass, live_sensors=False, disruptions=False)
    added.clear()
    await bs_platform.async_setup_entry(
        hass, _entry({"a": quiet}, {"a": ROUTE}),
        lambda entities, **kw: added.append((list(entities), kw)),
    )
    assert len(added) == 1
    assert {e._key for e in added[0][0]} == {
        "cancelled", "platform_changed", "delayed", "arrival_platform_changed",
        "transfer_at_risk",
    }


async def test_event_setup(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    added: list = []
    assert await event_platform.async_setup_entry(
        hass, _entry({"a": coord}, {"a": {**ROUTE, CONF_ROUTE_NAME: "Werk"}}),
        lambda entities, **kw: added.append((list(entities), kw)),
    )
    assert added[0][0][0].entity_id == "event.ns_werk_journey"


async def test_setups_survive_an_old_home_assistant(hass: HomeAssistant) -> None:
    """Before 2024.11, async_add_entities took no config_subentry_id."""
    coord = _coord(hass)
    added: list = []

    def old_style(entities, **kw):
        if kw:
            raise TypeError("config_subentry_id")
        added.append(list(entities))

    entry = _entry({"a": coord}, {"a": ROUTE})
    await bs_platform.async_setup_entry(hass, entry, old_style)
    await event_platform.async_setup_entry(hass, entry, old_style)
    assert len(added) == 3


async def test_setups_wait_for_the_hub(hass: HomeAssistant) -> None:
    entry = MagicMock()
    entry.runtime_data = None
    assert await bs_platform.async_setup_entry(hass, entry, MagicMock()) is False
    assert await event_platform.async_setup_entry(hass, entry, MagicMock()) is False


def test_route_ids_match_the_sensor_platform() -> None:
    assert route_ids(ROUTE) == (
        "hilversum_amersfoort centraal", "ns_hilversum_amersfoort_centraal",
        "Hilversum", "Amersfoort Centraal", None,
    )
    named = route_ids({**ROUTE, CONF_ROUTE_NAME: " Werk "})
    assert named[0] == "hilversum_amersfoort centraal_werk" and named[1] == "ns_werk"


# --------------------------------------------------------------------
# v2.28.0, second round
# --------------------------------------------------------------------

from zoneinfo import ZoneInfo  # noqa: E402

DUTCH = ZoneInfo("Europe/Amsterdam")


def test_the_service_day_ends_at_four_the_next_morning() -> None:
    evening = datetime(2026, 11, 21, 22, 30, tzinfo=DUTCH)
    assert NSUpdateCoordinator.service_day_end(evening) == datetime(
        2026, 11, 22, 4, 0, tzinfo=DUTCH)
    # Half past midnight still belongs to the evening before.
    night = datetime(2026, 11, 22, 0, 30, tzinfo=DUTCH)
    assert NSUpdateCoordinator.service_day_end(night) == datetime(
        2026, 11, 22, 4, 0, tzinfo=DUTCH)
    morning = datetime(2026, 11, 22, 4, 30, tzinfo=DUTCH)
    assert NSUpdateCoordinator.service_day_end(morning) == datetime(
        2026, 11, 23, 4, 0, tzinfo=DUTCH)


async def test_the_last_train_is_asked_as_arrive_by_the_end_of_the_day(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    coord.async_search_trips = AsyncMock(return_value=([_trip("L", 30, 45)], None))
    # Nobody shows it: nothing is asked.
    await coord.async_refresh_last_train()
    coord.async_search_trips.assert_not_awaited()

    remove = coord.async_add_focus_consumer(last_train=True)
    await coord.async_refresh_last_train()
    kwargs = coord.async_search_trips.call_args.kwargs
    assert kwargs["arrival"] is True and kwargs["extras"] is False
    assert kwargs["train_types"] == ["IC"]
    assert kwargs["when"].endswith("03:59:00+01:00")
    assert coord.last_train["train"] == "IC 1537"
    # Within the hour it is not asked again.
    await coord.async_refresh_last_train()
    assert coord.async_search_trips.await_count == 1
    remove()
    assert coord._last_consumers == 0


async def test_a_failed_last_train_lookup_keeps_what_was_known(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord.last_train = {"train": "IC 999"}
    coord.async_search_trips = AsyncMock(return_value=([], "unavailable"))
    remove = coord.async_add_focus_consumer(last_train=True)
    await coord.async_refresh_last_train()
    assert coord.last_train == {"train": "IC 999"}
    remove()


async def test_the_tick_also_looks_up_the_last_train(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.async_refresh_focus_live = AsyncMock()
    coord.async_refresh_last_train = AsyncMock()
    await coord._async_focus_tick(datetime.now(timezone.utc))
    coord.async_refresh_last_train.assert_awaited_once()


async def test_the_focus_refresh_fills_the_train_after(hass: HomeAssistant) -> None:
    coord = _coord(hass, minutes_to_station=8)
    coord._refresh_focus([_trip("A", 20, 35), _trip("B", 50, 65)],
                         datetime.now(timezone.utc))
    assert coord.following["train"] == "IC 1537"
    assert coord.focus["leave_at"] is not None


async def test_a_search_for_times_only_skips_the_extras(hass: HomeAssistant) -> None:
    coord = _coord(hass, fetch_composition=True)
    coord._annotate_compositions = AsyncMock()
    coord._session = MagicMock()
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value={"trips": [_trip("A", 20, 35)]})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    coord._session.get = MagicMock(return_value=response)
    trips, problem = await coord.async_search_trips("A", "B", extras=False)
    assert problem is None and len(trips) == 1
    coord._annotate_compositions.assert_not_awaited()


async def test_the_new_sensors_read_their_own_trip(hass: HomeAssistant) -> None:
    coord = _coord(hass, minutes_to_station=8)
    coord._refresh_focus([_trip("A", 20, 35, track="5"), _trip("B", 50, 65)],
                         datetime.now(timezone.utc))
    coord.last_train = {"departure": coord.following["departure"], "train": "IC 9",
                        "train_number": "9", "platform": "1", "departure_delay": 0,
                        "arrival": None, "transfers": 0}
    after = _sensor(coord, "following_departure")
    assert after.native_value == coord.following["departure"]
    assert after.extra_state_attributes["train"] == "IC 1537"
    last = _sensor(coord, "last_departure")
    assert last._last_train is True
    assert last.extra_state_attributes["train"] == "IC 9"
    assert last.extra_state_attributes["arrival"] is None
    leave = _sensor(coord, "leave_at")
    assert leave.native_value == coord.focus["leave_at"]
    assert leave.extra_state_attributes == {"minutes_to_station": 8}
    assert _sensor(coord, "arrival_platform").extra_state_attributes["station"] == \
        "Amersfoort Centraal"
    assert _sensor(coord, "transfer_margin").extra_state_attributes == {"transfers": []}
    coord.following = {}
    assert _sensor(coord, "following_departure").extra_state_attributes is None


async def test_the_new_binary_sensors(hass: HomeAssistant) -> None:
    coord = _coord(hass, minutes_to_station=8)
    trip = _trip("A", 5, 20)
    trip["legs"][0]["composition"] = {"numberOfParts": 3, "plannedNumberOfParts": 6}
    coord._refresh_focus([trip], datetime.now(timezone.utc))
    assert _binary(coord, "time_to_leave").is_on is True
    assert _binary(coord, "time_to_leave").extra_state_attributes["minutes_to_station"] == 8
    shorter = _binary(coord, "shorter_train")
    assert shorter.is_on is True
    assert shorter.extra_state_attributes == {
        "carriages": 3, "planned_carriages": 6, "train": "IC 1537",
    }
    risk = _binary(coord, "transfer_at_risk")
    assert risk.is_on is False
    assert risk.extra_state_attributes["station"] is None
    coord.focus = {}
    assert _binary(coord, "shorter_train").is_on is None


async def test_composition_is_read_at_the_boarding_stop(hass: HomeAssistant) -> None:
    """A train is shortened along its run; the traveller boards where
    they board."""
    coord = _coord(hass, fetch_composition=True)
    coord._fetch_journey_composition = AsyncMock(return_value={
        "trainType": "ICM", "numberOfParts": 7, "plannedNumberOfParts": 7,
        "_by_uic": {"8400320": {"numberOfParts": 4, "plannedNumberOfParts": 7,
                                "numberOfSeats": None}},
    })
    trips = [_trip("A", 5, 20)]
    await coord._annotate_compositions(trips, {})
    composition = trips[0]["legs"][0]["composition"]
    assert composition["numberOfParts"] == 4 and composition["plannedNumberOfParts"] == 7
    assert "_by_uic" not in composition
    # A figure NS left out at that stop does not wipe the run's own.
    assert "numberOfSeats" not in composition


async def test_composition_keeps_the_stock_of_every_stop(hass: HomeAssistant) -> None:
    """Planned against actual, per stop, the way /v2/journey reports it."""
    coord = _coord(hass, fetch_composition=True)
    payload = {"payload": {"stops": [
        {"status": "ORIGIN", "stop": {"uicCode": "8400058"},
         "plannedStock": {"numberOfParts": 7, "numberOfSeats": 471},
         "actualStock": {"trainType": "ICM", "numberOfParts": 7, "numberOfSeats": 471,
                         "hasSignificantChange": False, "trainParts": []}},
        {"status": "STOP", "stop": {"uicCode": "8400320"},
         "plannedStock": {"numberOfParts": 7, "numberOfSeats": 471},
         "actualStock": {"numberOfParts": 4, "numberOfSeats": 270,
                         "hasSignificantChange": True}},
        {"status": "PASSING", "stop": {"uicCode": "8400080"}},
    ]}}
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value=payload)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=response)
    slim = await coord._fetch_journey_composition("1537", {})
    assert slim["plannedNumberOfParts"] == 7
    assert slim["_by_uic"]["8400320"] == {
        "numberOfParts": 4, "numberOfSeats": 270, "plannedNumberOfParts": 7,
        "plannedNumberOfSeats": 471, "significantChange": True,
    }
    assert "8400080" not in slim["_by_uic"]
