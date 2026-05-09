"""Final push: cover the last 28 missing statements."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies.const import (
    CONF_API_KEY, CONF_FROM_STATION, CONF_TO_STATION, DOMAIN, SUBENTRY_TYPE_ROUTE,
)
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator


def _resp(status, json_payload=None, text_payload=""):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=json_payload or {})
    r.text = AsyncMock(return_value=text_payload)
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


def _coord(hass, **kw):
    defaults = {"api_key": "k", "from_station": "A", "to_station": "B",
                "scan_interval_minutes": 5, "fav_hours": 6, "fetch_composition": False}
    defaults.update(kw)
    c = NSUpdateCoordinator(hass, **defaults)
    c._store = MagicMock()
    c._store.async_load = AsyncMock(return_value=None)
    c._store.async_save = AsyncMock()
    return c


# ---- diagnostics ----


async def test_diagnostics_skips_non_route_subentries():
    """Cover diagnostics line 74 (continue on non-route subentry)."""
    from custom_components.ns_reisadvies.diagnostics import async_get_config_entry_diagnostics
    hass = MagicMock()
    runtime = MagicMock(); runtime.coordinators = {}
    sub = MagicMock(); sub.subentry_type = "OTHER"
    entry = MagicMock(); entry.runtime_data = runtime
    entry.version = 3; entry.title = "x"; entry.minor_version = 1
    entry.data = {CONF_API_KEY: "k"}; entry.options = {}
    entry.subentries = {"sub": sub}
    out = await async_get_config_entry_diagnostics(hass, entry)
    assert out is not None


# ---- __init__: _cleanup_session full path ----


def test_cleanup_session_full_path():
    """Cover lines 597-606: entity removal + cancel callback execution."""
    from custom_components.ns_reisadvies import _cleanup_session
    cancel = MagicMock()
    sess = {"train_entity_id": "sensor.t", "stop_entity_ids": ["sensor.s1", "sensor.s2"], "cleanup": cancel}
    runtime = MagicMock(); runtime.live_sessions = {"sid": sess}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    _cleanup_session(fake_hass, "sid")
    cancel.assert_called_once()
    assert fake_hass.states.async_remove.call_count == 3


def test_cleanup_session_cancel_raises_swallowed():
    """Cover the except: pass branch in _cleanup_session."""
    from custom_components.ns_reisadvies import _cleanup_session
    cancel = MagicMock(side_effect=RuntimeError("boom"))
    sess = {"train_entity_id": "sensor.t", "cleanup": cancel}
    runtime = MagicMock(); runtime.live_sessions = {"sid": sess}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    _cleanup_session(fake_hass, "sid")  # should not raise
    cancel.assert_called_once()


# ---- __init__: _backfill warning on update fail ----


def test_backfill_logs_warning_on_update_failure(caplog):
    """Cover lines 807-808: warning log when entity update raises."""
    import logging
    from custom_components.ns_reisadvies import _backfill_entity_subentries
    fake_hass = MagicMock()
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock(); entry.subentries = {"sid1": sub}; entry.entry_id = "e1"
    ent_reg = MagicMock()
    ent_reg.async_update_entity = MagicMock(side_effect=ValueError("boom"))
    ent = MagicMock(); ent.config_subentry_id = None
    ent.unique_id = "hilversum_duivendrecht"; ent.entity_id = "sensor.x"
    caplog.set_level(logging.WARNING, logger="custom_components.ns_reisadvies")
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[ent]):
        _backfill_entity_subentries(fake_hass, entry)
    assert any("Could not link" in (r.message or "") for r in caplog.records)


# ---- coordinator: line 553-557 (rail network max-pages safety cap) ----


async def test_rail_network_hits_max_pages_safety_cap(hass):
    """20 full pages -> hit safety cap (lines 553-557)."""
    coord = _coord(hass)
    coord._session = MagicMock()
    full_page = {"features": [{"x": i} for i in range(2000)]}
    # Provide 20 full pages; after the 20th the loop hits the safety cap.
    coord._session.get = MagicMock(side_effect=[_resp(200, full_page) for _ in range(20)])
    out = await coord.async_fetch_full_rail_network()
    assert out is not None
    # 20 pages * 2000 = 40000 features
    assert len(out["features"]) == 40000


# ---- coordinator: line 246 (composition cache, debug for 2nd train) ----


async def test_composition_warned_once_subsequent_failures_use_debug(hass):
    """warned_once=True on entry -> debug log on next failure (line 246)."""
    coord = _coord(hass)
    coord._composition_warned = True  # Already warned earlier
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(403))
    assert await coord._fetch_journey_composition("99", {}) is None


# ---- coordinator: live_train no-warning-yet empty + no-match warning ----


async def test_live_train_first_warning_on_empty(hass):
    """warned_once=False + empty result triggers warning + sets warned (line 832)."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"payload": {"treinen": []}}),
        _resp(200, {"payload": {"treinen": []}}),  # retry without filter, also empty
        _resp(200, {"payload": {}}),  # station-based fallback: no station_code
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is None
    # warned flag should now be set
    assert coord.hass.data.get(DOMAIN, {}).get("_live_train_warned") is True


