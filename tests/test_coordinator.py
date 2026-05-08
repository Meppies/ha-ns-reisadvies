"""Tests for the NSUpdateCoordinator + helpers."""
from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ns_reisadvies.coordinator import (
    NSUpdateCoordinator,
    async_validate_api_key,
)


def _make_coord(hass: HomeAssistant, **kwargs) -> NSUpdateCoordinator:
    """Build a coordinator with stubbed Storage so tests don't touch disk."""
    defaults = {
        "api_key": "test-key",
        "from_station": "Hilversum",
        "to_station": "Duivendrecht",
        "scan_interval_minutes": 5,
        "fav_hours": 6,
        "fetch_composition": False,
    }
    defaults.update(kwargs)
    coord = NSUpdateCoordinator(hass, **defaults)
    # Stub Storage so we never touch the disk in tests.
    coord._store = MagicMock()
    coord._store.async_load = AsyncMock(return_value=None)
    coord._store.async_save = AsyncMock()
    return coord


# ---------- track / untrack -------------------------------------------------


async def test_track_trip_pins_a_ctx_recon(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord.track_trip("ABC123")
    assert "ABC123" in coord.tracked_trips


async def test_track_trip_ignores_empty_input(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord.track_trip("")
    coord.track_trip(None)  # type: ignore[arg-type]
    assert coord.tracked_trips == {}


async def test_track_trip_is_idempotent(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord.track_trip("XYZ")
    first_ts = coord.tracked_trips["XYZ"]
    coord.track_trip("XYZ")  # duplicate, should not change timestamp
    assert coord.tracked_trips["XYZ"] == first_ts


async def test_untrack_trip_removes(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord.tracked_trips = {"A": time.time(), "B": time.time()}
    coord.untrack_trip("A")
    assert "A" not in coord.tracked_trips
    assert "B" in coord.tracked_trips


async def test_untrack_trip_silent_on_missing(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord.tracked_trips = {}
    coord.untrack_trip("never-existed")  # should not raise


# ---------- expiry ----------------------------------------------------------


async def test_expire_old_trips_removes_stale(hass: HomeAssistant) -> None:
    coord = _make_coord(hass, fav_hours=1)
    now = time.time()
    coord.tracked_trips = {
        "fresh": now - 10,
        "stale": now - 7200,  # > 1 hour old
    }
    expired = coord._expire_old_trips()
    assert expired == ["stale"]
    assert "fresh" in coord.tracked_trips
    assert "stale" not in coord.tracked_trips


async def test_expire_old_trips_disabled_when_fav_hours_zero(
    hass: HomeAssistant,
) -> None:
    coord = _make_coord(hass, fav_hours=0)
    coord.tracked_trips = {"old": time.time() - 999999}
    assert coord._expire_old_trips() == []
    assert "old" in coord.tracked_trips


# ---------- _note_unavailable / _note_available -----------------------------


async def test_edge_detection_logs_once(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """One warning per outage, one info per recovery; not per refresh."""
    coord = _make_coord(hass)
    caplog.set_level(logging.INFO, logger="custom_components.ns_reisadvies.coordinator")

    # Two failures in a row → only one WARNING line
    coord._note_unavailable("first")
    coord._note_unavailable("second")
    warnings = [
        r for r in caplog.records
        if r.levelname == "WARNING" and "is unavailable" in r.message
    ]
    assert len(warnings) == 1

    # Recovery → one INFO line
    coord._note_available()
    info = [
        r for r in caplog.records
        if r.levelname == "INFO" and "is back online" in r.message
    ]
    assert len(info) == 1

    # Subsequent successful refresh → no extra log
    coord._note_available()
    info_after = [
        r for r in caplog.records
        if r.levelname == "INFO" and "is back online" in r.message
    ]
    assert len(info_after) == 1


# ---------- _async_update_data ---------------------------------------------


def _aiohttp_response(status: int, json_payload: dict | None = None):
    """Build a fake aiohttp response usable in `async with`."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_payload or {})
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    return resp


async def test_update_data_returns_trips_on_success(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    payload = {"trips": [{"ctxRecon": "abc", "legs": []}]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_aiohttp_response(200, payload))

    trips = await coord._async_update_data()
    assert isinstance(trips, list)
    assert trips[0]["ctxRecon"] == "abc"


async def test_update_data_raises_auth_failed_on_401(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_aiohttp_response(401))

    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_update_data_raises_auth_failed_on_403(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_aiohttp_response(403))

    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_update_data_raises_update_failed_on_5xx(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_aiohttp_response(503))

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_update_data_raises_update_failed_on_network_error(
    hass: HomeAssistant,
) -> None:
    coord = _make_coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_update_data_no_api_key_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    coord = _make_coord(hass, api_key="")
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


# ---------- async_validate_api_key (config-flow probe) ----------------------


async def test_validate_api_key_empty_returns_invalid_auth(
    hass: HomeAssistant,
) -> None:
    assert await async_validate_api_key(hass, "") == "invalid_auth"
    assert await async_validate_api_key(hass, "   ") == "invalid_auth"


async def test_validate_api_key_success(hass: HomeAssistant) -> None:
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=_aiohttp_response(200))
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_get_clientsession",
        return_value=fake_session,
    ):
        assert await async_validate_api_key(hass, "valid-key") is None


async def test_validate_api_key_401(hass: HomeAssistant) -> None:
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=_aiohttp_response(401))
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_get_clientsession",
        return_value=fake_session,
    ):
        assert await async_validate_api_key(hass, "wrong") == "invalid_auth"


async def test_validate_api_key_5xx(hass: HomeAssistant) -> None:
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=_aiohttp_response(503))
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_get_clientsession",
        return_value=fake_session,
    ):
        assert await async_validate_api_key(hass, "k") == "cannot_connect"


async def test_validate_api_key_network_error(hass: HomeAssistant) -> None:
    fake_session = MagicMock()
    fake_session.get = MagicMock(side_effect=aiohttp.ClientError("dns"))
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_get_clientsession",
        return_value=fake_session,
    ):
        assert await async_validate_api_key(hass, "k") == "cannot_connect"


async def test_validate_api_key_timeout(hass: HomeAssistant) -> None:
    fake_session = MagicMock()
    fake_session.get = MagicMock(side_effect=asyncio.TimeoutError())
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_get_clientsession",
        return_value=fake_session,
    ):
        assert await async_validate_api_key(hass, "k") == "cannot_connect"


# ---------- persistent storage --------------------------------------------


async def test_async_load_tracked_handles_dict_payload(
    hass: HomeAssistant,
) -> None:
    coord = _make_coord(hass)
    coord._store.async_load = AsyncMock(
        return_value={"trips": {"A": 1700000000.0, "B": 1700000100.0}}
    )
    await coord.async_load_tracked()
    assert coord.tracked_trips == {"A": 1700000000.0, "B": 1700000100.0}


async def test_async_load_tracked_migrates_legacy_list(
    hass: HomeAssistant,
) -> None:
    """Older versions persisted favourites as a plain list. Should still load."""
    coord = _make_coord(hass)
    coord._store.async_load = AsyncMock(return_value={"trips": ["X", "Y"]})
    await coord.async_load_tracked()
    # Both should be present with a "now"-ish timestamp.
    assert set(coord.tracked_trips.keys()) == {"X", "Y"}
    for ts in coord.tracked_trips.values():
        assert ts > 0


async def test_async_load_tracked_handles_no_data(hass: HomeAssistant) -> None:
    coord = _make_coord(hass)
    coord._store.async_load = AsyncMock(return_value=None)
    await coord.async_load_tracked()
    assert coord.tracked_trips == {}
