"""Coverage for sensor edge cases."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.ns_reisadvies.sensor import NSReisadviesSensor


def _sensor(coord):
    return NSReisadviesSensor(
        coord, from_station="A", to_station="B",
        unique_id="a_b", suggested_object_id="ns_a_b",
    )


def test_native_value_no_data_returns_no_trips():
    coord = MagicMock()
    coord.data = None
    coord.tracked_trips = {}
    s = _sensor(coord)
    assert s.native_value == "No trips"


def test_native_value_malformed_data_returns_data_available():
    coord = MagicMock()
    coord.data = [{"legs": []}]  # IndexError on [0]["origin"]
    coord.tracked_trips = {}
    s = _sensor(coord)
    assert s.native_value == "Data available"


async def test_track_trip_raises_on_empty_ctx_recon():
    coord = MagicMock()
    s = _sensor(coord)
    with pytest.raises(ServiceValidationError):
        await s.async_track_trip("")
    with pytest.raises(ServiceValidationError):
        await s.async_track_trip("   ")


async def test_untrack_trip_raises_on_empty_ctx_recon():
    coord = MagicMock()
    s = _sensor(coord)
    with pytest.raises(ServiceValidationError):
        await s.async_untrack_trip("")
    with pytest.raises(ServiceValidationError):
        await s.async_untrack_trip("   ")


async def test_track_trip_no_track_method_raises():
    """Coord without track_trip method -> ServiceValidationError."""
    from custom_components.ns_reisadvies.sensor import NSReisadviesSensor
    coord = MagicMock(spec=[])  # No track_trip attr
    s = NSReisadviesSensor(coord, from_station="A", to_station="B", unique_id="a_b", suggested_object_id="x")
    with pytest.raises(ServiceValidationError):
        await s.async_track_trip("abc")


async def test_untrack_trip_no_untrack_method_raises():
    from custom_components.ns_reisadvies.sensor import NSReisadviesSensor
    coord = MagicMock(spec=[])
    s = NSReisadviesSensor(coord, from_station="A", to_station="B", unique_id="a_b", suggested_object_id="x")
    with pytest.raises(ServiceValidationError):
        await s.async_untrack_trip("abc")


def test_extra_state_attributes_with_list_tracked_trips():
    """Tracked-trips legacy list format -> still produces attributes."""
    from custom_components.ns_reisadvies.sensor import NSReisadviesSensor
    coord = MagicMock()
    coord.tracked_trips = ["A", "B"]  # legacy list, not dict
    coord.data = []
    coord.hass = MagicMock()
    coord.hass.config_entries.async_entries.return_value = []
    s = NSReisadviesSensor(coord, from_station="X", to_station="Y", unique_id="x_y", suggested_object_id="z")
    attrs = s.extra_state_attributes
    assert attrs["tracked_trips"] == ["A", "B"]


async def test_track_trip_success_calls_coord():
    from custom_components.ns_reisadvies.sensor import NSReisadviesSensor
    coord = MagicMock(); coord.track_trip = MagicMock(); coord.tracked_trips = {}
    s = NSReisadviesSensor(coord, from_station="A", to_station="B", unique_id="a_b", suggested_object_id="x")
    s.async_write_ha_state = MagicMock()
    s.hass = MagicMock()
    await s.async_track_trip("abc")
    coord.track_trip.assert_called_once_with("abc")
    s.async_write_ha_state.assert_called_once()


async def test_untrack_trip_success_calls_coord():
    from custom_components.ns_reisadvies.sensor import NSReisadviesSensor
    coord = MagicMock(); coord.untrack_trip = MagicMock(); coord.tracked_trips = {}
    s = NSReisadviesSensor(coord, from_station="A", to_station="B", unique_id="a_b", suggested_object_id="x")
    s.async_write_ha_state = MagicMock()
    s.hass = MagicMock()
    await s.async_untrack_trip("abc")
    coord.untrack_trip.assert_called_once_with("abc")
