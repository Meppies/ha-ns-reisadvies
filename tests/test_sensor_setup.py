"""Cover sensor.async_setup_entry by direct invocation with mocked hass/entry."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION, CONF_TO_STATION, SUBENTRY_TYPE_ROUTE,
)
from custom_components.ns_reisadvies.sensor import async_setup_entry


async def test_sensor_setup_raises_not_ready_without_runtime():
    hass = MagicMock(); entry = MagicMock(); entry.runtime_data = None
    add_entities = MagicMock()
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry, add_entities)


async def test_sensor_setup_raises_not_ready_when_no_coordinators():
    hass = MagicMock()
    runtime = MagicMock(); runtime.coordinators = {}
    entry = MagicMock(); entry.runtime_data = runtime
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry, MagicMock())


async def test_sensor_setup_skips_non_route_subentries():
    hass = MagicMock()
    coord = MagicMock()
    runtime = MagicMock(); runtime.coordinators = {"sub": coord}
    sub = MagicMock(); sub.subentry_type = "OTHER"
    entry = MagicMock(); entry.runtime_data = runtime
    entry.subentries = {"sub": sub}
    add_entities = MagicMock()
    # entity_platform.async_get_current_platform is called for service registration
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.ns_reisadvies.sensor.entity_platform.async_get_current_platform",
            lambda: MagicMock(),
        )
        result = await async_setup_entry(hass, entry, add_entities)
    assert result is True
    add_entities.assert_not_called()  # No route subentries -> no add


async def test_sensor_setup_skips_subentry_without_coord():
    hass = MagicMock()
    runtime = MagicMock(); runtime.coordinators = {"other": MagicMock()}
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock(); entry.runtime_data = runtime
    entry.subentries = {"sub": sub}  # subentry_id 'sub' but coord under 'other'
    add_entities = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.ns_reisadvies.sensor.entity_platform.async_get_current_platform",
            lambda: MagicMock(),
        )
        result = await async_setup_entry(hass, entry, add_entities)
    assert result is True
    add_entities.assert_not_called()


async def test_sensor_setup_happy_path_creates_sensor():
    hass = MagicMock()
    coord = MagicMock()
    runtime = MagicMock(); runtime.coordinators = {"sub1": coord}
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock(); entry.runtime_data = runtime
    entry.subentries = {"sub1": sub}
    add_entities = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.ns_reisadvies.sensor.entity_platform.async_get_current_platform",
            lambda: MagicMock(),
        )
        result = await async_setup_entry(hass, entry, add_entities)
    assert result is True
    add_entities.assert_called_once()
    args, kwargs = add_entities.call_args
    assert kwargs.get("config_subentry_id") == "sub1"


async def test_sensor_setup_with_route_name_uses_name_slug():
    """v2.15.0: when subentry.data has CONF_ROUTE_NAME, the sensor's
    suggested_object_id is derived from that name (e.g. "ns_werk")
    rather than from the station pair."""
    from custom_components.ns_reisadvies.const import CONF_ROUTE_NAME
    hass = MagicMock()
    coord = MagicMock()
    runtime = MagicMock(); runtime.coordinators = {"sub1": coord}
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "Werk",
    }
    entry = MagicMock(); entry.runtime_data = runtime
    entry.subentries = {"sub1": sub}
    captured: dict = {}
    def add(sensors, **kwargs):
        captured["sensors"] = list(sensors)
    add_entities = MagicMock(side_effect=add)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.ns_reisadvies.sensor.entity_platform.async_get_current_platform",
            lambda: MagicMock(),
        )
        result = await async_setup_entry(hass, entry, add_entities)
    assert result is True
    sensor = captured["sensors"][0]
    assert sensor._attr_unique_id == "hilversum_duivendrecht_werk"
    assert sensor._attr_suggested_object_id == "ns_werk"
    assert sensor._attr_device_info["name"] == "Werk"


async def test_sensor_setup_falls_back_on_typeerror():
    """Old HA without config_subentry_id support -> TypeError -> fallback call."""
    hass = MagicMock()
    coord = MagicMock()
    runtime = MagicMock(); runtime.coordinators = {"sub1": coord}
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock(); entry.runtime_data = runtime
    entry.subentries = {"sub1": sub}
    # First call raises TypeError, second call (fallback without kwarg) succeeds
    call_count = {"n": 0}
    def add(*args, **kwargs):
        call_count["n"] += 1
        if "config_subentry_id" in kwargs:
            raise TypeError("old HA")
    add_entities = MagicMock(side_effect=add)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.ns_reisadvies.sensor.entity_platform.async_get_current_platform",
            lambda: MagicMock(),
        )
        result = await async_setup_entry(hass, entry, add_entities)
    assert result is True
    assert call_count["n"] == 2  # First call raised, fallback succeeded
