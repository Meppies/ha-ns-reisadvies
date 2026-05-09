"""Tests for v2.15.0 route_name on the sensor entity."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.ns_reisadvies.sensor import NSReisadviesSensor


def _coord_stub() -> MagicMock:
    coord = MagicMock()
    coord.data = []
    coord.tracked_trips = {}
    coord.hass = MagicMock()
    # No live-train-map config entries → defaults flow.
    coord.hass.config_entries.async_entries.return_value = []
    return coord


def test_sensor_with_route_name_uses_name_as_device_name():
    """DeviceInfo.name == route_name when set, so the friendly name in
    HA is the user's chosen label."""
    s = NSReisadviesSensor(
        _coord_stub(),
        from_station="Hilversum",
        to_station="Duivendrecht",
        route_name="Werk",
        unique_id="hilversum_duivendrecht_werk",
        suggested_object_id="ns_werk",
    )
    assert s._attr_device_info["name"] == "Werk"
    assert s._attr_unique_id == "hilversum_duivendrecht_werk"
    assert s._attr_suggested_object_id == "ns_werk"


def test_sensor_without_route_name_keeps_legacy_device_name():
    """No route_name → DeviceInfo.name falls back to "<from> → <to>"."""
    s = NSReisadviesSensor(
        _coord_stub(),
        from_station="Hilversum",
        to_station="Duivendrecht",
        unique_id="hilversum_duivendrecht",
        suggested_object_id="ns_hilversum_duivendrecht",
    )
    assert s._attr_device_info["name"] == "Hilversum → Duivendrecht"
    assert s._route_name is None


def test_sensor_extra_state_attributes_surface_route_name():
    """The card relies on route_name + from_station + to_station being
    surfaced as state attributes so it can render the per-route heading."""
    s = NSReisadviesSensor(
        _coord_stub(),
        from_station="Hilversum",
        to_station="Duivendrecht",
        route_name="Werk",
        unique_id="hilversum_duivendrecht_werk",
        suggested_object_id="ns_werk",
    )
    attrs = s.extra_state_attributes
    assert attrs["route_name"] == "Werk"
    assert attrs["from_station"] == "Hilversum"
    assert attrs["to_station"] == "Duivendrecht"


def test_sensor_extra_state_attributes_route_name_none_for_unnamed():
    """Unnamed routes expose route_name=None so the card can decide to
    skip the heading (default rendering is the HA friendly name)."""
    s = NSReisadviesSensor(
        _coord_stub(),
        from_station="Amsterdam Centraal",
        to_station="Utrecht Centraal",
        unique_id="amsterdam_centraal_utrecht_centraal",
        suggested_object_id="ns_amsterdam_centraal_utrecht_centraal",
    )
    attrs = s.extra_state_attributes
    assert attrs["route_name"] is None
    assert attrs["from_station"] == "Amsterdam Centraal"
    assert attrs["to_station"] == "Utrecht Centraal"
