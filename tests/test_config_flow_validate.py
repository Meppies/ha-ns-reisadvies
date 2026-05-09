"""Coverage for the pure _validate_route helper in config_flow."""
from __future__ import annotations

from custom_components.ns_reisadvies.config_flow import _station_selector, _validate_route
from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
)


def test_validate_route_accepts_valid_input():
    user = {CONF_FROM_STATION: "hilversum", CONF_TO_STATION: "duivendrecht"}
    errors = _validate_route(user, [])
    assert errors == {}
    # Normalised to canonical casing.
    assert user[CONF_FROM_STATION] == "Hilversum"
    assert user[CONF_TO_STATION] == "Duivendrecht"


def test_validate_route_unknown_from_station():
    user = {CONF_FROM_STATION: "Atlantis Centraal", CONF_TO_STATION: "Hilversum"}
    errors = _validate_route(user, [])
    assert errors[CONF_FROM_STATION] == "unknown_station"


def test_validate_route_unknown_to_station():
    user = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Atlantis"}
    errors = _validate_route(user, [])
    assert errors[CONF_TO_STATION] == "unknown_station"


def test_validate_route_same_station():
    user = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "hilversum"}
    errors = _validate_route(user, [])
    assert errors["base"] == "same_station"


def test_validate_route_duplicate_unnamed_blocks():
    """Two unnamed routes between the same stations still collide."""
    existing = [("Hilversum", "Duivendrecht", "")]
    user = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    errors = _validate_route(user, existing)
    assert errors["base"] == "duplicate_route"


def test_validate_route_same_stations_different_names_allowed():
    """v2.15.0: name discriminates — two routes between the same stations
    with different names are valid."""
    existing = [("Hilversum", "Duivendrecht", "Werk")]
    user = {
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "Weekend",
    }
    errors = _validate_route(user, existing)
    assert errors == {}


def test_validate_route_same_stations_same_name_blocks():
    """Same stations + same name = duplicate."""
    existing = [("Hilversum", "Duivendrecht", "Werk")]
    user = {
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "werk",  # case-insensitive
    }
    errors = _validate_route(user, existing)
    assert errors["base"] == "duplicate_route"


def test_station_selector_constructs_dropdown():
    sel = _station_selector()
    assert sel is not None
