"""Wiring of the delay and next-train sensors (v2.20.0).

Covers what the pure tests cannot: that setup creates the two sensors for
every route, that they attach to the route's device, that their state and
attributes reach Home Assistant, and that their texts and icons exist.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockEntityPlatform

from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)
from custom_components.ns_reisadvies.sensor import (
    NSReisadviesDelaySensor,
    NSReisadviesNationalDisruptionSensor,
    NSReisadviesNextTrainSensor,
    NSReisadviesRouteDisruptionSensor,
    NSReisadviesSensor,
    async_setup_entry,
)

COMPONENT = Path(__file__).parent.parent / "custom_components" / "ns_reisadvies"

DELAYED = [{
    "status": "NORMAL",
    "legs": [{
        "origin": {
            "plannedDateTime": "2026-11-02T08:09:00+0100",
            "actualDateTime": "2026-11-02T08:13:00+0100",
            "plannedTrack": "5",
        },
        "product": {"categoryCode": "IC", "shortCategoryName": "IC", "number": "1522"},
    }],
}]


def _coord(hass, data):
    coord = MagicMock()
    coord.hass = hass
    coord.data = data
    coord.last_update_success = True
    return coord


async def _setup(hass, subentries: dict) -> list:
    coords = {sid: _coord(hass, DELAYED) for sid in subentries}
    entry = MagicMock()
    entry.runtime_data = MagicMock(coordinators=coords)
    entry.subentries = subentries
    added: list = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.ns_reisadvies.sensor.entity_platform.async_get_current_platform",
            lambda: MagicMock(),
        )
        assert await async_setup_entry(
            hass, entry, lambda ents, **kw: added.append((list(ents), kw))
        )
    return added


def _route(**data):
    sub = MagicMock()
    sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Amsterdam Centraal", **data}
    return sub


async def test_setup_adds_the_route_sensors(hass: HomeAssistant) -> None:
    added = await _setup(hass, {"a": _route(), "b": _route(**{CONF_ROUTE_NAME: "Werk"})})
    # Two routes, plus the one national disruption sensor for the hub.
    routes = [entry for entry in added if entry[1].get("config_subentry_id")]
    assert len(routes) == 2
    for entities, kwargs in routes:
        assert [type(e) for e in entities] == [
            NSReisadviesSensor, NSReisadviesDelaySensor, NSReisadviesNextTrainSensor,
            NSReisadviesRouteDisruptionSensor,
        ]
        route_uid = entities[0].unique_id
        assert entities[1].unique_id == f"{route_uid}_delay"
        assert entities[2].unique_id == f"{route_uid}_next_train"
        assert entities[3].unique_id == f"{route_uid}_disruptions"
        for entity in entities[1:]:
            assert entity.device_info["identifiers"] == {(DOMAIN, route_uid)}
        # Entity ids sit beside the trips sensor and are derived from the
        # route, not from the translated entity name: a Dutch instance
        # must not end up with sensor.<device>_vertraging.
        trips_object_id = entities[0]._attr_suggested_object_id
        assert entities[1]._attr_suggested_object_id == f"{trips_object_id}_delay"
        assert entities[2]._attr_suggested_object_id == f"{trips_object_id}_next_train"
        assert entities[3]._attr_suggested_object_id == f"{trips_object_id}_disruptions"
        assert kwargs["config_subentry_id"] in {"a", "b"}


async def test_setup_adds_one_national_disruption_sensor(
    hass: HomeAssistant,
) -> None:
    """It belongs to the hub, so it comes without a subentry."""
    added = await _setup(hass, {"a": _route(), "b": _route()})
    national = [entry for entry in added if not entry[1].get("config_subentry_id")]
    assert len(national) == 1
    entities = national[0][0]
    assert [type(e) for e in entities] == [NSReisadviesNationalDisruptionSensor]
    assert entities[0]._attr_suggested_object_id == "ns_disruptions"


async def test_setup_leaves_disruptions_out_when_switched_off(
    hass: HomeAssistant,
) -> None:
    coords = {"a": _coord(hass, DELAYED)}
    coords["a"].watch_disruptions = False
    entry = MagicMock()
    entry.runtime_data = MagicMock(coordinators=coords)
    entry.subentries = {"a": _route()}
    added: list = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.ns_reisadvies.sensor.entity_platform.async_get_current_platform",
            lambda: MagicMock(),
        )
        assert await async_setup_entry(
            hass, entry, lambda ents, **kw: added.append((list(ents), kw))
        )
    assert len(added) == 1
    assert len(added[0][0]) == 3


async def test_route_disruption_sensor_counts_and_explains(
    hass: HomeAssistant,
) -> None:
    """The count is the state; the detail is what a notification reads."""
    added = await _setup(hass, {"a": _route()})
    sensor = added[0][0][3]
    sensor.coordinator.route_disruptions = [{
        "id": "6069064", "type": "DISRUPTION", "title": "Arnhem - Doetinchem.",
        "summary": "Door een wisselstoring rijden er minder treinen.",
        "cause": "wisselstoring", "expected_until": "tot 20:30 uur",
        "impact": 3, "advices": ["Reis via Zutphen."],
        "stations": [{"name": "Arnhem Centraal"}, {"name": "Doetinchem"}],
    }]
    assert sensor.native_value == 1
    attributes = sensor.extra_state_attributes
    assert attributes["titles"] == ["Arnhem - Doetinchem."]
    assert attributes["types"] == ["DISRUPTION"]
    assert attributes["cause"] == "wisselstoring"
    assert attributes["worst_impact"] == 3
    assert attributes["stations"] == ["Arnhem Centraal", "Doetinchem"]

    sensor.coordinator.route_disruptions = []
    assert sensor.native_value == 0
    assert sensor.extra_state_attributes["summary"] is None


async def test_national_sensor_counts_each_kind(hass: HomeAssistant) -> None:
    added = await _setup(hass, {"a": _route()})
    national = [e for e in added if not e[1].get("config_subentry_id")][0][0][0]
    national.coordinator.disruptions = [
        {"id": "1", "type": "DISRUPTION", "title": "A", "summary": "a", "impact": 2},
        {"id": "2", "type": "MAINTENANCE", "title": "B", "summary": "b", "impact": 5},
        {"id": "3", "type": "MAINTENANCE", "title": "C", "summary": "c"},
    ]
    assert national.native_value == 3
    attributes = national.extra_state_attributes
    assert attributes["disruption"] == 1
    assert attributes["maintenance"] == 2
    assert attributes["calamity"] == 0
    assert attributes["worst_impact"] == 5


async def test_delay_is_recorded_as_a_measurement(hass: HomeAssistant) -> None:
    """A delay in minutes belongs in long-term statistics."""
    added = await _setup(hass, {"a": _route()})
    delay = added[0][0][1]
    assert delay.state_class == SensorStateClass.MEASUREMENT
    assert delay.device_class == SensorDeviceClass.DURATION
    assert delay.native_unit_of_measurement == UnitOfTime.MINUTES


@pytest.mark.parametrize(
    ("language", "summary"),
    [("nl", "IC 08:09 +4, spoor 5"), ("en", "IC 08:09 +4, platform 5")],
)
async def test_state_reaches_home_assistant(
    hass: HomeAssistant, language: str, summary: str
) -> None:
    hass.config.language = language
    entities = (await _setup(hass, {"a": _route()}))[0][0]
    delay, next_train = entities[1], entities[2]
    delay.entity_id = "sensor.test_delay"
    next_train.entity_id = "sensor.test_next_train"
    platform = MockEntityPlatform(hass, domain="sensor", platform_name=DOMAIN)
    await platform.async_add_entities([delay, next_train])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_delay")
    assert state.state == "4"
    assert state.attributes["unit_of_measurement"] == "min"
    assert state.attributes["device_class"] == "duration"
    assert state.attributes["status"] == "delayed"
    assert state.attributes["train"] == "IC 1522"
    assert state.attributes["expected"] == "08:13"
    assert "delay" not in state.attributes

    state = hass.states.get("sensor.test_next_train")
    assert state.state == summary
    assert state.attributes["track"] == "5"


async def test_no_trips_means_unknown_and_no_attributes(hass: HomeAssistant) -> None:
    coord = _coord(hass, [])
    delay = NSReisadviesDelaySensor(coord, route_unique_id="x")
    next_train = NSReisadviesNextTrainSensor(coord, route_unique_id="x")
    next_train.hass = hass
    assert delay.native_value is None
    assert next_train.native_value is None
    assert delay.extra_state_attributes == {}


async def test_coordinator_update_is_followed(hass: HomeAssistant) -> None:
    coord = _coord(hass, [])
    delay = NSReisadviesDelaySensor(coord, route_unique_id="x")
    assert delay.native_value is None
    coord.data = DELAYED
    assert delay.native_value == 4


def test_every_sensor_has_texts_and_an_icon() -> None:
    """Custom integrations read names from translations/ only (see v2.19.1)."""
    icons = json.loads((COMPONENT / "icons.json").read_text())["entity"]["sensor"]
    for lang in ("en", "nl"):
        names = json.loads(
            (COMPONENT / "translations" / f"{lang}.json").read_text()
        )["entity"]["sensor"]
        for key in ("delay", "next_train"):
            assert names[key]["name"], (lang, key)
            assert icons[key]["default"].startswith("mdi:"), key
