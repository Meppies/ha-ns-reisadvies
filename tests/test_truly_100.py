"""Cover the very last 12 missing statements."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ns_reisadvies.const import (
    CONF_API_KEY, CONF_FROM_STATION, CONF_TO_STATION, DOMAIN, SUBENTRY_TYPE_ROUTE,
)


def _resp(status, json_payload=None, text_payload=""):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=json_payload or {})
    r.text = AsyncMock(return_value=text_payload)
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


# ---- __init__.py 160: migrate v2->v3 info log line ----


async def test_migrate_v2_logs_info_line():
    from custom_components.ns_reisadvies import async_migrate_entry
    fake_hass = MagicMock()
    fake_hass.config_entries.async_update_entry = MagicMock()
    entry = MagicMock()
    entry.version = 2; entry.entry_id = "e1"
    entry.data = {CONF_API_KEY: "k"}; entry.options = {}
    assert await async_migrate_entry(fake_hass, entry) is True


# ---- __init__.py 283: 2-part fallback in recover_subentries ----


async def test_recover_subentries_two_part_fallback():
    """File like 'ns_reisadvies_tracked_trips_Foo_Bar' where neither half is a known station."""
    from custom_components.ns_reisadvies import _recover_subentries_from_storage
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = "/storage"
    fake_hass.async_add_executor_job = AsyncMock(return_value=[
        "ns_reisadvies_tracked_trips_Foo_Bar",
    ])
    fake_hass.config_entries.async_add_subentry = MagicMock()
    entry = MagicMock(); entry.subentries = {}
    await _recover_subentries_from_storage(fake_hass, entry)
    fake_hass.config_entries.async_add_subentry.assert_called_once()


# ---- __init__.py 503: tzinfo replace in _resolve_stops ----


def test_resolve_stops_naive_iso_gets_utc_tzinfo():
    """Naive ISO timestamp gets tzinfo=UTC applied (line 503)."""
    from custom_components.ns_reisadvies import _resolve_stops
    stops = [{"name": "X", "uicCode": "X", "lat": 0, "lng": 0,
              "plannedDepartureDateTime": "2000-01-01T00:00:00"}]  # naive, no tz
    out = _resolve_stops(stops, {})
    assert out[0]["passed"] is True


# ---- __init__.py 600-601: _cleanup_session except branch ----


def test_cleanup_session_real_callable_raises():
    """Use a real callable that raises -> hits except branch (lines 600-601)."""
    from custom_components.ns_reisadvies import _cleanup_session
    def _raises():
        raise RuntimeError("boom")
    sess = {"train_entity_id": "sensor.t", "cleanup": _raises}
    runtime = MagicMock(); runtime.live_sessions = {"sid": sess}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    _cleanup_session(fake_hass, "sid")  # should not raise


# ---- __init__.py 605-606: _arm_cleanup _fire closure body ----


def test_arm_cleanup_fire_closure_invokes_cleanup():
    """Capture _fire from async_call_later and invoke -> covers 605-606."""
    from custom_components.ns_reisadvies import _arm_cleanup
    sess = {"train_entity_id": "sensor.t"}
    runtime = MagicMock(); runtime.live_sessions = {"sid": sess}
    e = MagicMock(); e.runtime_data = runtime
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = [e]
    captured = {}
    def _capture(_hass, _seconds, fn):
        captured["fire"] = fn
        return MagicMock()
    with patch("custom_components.ns_reisadvies.async_call_later", side_effect=_capture):
        _arm_cleanup(fake_hass, "sid")
    assert "fire" in captured
    captured["fire"](None)  # invoke the @callback _fire


# ---- __init__.py 807-808: rail cache OSError on stat ----




# ---- coordinator 673: journey_route ts.replace('Z',...) on Z-suffix ----
# Already tested in test_final_100.test_journey_route_with_z_suffix_passed_iso
# but apparently doesn't hit 673. The line 673 is `parsed = parsed.replace(tzinfo=timezone.utc)`
# which only fires when fromisoformat result has tzinfo=None. Let me write a more
# targeted test that uses a naive ISO (no Z, no offset).


async def test_journey_route_naive_iso_gets_utc(hass):
    from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator
    coord = NSUpdateCoordinator(
        hass, api_key="k", from_station="A", to_station="B",
        scan_interval_minutes=5, fav_hours=6, fetch_composition=False,
    )
    coord._store = MagicMock()
    coord._store.async_load = AsyncMock(return_value=None)
    coord._entry = None
    payload = {"payload": {"stops": [
        {"station": {"uicCode": "AAA", "name": "A"}, "status": "",
         "actualArrivalDateTime": "2000-01-01T00:00:00"},  # NAIVE: no tz
    ]}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, payload),
        _resp(200, {"payload": [{"code": "AAA", "UICCode": "AAA", "namen": {"lang": "A"}, "lat": 52, "lng": 4}]}),
    ])
    out = await coord.async_fetch_journey_route("100")
    assert out[0]["passed"] is True


# ---- coordinator 818: live_train data is non-dict non-list (e.g. None) ----


async def test_live_train_data_is_string_falls_to_else(hass):
    """data is a string (not dict, not list) -> vehicles = [] branch (line 818)."""
    from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator
    coord = NSUpdateCoordinator(
        hass, api_key="k", from_station="A", to_station="B",
        scan_interval_minutes=5, fav_hours=6, fetch_composition=False,
    )
    coord._store = MagicMock(); coord._store.async_load = AsyncMock(return_value=None)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, "some-string-payload"),  # non-dict, non-list
        _resp(200, "empty-retry"),
        _resp(200, {"payload": {}}),
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is None


# ---- coordinator 832: empty-then-retry-fail goes through fallback URL ----


async def test_live_train_empty_then_retry_first_fails_goes_to_fallback(hass):
    """vehicle URL empty -> retry without filter returns None -> fallback URL retry (line 832)."""
    from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator
    coord = NSUpdateCoordinator(
        hass, api_key="k", from_station="A", to_station="B",
        scan_interval_minutes=5, fav_hours=6, fetch_composition=False,
    )
    coord._store = MagicMock(); coord._store.async_load = AsyncMock(return_value=None)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"payload": {"treinen": []}}),  # 1st call: empty with filter
        _resp(503),  # retry without filter on URL_main fails
        _resp(200, {"payload": {"treinen": [{"route": "100", "lat": 52, "lng": 5}]}}),  # fallback URL succeeds
    ])
    out = await coord.async_fetch_live_train("100")
    assert out is not None
    assert out["lat"] == 52


async def test_migrate_v1_with_options_uses_options_branch():
    """v1 migration: primary has CONF_API_KEY in options -> _opt returns options value (line 160)."""
    from custom_components.ns_reisadvies import async_migrate_entry
    fake_hass = MagicMock()
    primary = MagicMock()
    primary.version = 1; primary.entry_id = "a"
    primary.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    primary.options = {CONF_API_KEY: "opt-key"}  # API key is in OPTIONS
    fake_hass.config_entries.async_entries.return_value = [primary]
    fake_hass.config_entries.async_update_entry = MagicMock()
    fake_hass.config_entries.async_add_subentry = MagicMock()
    fake_hass.async_create_task = MagicMock()
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=MagicMock()), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[]):
        assert await async_migrate_entry(fake_hass, primary) is True
    # Verify the api key from options ended up in hub_data
    _, kwargs = fake_hass.config_entries.async_update_entry.call_args
    assert kwargs["data"][CONF_API_KEY] == "opt-key"


async def test_rail_cache_stat_oserror_force_path(tmp_path):
    """OSError on stat in rail_cache — use mock target to avoid Path.stat global patch."""
    from custom_components.ns_reisadvies import _async_refresh_rail_cache
    target_dir = tmp_path / "www"; target_dir.mkdir()
    target_file = target_dir / "rail.geojson"
    target_file.write_text("{}")
    # Make stat fail by removing read permission then chmod back after
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = str(target_dir)
    fake_hass.async_add_executor_job = AsyncMock()
    coord = MagicMock()
    coord.async_fetch_full_rail_network = AsyncMock(return_value={"type": "FeatureCollection", "features": [{}]})
    # Replace target.stat with raising via Path subclass
    from pathlib import Path as _P
    original_stat = _P.stat
    call_counter = {"n": 0}
    def stat_raise(self, *a, **kw):
        call_counter["n"] += 1
        if call_counter["n"] == 1 and str(self).endswith("rail.geojson"):
            raise OSError("boom")
        return original_stat(self, *a, **kw)
    _P.stat = stat_raise
    try:
        await _async_refresh_rail_cache(fake_hass, coord, force=False)
    finally:
        _P.stat = original_stat
    coord.async_fetch_full_rail_network.assert_called_once()
