"""Tests for the NSReisadviesSensor entity."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.ns_reisadvies.const import DOMAIN
from custom_components.ns_reisadvies.sensor import NSReisadviesSensor
from custom_components.ns_reisadvies.types import NSRuntimeData


def _stub_coordinator(
    hass, data: list[dict] | None = None, tracked: dict | None = None
):
    """Hand-rolled stub — DataUpdateCoordinator is heavyweight to spin up
    in unit tests and the sensor only reads three attributes from it.
    """
    coord = MagicMock()
    coord.hass = hass
    coord.data = data
    coord.tracked_trips = tracked or {}
    coord.last_update_success = True
    return coord


def _stub_entry_with_runtime(hass, runtime: NSRuntimeData) -> None:
    """Register a fake hub entry on hass so the sensor can read runtime_data."""
    entry = MagicMock()
    entry.runtime_data = runtime
    hass.config_entries.async_entries = MagicMock(return_value=[entry])


def _make_sensor(coord) -> NSReisadviesSensor:
    return NSReisadviesSensor(
        coord,
        from_station="Hilversum",
        to_station="Duivendrecht",
        unique_id="hilversum_duivendrecht",
    )


async def test_native_value_no_trips(hass) -> None:
    """When the API returns nothing, the sensor reports 'No trips'."""
    coord = _stub_coordinator(hass, data=None)
    _stub_entry_with_runtime(hass, NSRuntimeData())

    sensor = _make_sensor(coord)
    assert sensor.native_value == "No trips"


async def test_native_value_returns_planned_departure(hass) -> None:
    """The sensor exposes the first leg's plannedDateTime as state."""
    trips = [
        {"legs": [{"origin": {"plannedDateTime": "2026-05-08T08:30:00+02:00"}}]}
    ]
    coord = _stub_coordinator(hass, data=trips)
    _stub_entry_with_runtime(hass, NSRuntimeData())

    sensor = _make_sensor(coord)
    assert sensor.native_value == "2026-05-08T08:30:00+02:00"


async def test_extra_state_attributes_exposes_hub_flags(hass) -> None:
    """Card-relevant hub flags are surfaced via extra_state_attributes."""
    coord = _stub_coordinator(hass, data=[{"legs": []}], tracked={"abc": "ctx"})
    _stub_entry_with_runtime(
        hass,
        NSRuntimeData(live_train_map_enabled=True, live_map_refresh_seconds=15),
    )

    sensor = _make_sensor(coord)
    attrs = sensor.extra_state_attributes
    assert attrs["live_train_map_enabled"] is True
    assert attrs["live_map_refresh_seconds"] == 15
    assert attrs["tracked_trips"] == ["abc"]
    assert attrs["trips"] == [{"legs": []}]


async def test_extra_state_attributes_defaults(hass) -> None:
    """Missing hub flags default to safe values."""
    coord = _stub_coordinator(hass, data=None)
    _stub_entry_with_runtime(hass, NSRuntimeData())

    sensor = _make_sensor(coord)
    attrs = sensor.extra_state_attributes
    assert attrs["live_train_map_enabled"] is False
    assert attrs["live_map_refresh_seconds"] == 10
    assert attrs["tracked_trips"] == []


async def test_sensor_has_device_info_and_entity_name(hass) -> None:
    """Each route exposes a DeviceInfo and uses has_entity_name."""
    coord = _stub_coordinator(hass, data=None)
    sensor = _make_sensor(coord)

    assert sensor._attr_has_entity_name is True
    assert sensor._attr_name is None
    assert sensor.device_info is not None
    assert sensor.device_info["identifiers"] == {(DOMAIN, "hilversum_duivendrecht")}
    assert sensor.device_info["name"] == "Hilversum → Duivendrecht"