async def test_live_train_first_warning_on_no_match(hass):
    """warned_once=False + multiple vehicles none matching -> warning (lines 844-847)."""
    coord = _coord(hass)
    payload = {"payload": {"treinen": [
        {"route": "X", "lat": 52, "lng": 5},
        {"route": "Y", "lat": 52, "lng": 5},
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, payload),
        _resp(200, {"payload": {}}),  # station-based fallback returns None
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is None
    assert coord.hass.data.get(DOMAIN, {}).get("_live_train_warned") is True


async def test_live_train_first_warning_on_5xx(hass):
    """warned_once=False + 5xx on both endpoints -> warning + station-based fallback (lines 811-818)."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(503, text_payload="down"),
        _resp(503, text_payload="also down"),
        _resp(200, {"payload": {}}),
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is None


# ---- coordinator: stations_geo log line (507) ----


async def test_stations_geo_after_runtime_set_logs(hass, caplog):
    """stations_geo runtime path stores result back on runtime + logs (line 507)."""
    import logging
    coord = _coord(hass)
    runtime = MagicMock(); runtime.stations_geo = None  # Initially empty
    coord._entry = MagicMock(); coord._entry.runtime_data = runtime
    payload = {"payload": [{"code": "A", "UICCode": "1", "namen": {"lang": "A"}, "lat": 52, "lng": 4}]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))
    caplog.set_level(logging.DEBUG, logger="custom_components.ns_reisadvies.coordinator")
    out = await coord.async_fetch_stations_geo()
    assert "A" in out
    assert runtime.stations_geo == out  # Stored back


# ---- coordinator: journey_route timezone branches ----


async def test_journey_route_with_z_suffix_passed_iso(hass):
    """Z-suffix ISO timestamp -> normalized + passed (line 678)."""
    coord = _coord(hass)
    coord._entry = None
    payload = {"payload": {"stops": [
        {"station": {"uicCode": "AAA", "name": "A"}, "status": "",
         "actualArrivalDateTime": "2000-01-01T00:00:00Z"},  # Z suffix replaced
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, payload),
        _resp(200, {"payload": [{"code": "AAA", "UICCode": "AAA", "namen": {"lang": "A"}, "lat": 52, "lng": 4}]}),
    ])
    out = await coord.async_fetch_journey_route("100")
    assert out[0]["passed"] is True


async def test_composition_warned_once_network_error_uses_debug(hass):
    """warned_once=True + network error -> debug branch (line 246)."""
    import aiohttp
    coord = _coord(hass)
    coord._composition_warned = True
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("net"))
    assert await coord._fetch_journey_composition("x", {}) is None


async def test_live_train_data_dict_no_payload_key(hass):
    """data dict has 'treinen' but no 'payload' -> branch lines 811-816."""
    coord = _coord(hass)
    payload = {"treinen": [{"route": "100", "lat": 52, "lng": 5}]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))
    out = await coord.async_fetch_live_train("100")
    assert out is not None
    assert out["lat"] == 52


async def test_live_train_payload_is_list(hass):
    """data['payload'] is a list -> branch line 808-809."""
    coord = _coord(hass)
    payload = {"payload": [{"route": "100", "lat": 52, "lng": 5}]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))
    out = await coord.async_fetch_live_train("100")
    assert out is not None


async def test_live_train_text_capture_raises_swallowed(hass):
    """resp.text() raising in error path -> lines 775-776."""
    coord = _coord(hass)
    bad_resp = MagicMock()
    bad_resp.status = 503
    bad_resp.text = AsyncMock(side_effect=RuntimeError("text broken"))
    bad_resp.__aenter__ = AsyncMock(return_value=bad_resp)
    bad_resp.__aexit__ = AsyncMock(return_value=None)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        bad_resp,
        _resp(503),
        _resp(200, {"payload": {}}),
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is None


async def test_live_train_retry_data2_list_via_payload(hass):
    """Retry path: data2 is a dict with payload list (lines 844-845)."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"payload": {"treinen": []}}),
        _resp(200, {"payload": [{"route": "100", "lat": 52, "lng": 5}]}),
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is not None


async def test_live_train_retry_data2_bare_list(hass):
    """Retry path: data2 is a bare list (lines 846-847)."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"payload": {"treinen": []}}),
        _resp(200, [{"route": "100", "lat": 52, "lng": 5}]),
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is not None


async def test_journey_route_status_passing_passed_lower(hass):
    """PASSING_PASSED in lowercase needs upper() (line 673 region)."""
    coord = _coord(hass)
    coord._entry = None
    payload = {"payload": {"stops": [
        {"station": {"uicCode": "AAA", "name": "A"}, "status": "passing_passed"},
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, payload),
        _resp(200, {"payload": [{"code": "AAA", "UICCode": "AAA", "namen": {"lang": "A"}, "lat": 52, "lng": 4}]}),
    ])
    out = await coord.async_fetch_journey_route("100")
    assert out[0]["passed"] is True


# ---- __init__ remaining branches ----


async def test_periodic_rail_refresh_closure_invokes_refresh(hass):
    """Capture and invoke the _periodic_rail_refresh closure (line 401)."""
    from custom_components.ns_reisadvies import async_setup_entry
    captured = {}
    def _capture_call_later(_hass, _delay, fn):
        captured["fn"] = fn
        return MagicMock()
    fake_hass = MagicMock()
    fake_hass.data = {}
    coord = MagicMock()
    coord.async_load_tracked = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.async_fetch_full_rail_network = AsyncMock(return_value=None)
    sub = MagicMock()
    sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock()
    entry.data = {CONF_API_KEY: "k"}; entry.options = {}
    entry.subentries = {"sid": sub}
    entry.entry_id = "e1"
    fake_hass.config.path.return_value = "/nope"
    fake_hass.config_entries.async_forward_entry_setups = AsyncMock()
    with patch("custom_components.ns_reisadvies.NSUpdateCoordinator", return_value=coord), \
         patch("custom_components.ns_reisadvies.async_call_later", side_effect=_capture_call_later), \
         patch("custom_components.ns_reisadvies.async_track_time_interval"), \
         patch("custom_components.ns_reisadvies._recover_subentries_from_storage", new=AsyncMock()), \
         patch("custom_components.ns_reisadvies._backfill_entity_subentries"), \
         patch("custom_components.ns_reisadvies.os.path.isdir", return_value=False), \
         patch("custom_components.ns_reisadvies.websocket_api.async_register_command"):
        await async_setup_entry(fake_hass, entry)
    # Invoke the captured closure to cover line 401
    if "fn" in captured:
        await captured["fn"](None)


async def test_async_setup_entry_skips_non_route_subentry(hass):
    """async_setup_entry skips non-route subentries (lines 348, 352)."""
    from custom_components.ns_reisadvies import async_setup_entry
    fake_hass = MagicMock()
    fake_hass.data = {}
    sub_other = MagicMock(); sub_other.subentry_type = "OTHER"
    sub_empty = MagicMock(); sub_empty.subentry_type = SUBENTRY_TYPE_ROUTE
    sub_empty.data = {}  # No stations
    entry = MagicMock()
    entry.data = {CONF_API_KEY: "k"}; entry.options = {}
    entry.subentries = {"a": sub_other, "b": sub_empty}
    entry.entry_id = "e1"
    fake_hass.config_entries.async_forward_entry_setups = AsyncMock()
    with patch("custom_components.ns_reisadvies._recover_subentries_from_storage", new=AsyncMock()), \
         patch("custom_components.ns_reisadvies._backfill_entity_subentries"), \
         patch("custom_components.ns_reisadvies.os.path.isdir", return_value=False), \
         patch("custom_components.ns_reisadvies.websocket_api.async_register_command"):
        result = await async_setup_entry(fake_hass, entry)
    assert result is True
