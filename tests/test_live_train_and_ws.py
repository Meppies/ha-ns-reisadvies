"""Coverage for the station fallback, WS handlers, rail cache, card resource."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator
import asyncio

async def _run_ws(handler, hass, conn, msg):
    """Invoke a @async_response WS handler and await its scheduled coroutine."""
    coros = []
    hass.async_create_task = lambda coro, **kw: coros.append(coro) or MagicMock()
    handler(hass, conn, msg)
    if coros:
        await coros[0]



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


async def test_station_based_no_api_key(hass):
    c = _coord(hass, api_key="")
    assert await c._async_station_based_position("100") is None


async def test_station_based_http_error(hass):
    c = _coord(hass)
    c._session = MagicMock()
    c._session.get = MagicMock(return_value=_resp(500))
    assert await c._async_station_based_position("100") is None


async def test_station_based_no_station_code(hass):
    c = _coord(hass)
    c._session = MagicMock()
    c._session.get = MagicMock(return_value=_resp(200, {"payload": {}}))
    assert await c._async_station_based_position("100") is None


async def test_station_based_unknown_station(hass):
    c = _coord(hass)
    c._entry = None
    c._session = MagicMock()
    c._session.get = MagicMock(side_effect=[
        _resp(200, {"payload": {"station": "ZZZ"}}),
        _resp(200, {"payload": []}),
    ])
    assert await c._async_station_based_position("100") is None


async def test_station_based_with_anchor(hass):
    c = _coord(hass)
    c._entry = None
    c._session = MagicMock()
    c._session.get = MagicMock(side_effect=[
        _resp(200, {"payload": {"station": "HVS", "spoor": "5"}}),
        _resp(200, {"payload": [{"code": "HVS", "UICCode": "8400388", "namen": {"lang": "Hilversum"}, "lat": 52.2, "lng": 5.1}]}),
    ])
    out = await c._async_station_based_position("100", anchor_iso="2026-04-30T08:25:00+0200")
    assert out is not None
    assert out["station_code"] == "HVS"
    assert out["spoor"] == "5"














def test_arm_cleanup_replaces_existing():
    from custom_components.ns_reisadvies import _arm_cleanup
    cancel_old = MagicMock()
    sess = {"cleanup": cancel_old}
    runtime = MagicMock(); runtime.live_sessions = {"sid": sess}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    cancel_new = MagicMock()
    with patch("custom_components.ns_reisadvies.async_call_later", return_value=cancel_new):
        _arm_cleanup(fake_hass, "sid", seconds=300)
    cancel_old.assert_called_once()
    assert sess["cleanup"] is cancel_new


def test_arm_cleanup_silent_when_missing():
    from custom_components.ns_reisadvies import _arm_cleanup
    runtime = MagicMock(); runtime.live_sessions = {}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    with patch("custom_components.ns_reisadvies.async_call_later", return_value=lambda: None):
        _arm_cleanup(fake_hass, "missing")


async def test_rail_cache_skips_when_fresh(tmp_path):
    from custom_components.ns_reisadvies import _async_refresh_rail_cache
    target_dir = tmp_path / "www"; target_dir.mkdir()
    (target_dir / "rail.geojson").write_text("{}")
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = str(target_dir)
    coord = MagicMock(); coord.async_fetch_full_rail_network = AsyncMock(return_value=None)
    await _async_refresh_rail_cache(fake_hass, coord, force=False)
    coord.async_fetch_full_rail_network.assert_not_called()


async def test_rail_cache_writes_when_forced(tmp_path):
    from custom_components.ns_reisadvies import _async_refresh_rail_cache
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = str(tmp_path / "www")
    fake_hass.async_add_executor_job = AsyncMock()
    coord = MagicMock()
    coord.async_fetch_full_rail_network = AsyncMock(return_value={"type": "FeatureCollection", "features": [{}]})
    await _async_refresh_rail_cache(fake_hass, coord, force=True)
    coord.async_fetch_full_rail_network.assert_called_once()
    fake_hass.async_add_executor_job.assert_called_once()


async def test_rail_cache_skips_on_none_data(tmp_path):
    from custom_components.ns_reisadvies import _async_refresh_rail_cache
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = str(tmp_path / "x")
    fake_hass.async_add_executor_job = AsyncMock()
    coord = MagicMock(); coord.async_fetch_full_rail_network = AsyncMock(return_value=None)
    await _async_refresh_rail_cache(fake_hass, coord, force=True)
    fake_hass.async_add_executor_job.assert_not_called()


async def test_register_card_resource_calls_add_extra_js():
    from custom_components.ns_reisadvies import _async_register_card_resource
    fake_hass = MagicMock(); fake_hass.data = {}
    with patch("custom_components.ns_reisadvies.add_extra_js_url") as mock_js:
        await _async_register_card_resource(fake_hass, "1.0")
    mock_js.assert_called_once()


async def test_register_card_resource_creates_when_missing():
    from custom_components.ns_reisadvies import _async_register_card_resource
    resources = MagicMock(); resources.loaded = True
    resources.async_items = MagicMock(return_value=[])
    resources.async_create_item = AsyncMock()
    lov_data = MagicMock(); lov_data.resources = resources
    fake_hass = MagicMock()
    fake_hass.data = MagicMock()
    fake_hass.data.get = MagicMock(return_value=lov_data)
    with patch("custom_components.ns_reisadvies.add_extra_js_url"):
        await _async_register_card_resource(fake_hass, "1.0")
    resources.async_create_item.assert_called_once()


async def test_register_card_resource_updates_when_url_changed():
    from custom_components.ns_reisadvies import _async_register_card_resource, CARD_URL
    resources = MagicMock(); resources.loaded = False
    resources.async_load = AsyncMock()
    existing = {"id": "abc", "url": f"{CARD_URL}?v=old", "type": "module"}
    resources.async_items = MagicMock(return_value=[existing])
    resources.async_update_item = AsyncMock()
    lov_data = MagicMock(); lov_data.resources = resources
    fake_hass = MagicMock()
    fake_hass.data = MagicMock()
    fake_hass.data.get = MagicMock(return_value=lov_data)
    with patch("custom_components.ns_reisadvies.add_extra_js_url"):
        await _async_register_card_resource(fake_hass, "new")
    resources.async_load.assert_called_once()
    resources.async_update_item.assert_called_once()
