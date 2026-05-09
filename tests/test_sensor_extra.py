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
