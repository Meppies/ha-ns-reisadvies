"""Tests for the NSReisadviesSensor entity."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.ns_reisadvies.const import DOMAIN
from custom_components.ns_reisadvies.sensor import NSReisadviesSensor


def _stub_coordinator(
    hass, data: list[dict] | None = None, tracked: dict | None = None
):
    """Hand-rolled stub — DataUpdateCoordinator is heavyweight to instantiate
    in unit tests and the sensor only reads three attributes from it."""
    coord = MagicMock()
    coord.hass = hass
    coord.data = data
    coord.tracked_trips = tracked or {}
    coord.last_update_success = True
    return coord


async def test_native_value_no_trips(hass) -> None:
    """When the API returns nothing, the sensor reports 'No trips'."""
    coord = _stub_coordinator(hass, data=None)
    hass.data.setdefault(DOMAIN, {})

    sensor = NSReisadviesSensor(
        coord, name="NS Hilversum -> Duivendrecht", unique_id="hilversum_duivendrecht",
    )
    assert sensor.native_value == "No trips"


async def test_native_value_returns_planned_departure(hass) -> None:
    """The sensor exposes the first leg's plannedDateTime as state."""
    trips = [
        {"legs": [{"origin": {"plannedDateTime": "2026-05-08T08:30:00+02:00"}}]}
    ]
    coord = _stub_coordinator(hass, data=trips)
    hass.data.setdefault(DOMAIN, {})

    sensor = NSReisadviesSensor(
        coord, name="NS Hilversum -> Duivendrecht", unique_id="hilversum_duivendrecht",
    )
    assert sensor.native_value == "2026-05-08T08:30:00+02:00"


async def test_extra_state_attributes_exposes_hub_flags(hass) -> None:
    """Card-relevant hub flags are surfaced via extra_state_attributes."""
    coord = _stub_coordinator(hass, data=[{"legs": []}], tracked={"abc": "ctx"})
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["_live_train_map_enabled"] = True
    hass.data[DOMAIN]["_live_map_refresh_seconds"] = 15

    sensor = NSReisadviesSensor(
        coord, name="NS Hilversum -> Duivendrecht", unique_id="hilversum_duivendrecht",
    )
    attrs = sensor.extra_state_attributes
    assert attrs["live_train_map_enabled"] is True
    assert attrs["live_map_refresh_seconds"] == 15
    assert attrs["tracked_trips"] == ["abc"]
    assert attrs["trips"] == [{"legs": []}]


async def test_extra_state_attributes_defaults(hass) -> None:
    """Missing hub flags default to safe values."""
    coord = _stub_coordinator(hass, data=None)
    hass.data.setdefault(DOMAIN, {})

    sensor = NSReisadviesSensor(
        coord, name="NS Hilversum -> Duivendrecht", unique_id="hilversum_duivendrecht",
    )
    attrs = sensor.extra_state_attributes
    assert attrs["live_train_map_enabled"] is False
    assert attrs["live_map_refresh_seconds"] == 10
    assert attrs["tracked_trips"] == []
