"""Cover WS handlers via __wrapped__ (bypassing @async_response decorator)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ns_reisadvies import (
    _ws_track_train_poll, _ws_track_train_start, _ws_track_train_stop,
)

start_inner = _ws_track_train_start.__wrapped__  # type: ignore[attr-defined]
poll_inner = _ws_track_train_poll.__wrapped__  # type: ignore[attr-defined]


async def test_ws_start_no_hub_sends_error():
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = []
    conn = MagicMock()
    msg = {"id": 1, "train_number": "100"}
    await start_inner(fake_hass, conn, msg)
    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "no_hub"


async def test_ws_start_happy_path_sends_result():
    coord = MagicMock()
    coord.async_fetch_stations_geo = AsyncMock(return_value={})
    coord.async_fetch_journey_route = AsyncMock(return_value=[])
    coord.async_fetch_arcgis_position = AsyncMock(return_value={"lat": 52, "lng": 5, "speed": 88, "heading": 90, "ts_ms": 1})
    runtime = MagicMock(); runtime.coordinators = {"sub": coord}; runtime.live_sessions = {}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    conn = MagicMock()
    msg = {"id": 1, "train_number": "100", "stops": [{"name": "Hilversum", "uicCode": "HVS", "lat": 52.2, "lng": 5.1, "passed": False}]}
    with patch("custom_components.ns_reisadvies.async_call_later", return_value=lambda: None):
        await start_inner(fake_hass, conn, msg)
    conn.send_result.assert_called_once()
    assert "session_id" in conn.send_result.call_args[0][1]


async def test_ws_start_journey_richer_than_leg_merges_passed_flags():
    coord = MagicMock()
    coord.async_fetch_stations_geo = AsyncMock(return_value={})
    coord.async_fetch_journey_route = AsyncMock(return_value=[
        {"name": "A", "uicCode": "A", "lat": 52, "lng": 5, "passed": False},
        {"name": "HVS", "uicCode": "HVS", "lat": 52.2, "lng": 5.1, "passed": False},
        {"name": "C", "uicCode": "C", "lat": 52.3, "lng": 5.2, "passed": False},
    ])
    coord.async_fetch_arcgis_position = AsyncMock(return_value=None)
    runtime = MagicMock(); runtime.coordinators = {"sub": coord}; runtime.live_sessions = {}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    conn = MagicMock()
    msg = {"id": 1, "train_number": "100", "stops": [{"uicCode": "HVS", "lat": 52.2, "lng": 5.1, "passed": True}]}
    with patch("custom_components.ns_reisadvies.async_call_later", return_value=lambda: None):
        await start_inner(fake_hass, conn, msg)
    conn.send_result.assert_called_once()
    result = conn.send_result.call_args[0][1]
    # Journey merged with leg passed flag.
    hvs = next((s for s in result["stops"] if s["uicCode"] == "HVS"), None)
    assert hvs is not None and hvs["passed"] is True


async def test_ws_poll_unknown_session():
    runtime = MagicMock(); runtime.live_sessions = {}; runtime.coordinators = {"s": MagicMock()}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    conn = MagicMock()
    await poll_inner(fake_hass, conn, {"id": 1, "session_id": "missing"})
    assert conn.send_error.call_args[0][1] == "unknown_session"


async def test_ws_poll_no_coord():
    runtime = MagicMock(); runtime.live_sessions = {"sid": {"train_number": "100", "train_entity_id": "x"}}; runtime.coordinators = {}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    conn = MagicMock()
    await poll_inner(fake_hass, conn, {"id": 1, "session_id": "sid"})
    assert conn.send_error.call_args[0][1] == "no_hub"


async def test_ws_poll_happy_returns_position():
    coord = MagicMock()
    coord.async_fetch_arcgis_position = AsyncMock(return_value={"lat": 52, "lng": 5, "speed": 88, "heading": 90, "ts_ms": 1})
    runtime = MagicMock(); runtime.live_sessions = {"sid": {"train_number": "100", "train_entity_id": "device_tracker.x"}}; runtime.coordinators = {"sub": coord}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    conn = MagicMock()
    with patch("custom_components.ns_reisadvies.async_call_later", return_value=lambda: None):
        await poll_inner(fake_hass, conn, {"id": 1, "session_id": "sid"})
    conn.send_result.assert_called_once()
    assert conn.send_result.call_args[0][1]["train_position"]["lat"] == 52


async def test_ws_poll_happy_no_position():
    coord = MagicMock()
    coord.async_fetch_arcgis_position = AsyncMock(return_value=None)
    runtime = MagicMock(); runtime.live_sessions = {"sid": {"train_number": "100", "train_entity_id": "x"}}; runtime.coordinators = {"sub": coord}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    conn = MagicMock()
    with patch("custom_components.ns_reisadvies.async_call_later", return_value=lambda: None):
        await poll_inner(fake_hass, conn, {"id": 1, "session_id": "sid"})
    conn.send_result.assert_called_once()
    assert conn.send_result.call_args[0][1]["train_position"] is None


def test_ws_stop_calls_cleanup_and_returns_ok():
    runtime = MagicMock(); runtime.live_sessions = {"sid": {"train_entity_id": "x", "stop_entity_ids": []}}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    conn = MagicMock()
    _ws_track_train_stop(fake_hass, conn, {"id": 1, "session_id": "sid"})
    conn.send_result.assert_called_once_with(1, {"ok": True})
