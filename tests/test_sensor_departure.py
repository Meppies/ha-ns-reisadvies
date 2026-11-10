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
    NSReisadviesNextTrainSensor,
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


async def test_setup_adds_three_sensors_per_route(hass: HomeAssistant) -> None:
    added = await _setup(hass, {"a": _route(), "b": _route(**{CONF_ROUTE_NAME: "Werk"})})
    assert len(added) == 2
    for entities, kwargs in added:
        assert [type(e) for e in entities] == [
            NSReisadviesSensor, NSReisadviesDelaySensor, NSReisadviesNextTrainSensor,
        ]
        route_uid = entities[0].unique_id
        assert entities[1].unique_id == f"{route_uid}_delay"
        assert entities[2].unique_id == f"{route_uid}_next_train"
        for entity in entities[1:]:
            assert entity.device_info["identifiers"] == {(DOMAIN, route_uid)}
        assert kwargs["config_subentry_id"] in {"a", "b"}


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
