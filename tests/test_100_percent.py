"""Final push to 100%: static-paths helper + scattered __init__ + coordinator logging."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies import (
    _async_register_static_paths, async_setup_entry,
)
from custom_components.ns_reisadvies.const import DOMAIN
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator


# ---- _async_register_static_paths ----------------------------------------


async def test_static_paths_skip_when_already_registered():
    fake_hass = MagicMock()
    fake_hass.data = {DOMAIN: {"static_paths_registered": True}}
    await _async_register_static_paths(fake_hass)
    fake_hass.config.path.assert_not_called()


async def test_static_paths_skip_when_www_missing():
    fake_hass = MagicMock()
    fake_hass.data = {DOMAIN: {}}
    fake_hass.config.path.return_value = "/nonexistent"
    with patch("custom_components.ns_reisadvies.os.path.isdir", return_value=False):
        await _async_register_static_paths(fake_hass)
    fake_hass.http.async_register_static_paths.assert_not_called()


async def test_static_paths_happy_path():
    fake_hass = MagicMock()
    fake_hass.data = {DOMAIN: {}}
    fake_hass.config.path.return_value = "/exists"
    fake_hass.http.async_register_static_paths = AsyncMock()
    integration = MagicMock(); integration.version = "2.13.7"
    with patch("custom_components.ns_reisadvies.os.path.isdir", return_value=True), \
         patch("custom_components.ns_reisadvies.async_get_integration", new=AsyncMock(return_value=integration)), \
         patch("custom_components.ns_reisadvies._async_register_card_resource", new=AsyncMock()) as mock_card:
        await _async_register_static_paths(fake_hass)
    fake_hass.http.async_register_static_paths.assert_called_once()
    assert fake_hass.data[DOMAIN]["static_paths_registered"] is True
    assert fake_hass.data[DOMAIN]["card_url_registered"] is True
    mock_card.assert_called_once_with(fake_hass, "2.13.7")


async def test_static_paths_integration_lookup_failure_uses_default_version():
    fake_hass = MagicMock()
    fake_hass.data = {DOMAIN: {}}
    fake_hass.config.path.return_value = "/exists"
    fake_hass.http.async_register_static_paths = AsyncMock()
    with patch("custom_components.ns_reisadvies.os.path.isdir", return_value=True), \
         patch("custom_components.ns_reisadvies.async_get_integration", side_effect=RuntimeError("x")), \
         patch("custom_components.ns_reisadvies._async_register_card_resource", new=AsyncMock()) as mock_card:
        await _async_register_static_paths(fake_hass)
    mock_card.assert_called_once_with(fake_hass, "0")


# ---- coordinator: defensive logging branches -----------------------------


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


async def test_composition_first_failure_warns_then_subsequent_failure_debug(hass):
    """One warning, multiple debug for further failures (line 246)."""
    import logging
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(503))
    coord._composition_warned = False
    # First call: warns
    assert await coord._fetch_journey_composition("a", {}) is None
    # Second call (different train) with warned_once set -> debug branch
    assert await coord._fetch_journey_composition("b", {}) is None


async def test_update_data_tracked_trip_skip_branch(hass):
    """HTTP 500 on tracked-trip fetch -> 'skip' status (line 404)."""
    import time
    coord = _coord(hass)
    coord.tracked_trips = {"FAV1": time.time()}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"trips": []}),
        _resp(500),
    ])
    out = await coord._async_update_data()
    assert "FAV1" in coord.tracked_trips  # Still kept


async def test_update_data_with_composition_calls_annotate(hass):
    """fetch_composition=True triggers _annotate_compositions (line 443)."""
    coord = _coord(hass, fetch_composition=True)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"trips": [{"ctxRecon": "a", "legs": [{"product": {"number": 100}, "origin": {"plannedDateTime": "2026-01-01T00:00"}}]}]}),
        _resp(200, {"payload": {"stops": [{"status": "ORIGIN", "actualStock": {"trainType": "VIRM", "trainParts": [{"image": {"uri": "x"}, "type": "VIRM-IV"}]}}]}}),
    ])
    out = await coord._async_update_data()
    assert out[0]["legs"][0].get("composition") is not None


async def test_rail_network_pagination_continues_to_second_page(hass):
    """First page full (2000 features) -> request second page (lines 551-557)."""
    coord = _coord(hass)
    coord._session = MagicMock()
    page1 = {"features": [{"x": i} for i in range(2000)]}
    page2 = {"features": [{"y": 1}]}  # less than page_size -> exit
    coord._session.get = MagicMock(side_effect=[_resp(200, page1), _resp(200, page2)])
    out = await coord.async_fetch_full_rail_network()
    assert out is not None
    assert len(out["features"]) == 2001


async def test_journey_route_status_departed_passed(hass):
    """Status DEPARTED -> passed=True (line 657 branch)."""
    coord = _coord(hass)
    coord._entry = None
    payload = {"payload": {"stops": [
        {"station": {"uicCode": "AAA", "name": "A"}, "status": "DEPARTED"},
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, payload),
        _resp(200, {"payload": [{"code": "AAA", "UICCode": "AAA", "namen": {"lang": "A"}, "lat": 52, "lng": 4}]}),
    ])
    out = await coord.async_fetch_journey_route("100")
    assert out[0]["passed"] is True


async def test_journey_route_invalid_iso_no_passed(hass):
    """Invalid ISO timestamps -> stays not-passed (line 670-671 branch)."""
    coord = _coord(hass)
    coord._entry = None
    payload = {"payload": {"stops": [
        {"station": {"uicCode": "AAA", "name": "A"}, "status": "",
         "actualDepartureDateTime": "garbage",
         "plannedDepartureDateTime": "also-garbage"},
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, payload),
        _resp(200, {"payload": [{"code": "AAA", "UICCode": "AAA", "namen": {"lang": "A"}, "lat": 52, "lng": 4}]}),
    ])
    out = await coord.async_fetch_journey_route("100")
    assert out[0]["passed"] is False


async def test_live_train_response_text_capture_on_5xx(hass):
    """5xx on first vehicle URL captures response text body (lines 775-776)."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(503, text_payload="upstream error details here"),
        _resp(503, text_payload="fallback also down"),
        _resp(200, {"payload": {}}),  # station-based, no station
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is None


async def test_live_train_logs_when_already_warned_once(hass):
    """warned_once=True -> debug logs instead of warnings (lines 832, 851-858)."""
    coord = _coord(hass)
    coord.hass.data.setdefault(DOMAIN, {})["_live_train_warned"] = True
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(503),
        _resp(503),
        _resp(200, {"payload": {}}),
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is None
