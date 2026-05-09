"""Extended coverage for NSUpdateCoordinator helpers.

These tests target the asynchronous fetcher methods that the v2.13.0
test pass left uncovered: composition, stations geo, ArcGIS train
position, the full rail-network paginator, the journey-route lookup,
and the tracked-trips merge inside ``_async_update_data``.

Each test stubs ``coord._session`` with a MagicMock that returns a
fake aiohttp response, so nothing here touches the network.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator


def _resp(status, payload=None):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=payload or {})
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


def _make(hass, **kw):
    defaults = {
        "api_key": "k",
        "from_station": "Hilversum",
        "to_station": "Duivendrecht",
        "scan_interval_minutes": 5,
        "fav_hours": 6,
        "fetch_composition": False,
    }
    defaults.update(kw)
    coord = NSUpdateCoordinator(hass, **defaults)
    coord._store = MagicMock()
    coord._store.async_load = AsyncMock(return_value=None)
    coord._store.async_save = AsyncMock()
    return coord


async def test_composition_returns_none_for_empty_train_number(hass):
    coord = _make(hass)
    assert await coord._fetch_journey_composition("", {}) is None


async def test_composition_uses_cache_on_second_call(hass):
    coord = _make(hass)
    coord._composition_cache = {"123": {"trainType": "VIRM"}}
    coord._session = MagicMock()
    coord._session.get = MagicMock()
    out = await coord._fetch_journey_composition("123", {})
    assert out == {"trainType": "VIRM"}
    coord._session.get.assert_not_called()


async def test_composition_success_parses_origin_stop(hass):
    coord = _make(hass)
    payload = {"payload": {"stops": [
        {"status": "PASSED", "actualStock": {}},
        {"status": "ORIGIN", "actualStock": {
            "trainType": "VIRM", "numberOfParts": 2, "numberOfSeats": 200,
            "numberOfFirstClassSeats": 30, "hasSignificantChange": True,
            "trainParts": [
                {"image": {"uri": "https://x/a.png"}, "type": "VIRM-IV", "stockIdentifier": "S1"},
                {"image": {"uri": ""}, "type": "VIRM-VI", "stockIdentifier": "S2"},
            ],
        }},
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))
    out = await coord._fetch_journey_composition("4567", {})
    assert out is not None
    assert out["trainType"] == "VIRM"
    assert out["numberOfParts"] == 2
    assert out["shorter"] is True
    assert len(out["parts"]) == 2
    assert coord._composition_cache["4567"] == out


async def test_composition_first_failure_logs_warning_then_debug(hass, caplog):
    import logging
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(403))
    caplog.set_level(logging.WARNING, logger="custom_components.ns_reisadvies.coordinator")
    assert await coord._fetch_journey_composition("1", {}) is None
    warns = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warns) == 1
    coord._session.get = MagicMock(return_value=_resp(403))
    assert await coord._fetch_journey_composition("2", {}) is None
    warns_after = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warns_after) == 1


async def test_composition_network_error_returns_none(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))
    assert await coord._fetch_journey_composition("99", {}) is None
    assert coord._composition_cache.get("99") is None


async def test_composition_drops_empty_results(hass):
    coord = _make(hass)
    payload = {"payload": {"stops": [{"status": "ORIGIN", "actualStock": {"trainType": "VIRM", "trainParts": []}}]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))
    assert await coord._fetch_journey_composition("0", {}) is None


async def test_annotate_compositions_noop_when_disabled(hass):
    coord = _make(hass, fetch_composition=False)
    trips = [{"legs": [{"product": {"number": 1}}]}]
    await coord._annotate_compositions(trips, {})
    assert "composition" not in trips[0]["legs"][0]


async def test_annotate_compositions_skips_when_no_train_numbers(hass):
    coord = _make(hass, fetch_composition=True)
    trips = [{"legs": [{"product": {}}]}]
    await coord._annotate_compositions(trips, {})
    assert "composition" not in trips[0]["legs"][0]


async def test_annotate_compositions_decorates_legs(hass):
    coord = _make(hass, fetch_composition=True)
    trips = [{"legs": [{"product": {"number": 100}}, {"product": {"number": 200}}]}]
    fake = {"trainType": "VIRM", "parts": [{"image": "x", "type": "VIRM-IV"}]}
    async def _stub(num, headers):
        return fake if num == "100" else None
    coord._fetch_journey_composition = _stub
    await coord._annotate_compositions(trips, {})
    assert trips[0]["legs"][0]["composition"] == fake
    assert "composition" not in trips[0]["legs"][1]

async def test_stations_geo_returns_runtime_cache(hass):
    coord = _make(hass)
    cached = {"HVS": {"name": "Hilversum", "lat": 52.2, "lng": 5.18}}
    runtime = MagicMock()
    runtime.stations_geo = cached
    coord._entry = MagicMock()
    coord._entry.runtime_data = runtime
    out = await coord.async_fetch_stations_geo()
    assert out == cached


async def test_stations_geo_returns_empty_without_api_key(hass):
    coord = _make(hass, api_key="")
    coord._entry = None
    assert await coord.async_fetch_stations_geo() == {}


async def test_stations_geo_returns_empty_on_http_error(hass):
    coord = _make(hass)
    coord._entry = None
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(503))
    assert await coord.async_fetch_stations_geo() == {}


async def test_stations_geo_returns_empty_on_network_error(hass):
    coord = _make(hass)
    coord._entry = None
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("dns"))
    assert await coord.async_fetch_stations_geo() == {}


async def test_stations_geo_parses_payload_and_indexes_by_uic(hass):
    coord = _make(hass)
    coord._entry = None
    payload = {"payload": [
        {"code": "HVS", "UICCode": "8400388",
         "namen": {"lang": "Hilversum", "middel": "Hilversum", "kort": "HVS"},
         "land": "NL", "lat": 52.2256, "lng": 5.1819},
        {"code": "ZZZ", "UICCode": "0000", "namen": {"lang": "Nowhere"}},
        {"namen": {"lang": "Ghost"}, "lat": 0, "lng": 0},
    ]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))
    out = await coord.async_fetch_stations_geo()
    assert "HVS" in out
    assert "8400388" in out
    assert out["HVS"]["name"] == "Hilversum"
    assert out["HVS"]["lat"] == pytest.approx(52.2256)
    assert "ZZZ" not in out


async def test_arcgis_returns_none_for_empty_train_number(hass):
    coord = _make(hass)
    assert await coord.async_fetch_arcgis_position("") is None


async def test_arcgis_returns_none_for_non_numeric(hass):
    coord = _make(hass)
    assert await coord.async_fetch_arcgis_position("not-a-number") is None


async def test_arcgis_success(hass):
    coord = _make(hass)
    payload = {"features": [{"attributes": {
        "treinNummer": 1234, "lat": 52.0, "lng": 5.0, "snelheid": 88,
        "richting": 270, "Tijd": 1700000000000, "Stationsnaam": "Hilversum",
        "type": "VIRM", "ritId": "abc",
    }}]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))
    out = await coord.async_fetch_arcgis_position("1234")
    assert out is not None
    assert out["lat"] == 52.0
    assert out["speed"] == 88
    assert out["source"] == "prorail-obis"


async def test_arcgis_empty_features(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"features": []}))
    assert await coord.async_fetch_arcgis_position("1") is None


async def test_arcgis_lat_missing(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"features": [{"attributes": {"treinNummer": 1, "lng": 5}}]}))
    assert await coord.async_fetch_arcgis_position("1") is None


async def test_arcgis_http_error(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(500))
    assert await coord.async_fetch_arcgis_position("1") is None


async def test_arcgis_network_error(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("net"))
    assert await coord.async_fetch_arcgis_position("1") is None


async def test_rail_network_single_page(hass):
    coord = _make(hass)
    feats = [{"type": "Feature", "geometry": {}, "properties": {}}]
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"features": feats}))
    out = await coord.async_fetch_full_rail_network()
    assert out is not None
    assert out["type"] == "FeatureCollection"
    assert out["features"] == feats


async def test_rail_network_http_error(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(503))
    assert await coord.async_fetch_full_rail_network() is None


async def test_rail_network_network_error(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("net"))
    assert await coord.async_fetch_full_rail_network() is None


async def test_rail_network_empty_features(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"features": []}))
    assert await coord.async_fetch_full_rail_network() is None

async def test_journey_route_empty_without_train_number(hass):
    coord = _make(hass)
    assert await coord.async_fetch_journey_route("") == []


async def test_journey_route_empty_without_api_key(hass):
    coord = _make(hass, api_key="")
    assert await coord.async_fetch_journey_route("100") == []


async def test_journey_route_returns_empty_on_http_error(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(500))
    assert await coord.async_fetch_journey_route("1") == []


async def test_journey_route_returns_empty_on_network_error(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("net"))
    assert await coord.async_fetch_journey_route("1") == []


async def test_journey_route_returns_empty_on_no_stops(hass):
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"payload": {"stops": []}}))
    assert await coord.async_fetch_journey_route("1") == []


async def test_journey_route_success_with_passed_flag(hass):
    coord = _make(hass)
    coord._entry = None
    payload = {"payload": {"stops": [
        {"station": {"uicCode": "8400001", "stationCode": "AAA", "name": "Stop A"},
         "status": "PASSED",
         "actualDepartureDateTime": "2020-01-01T00:00:00+00:00"},
        {"station": {"uicCode": "8400002", "stationCode": "BBB", "name": "Stop B"},
         "status": "STOP",
         "plannedDepartureDateTime": "2099-01-01T00:00:00+00:00"},
        {"station": {"uicCode": "9999999", "stationCode": "ZZZ", "name": "Ghost"}},
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, payload),
        _resp(200, {"payload": [
            {"code": "AAA", "UICCode": "8400001", "namen": {"lang": "Stop A"}, "lat": 52.0, "lng": 4.0},
            {"code": "BBB", "UICCode": "8400002", "namen": {"lang": "Stop B"}, "lat": 52.1, "lng": 4.1},
        ]}),
    ])
    out = await coord.async_fetch_journey_route("100")
    assert len(out) == 2
    assert out[0]["passed"] is True
    assert out[1]["passed"] is False


async def test_update_data_includes_tracked_trips(hass):
    coord = _make(hass)
    coord.tracked_trips = {"FAV1": time.time()}
    normal = {"trips": [{"ctxRecon": "n1", "legs": [{"origin": {"plannedDateTime": "2026-01-01T08:00"}}]}]}
    fav = {"ctxRecon": "FAV1", "legs": [{"origin": {"plannedDateTime": "2026-01-01T09:00"}}]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[_resp(200, normal), _resp(200, fav)])
    out = await coord._async_update_data()
    ctxs = [t["ctxRecon"] for t in out]
    assert "n1" in ctxs and "FAV1" in ctxs


async def test_update_data_drops_gone_tracked_trips(hass):
    coord = _make(hass)
    coord.tracked_trips = {"GONE": time.time()}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[_resp(200, {"trips": []}), _resp(404)])
    await coord._async_update_data()
    assert "GONE" not in coord.tracked_trips


async def test_update_data_dedups_tracked_already_in_normal(hass):
    coord = _make(hass)
    coord.tracked_trips = {"DUP": time.time()}
    trip = {"ctxRecon": "DUP", "legs": [{"origin": {"plannedDateTime": "2026-01-01T08:00"}}]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[_resp(200, {"trips": [trip]}), _resp(200, trip)])
    out = await coord._async_update_data()
    assert sum(1 for t in out if t.get("ctxRecon") == "DUP") == 1


async def test_update_data_unexpected_4xx_raises_update_failed(hass):
    from homeassistant.helpers.update_coordinator import UpdateFailed
    coord = _make(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(418))
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_validate_api_key_unexpected_status(hass):
    from custom_components.ns_reisadvies.coordinator import async_validate_api_key
    from unittest.mock import patch
    fake = MagicMock()
    fake.get = MagicMock(return_value=_resp(418))
    with patch("custom_components.ns_reisadvies.coordinator.async_get_clientsession", return_value=fake):
        assert await async_validate_api_key(hass, "k") == "cannot_connect"


async def test_composition_warned_second_failure_logs_debug(hass, caplog):
    """Second composition failure of same train number with cache hit -> no second warning."""
    import logging
    coord = _make(hass)
    coord._composition_warned = True
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(403))
    caplog.set_level(logging.DEBUG, logger="custom_components.ns_reisadvies.coordinator")
    assert await coord._fetch_journey_composition("x", {}) is None
    debug = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert any("HTTP" in (r.message or "") for r in debug)


async def test_annotate_compositions_skips_legs_without_number(hass):
    coord = _make(hass, fetch_composition=True)
    trips = [{"legs": [{"product": {"number": 100}}, {"product": {}}]}]
    fake = {"trainType": "VIRM", "parts": [{"image": "x", "type": "VIRM-IV"}]}
    async def _stub(num, headers):
        return fake
    coord._fetch_journey_composition = _stub
    await coord._annotate_compositions(trips, {})
    # Leg 0 gets composition; leg 1 skipped (no number).
    assert trips[0]["legs"][0]["composition"] == fake
    assert "composition" not in trips[0]["legs"][1]


async def test_update_data_tracked_trip_network_error_skipped(hass):
    """Network error while fetching a tracked trip -> 'skip' status, kept in tracked_trips."""
    coord = _make(hass)
    coord.tracked_trips = {"FAV1": time.time()}
    coord._session = MagicMock()
    # First GET ok (normal trips), second GET errors
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"trips": []}),
        aiohttp.ClientError("net"),
    ])
    out = await coord._async_update_data()
    # Tracked trip stays (skip != gone)
    assert "FAV1" in coord.tracked_trips
