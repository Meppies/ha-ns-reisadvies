"""Coverage for pure helpers in custom_components.ns_reisadvies.__init__."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.ns_reisadvies import (
    _any_coordinator, _cleanup_session, _hub_entry, _live_sessions, _option,
    _resolve_stops, _runtime, _set_stop_state, _set_train_state,
)
from custom_components.ns_reisadvies.const import DOMAIN


def test_option_prefers_options_over_data():
    entry = MagicMock()
    entry.options = {"k": "opt"}
    entry.data = {"k": "data"}
    assert _option(entry, "k", "d") == "opt"


def test_option_falls_back_to_data():
    entry = MagicMock()
    entry.options = {}
    entry.data = {"k": "data"}
    assert _option(entry, "k", "d") == "data"


def test_option_returns_default():
    entry = MagicMock()
    entry.options = {}
    entry.data = {}
    assert _option(entry, "k", "def") == "def"


def test_hub_entry_returns_first():
    e = MagicMock()
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    assert _hub_entry(hass) is e


def test_hub_entry_returns_none_when_empty():
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    assert _hub_entry(hass) is None


def test_runtime_returns_none_without_entry():
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    assert _runtime(hass) is None


def test_runtime_returns_runtime_data():
    e = MagicMock()
    e.runtime_data = "R"
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    assert _runtime(hass) == "R"


def test_live_sessions_uses_runtime_when_available():
    sessions = {"a": 1}
    runtime = MagicMock()
    runtime.live_sessions = sessions
    e = MagicMock()
    e.runtime_data = runtime
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    assert _live_sessions(hass) is sessions


def test_live_sessions_falls_back_to_hass_data():
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    hass.data = {}
    out = _live_sessions(hass)
    assert out == {}
    assert hass.data[DOMAIN]["_live_sessions"] is out


def test_any_coordinator_returns_none_without_runtime():
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    assert _any_coordinator(hass) is None


def test_any_coordinator_returns_first_coord():
    coord = object()
    runtime = MagicMock()
    runtime.coordinators = {"sub1": coord}
    e = MagicMock()
    e.runtime_data = runtime
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    assert _any_coordinator(hass) is coord


def test_any_coordinator_none_when_dict_empty():
    runtime = MagicMock()
    runtime.coordinators = {}
    e = MagicMock()
    e.runtime_data = runtime
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    assert _any_coordinator(hass) is None


def test_resolve_stops_with_explicit_lat_lng():
    stops = [{"name": "Hilversum", "uicCode": "hvs", "lat": 52.0, "lng": 5.0, "passed": True}]
    out = _resolve_stops(stops, {})
    assert out == [{"name": "Hilversum", "lat": 52.0, "lng": 5.0, "uicCode": "HVS", "passed": True}]


def test_resolve_stops_falls_back_to_geo_by_uic():
    geo = {"HVS": {"name": "Hilversum", "lat": 52.2, "lng": 5.18}}
    stops = [{"name": "", "uicCode": "hvs"}]
    out = _resolve_stops(stops, geo)
    assert out[0]["lat"] == 52.2
    assert out[0]["name"] == "Hilversum"


def test_resolve_stops_falls_back_to_geo_by_name():
    geo = {"X": {"name": "Duivendrecht", "lat": 52.3, "lng": 4.9}}
    stops = [{"name": "Duivendrecht"}]
    out = _resolve_stops(stops, geo)
    assert out[0]["lat"] == 52.3


def test_resolve_stops_passed_from_iso_planned():
    stops = [{"name": "X", "uicCode": "X", "lat": 0, "lng": 0, "plannedDepartureDateTime": "2000-01-01T00:00:00+00:00"}]
    out = _resolve_stops(stops, {})
    assert out[0]["passed"] is True


def test_resolve_stops_passed_false_for_future():
    stops = [{"name": "X", "uicCode": "X", "lat": 0, "lng": 0, "plannedDepartureDateTime": "2099-01-01T00:00:00+00:00"}]
    out = _resolve_stops(stops, {})
    assert out[0]["passed"] is False


def test_resolve_stops_invalid_iso_returns_false():
    stops = [{"name": "X", "uicCode": "X", "lat": 0, "lng": 0, "plannedDepartureDateTime": "garbage"}]
    out = _resolve_stops(stops, {})
    assert out[0]["passed"] is False


def test_resolve_stops_handles_empty_list():
    assert _resolve_stops([], {}) == []


def test_set_train_state_writes_state():
    hass = MagicMock()
    pos = {"lat": 52.0, "lng": 5.0, "speed": 88, "heading": 90, "ts": 123}
    _set_train_state(hass, "sensor.x", "Train", pos)
    args, kwargs = hass.states.async_set.call_args
    assert args[0] == "sensor.x"
    assert args[1] == "moving"
    assert args[2]["latitude"] == 52.0
    assert args[2]["speed"] == 88
    assert kwargs["force_update"] is True


def test_set_stop_state_writes_state():
    hass = MagicMock()
    _set_stop_state(hass, "sensor.s", "Stop", 52.0, 5.0)
    args, kwargs = hass.states.async_set.call_args
    assert args[0] == "sensor.s"
    assert args[1] == "station"
    assert args[2]["friendly_name"] == "Stop"


def test_cleanup_session_removes_entities_and_calls_cancel():
    cancel = MagicMock()
    sess = {"train_entity_id": "sensor.t", "stop_entity_ids": ["sensor.s1"], "cleanup": cancel}
    runtime = MagicMock()
    runtime.live_sessions = {"sid": sess}
    e = MagicMock()
    e.runtime_data = runtime
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    _cleanup_session(hass, "sid")
    assert "sid" not in runtime.live_sessions
    hass.states.async_remove.assert_any_call("sensor.t")
    hass.states.async_remove.assert_any_call("sensor.s1")
    cancel.assert_called_once()


def test_cleanup_session_silent_on_missing():
    runtime = MagicMock()
    runtime.live_sessions = {}
    e = MagicMock()
    e.runtime_data = runtime
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    _cleanup_session(hass, "missing")  # should not raise


def test_cleanup_session_swallows_cancel_error():
    cancel = MagicMock(side_effect=RuntimeError("boom"))
    sess = {"cleanup": cancel}
    runtime = MagicMock()
    runtime.live_sessions = {"sid": sess}
    e = MagicMock()
    e.runtime_data = runtime
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [e]
    _cleanup_session(hass, "sid")  # should not raise
