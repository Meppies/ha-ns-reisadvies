"""Tests for coordinator's per-route filter wiring (v2.14.0)."""
from __future__ import annotations

from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies.coordinator import (
    NSUpdateCoordinator,
    _parse_date,
    _parse_time,
)


def _resp(status: int, json_payload: dict | None = None):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=json_payload or {})
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


def _coord(hass: HomeAssistant, **kw) -> NSUpdateCoordinator:
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


# ---- _parse_time / _parse_date helpers --------------------------------------


def test_parse_time_none_input():
    assert _parse_time(None) is None
    assert _parse_time("") is None


def test_parse_time_valid():
    assert _parse_time("08:30") == time(8, 30)
    assert _parse_time("23:59") == time(23, 59)


def test_parse_time_invalid_returns_none():
    assert _parse_time("not-a-time") is None
    assert _parse_time("25:99") is None
    assert _parse_time("8") is None  # missing colon


def test_parse_date_none_input():
    assert _parse_date(None) is None
    assert _parse_date("") is None


def test_parse_date_valid():
    assert _parse_date("2026-12-24") == date(2026, 12, 24)


def test_parse_date_invalid_returns_none():
    assert _parse_date("not-a-date") is None
    assert _parse_date("2026/12/24") is None  # wrong format


# ---- coordinator constructor parses filter args -----------------------------


async def test_coordinator_stores_parsed_filter_fields(hass: HomeAssistant) -> None:
    coord = _coord(
        hass,
        filter_days=[0, 2, 4],
        filter_time="08:00",
        filter_window_minutes=60,
        filter_date="2026-12-24",
    )
    assert coord.filter_days == [0, 2, 4]
    assert coord.filter_time == time(8, 0)
    assert coord.filter_window_minutes == 60
    assert coord.filter_date == date(2026, 12, 24)


async def test_coordinator_clamps_window_to_valid_range(hass: HomeAssistant) -> None:
    coord = _coord(hass, filter_window_minutes=999)
    assert coord.filter_window_minutes == 360  # capped
    coord2 = _coord(hass, filter_window_minutes=-10)
    assert coord2.filter_window_minutes == 0  # floored


async def test_coordinator_filter_defaults_when_no_args(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    assert coord.filter_days == []
    assert coord.filter_time is None
    assert coord.filter_window_minutes == 0
    assert coord.filter_date is None


async def test_coordinator_handles_invalid_filter_strings(hass: HomeAssistant) -> None:
    coord = _coord(
        hass,
        filter_time="garbage",
        filter_date="also-garbage",
    )
    assert coord.filter_time is None
    assert coord.filter_date is None


# ---- _async_update_data with filter -----------------------------------------


async def test_update_data_no_filter_uses_now(hass: HomeAssistant) -> None:
    """No filter set → existing v2.13.x behaviour preserved."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": []}))
    out = await coord._async_update_data()
    assert out == []
    # Verify the API was called with a dateTime param (we don't check
    # its exact value because it depends on the wall clock).
    call_kwargs = coord._session.get.call_args.kwargs
    assert "dateTime" in call_kwargs["params"]


async def test_update_data_with_filter_passes_target_to_api(
    hass: HomeAssistant,
) -> None:
    """Filter set → API receives the computed target as dateTime."""
    from datetime import datetime as _dt

    fixed_now = _dt(2026, 5, 9, 14, 0)  # Saturday
    coord = _coord(
        hass,
        filter_days=[0],  # Monday only
        filter_time="08:00",
    )
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": []}))
    with patch(
        "custom_components.ns_reisadvies.coordinator.datetime",
        wraps=_dt,
    ) as mock_dt:
        mock_dt.now.return_value = fixed_now
        await coord._async_update_data()
    # Saturday → next Monday is 2026-05-11 at 08:00.
    call_kwargs = coord._session.get.call_args.kwargs
    assert call_kwargs["params"]["dateTime"].startswith("2026-05-11T08:00")


async def test_update_data_with_window_filters_response(
    hass: HomeAssistant,
) -> None:
    """Trips outside the window are dropped before being returned."""
    from datetime import datetime as _dt

    fixed_now = _dt(2026, 5, 9, 7, 0)  # Saturday morning
    trips_payload = {
        "trips": [
            # 07:00 — exact target
            {"ctxRecon": "a", "legs": [{"origin": {"plannedDateTime": "2026-05-09T07:00:00"}}]},
            # 08:00 — within ±60min window
            {"ctxRecon": "b", "legs": [{"origin": {"plannedDateTime": "2026-05-09T08:00:00"}}]},
            # 10:00 — outside window
            {"ctxRecon": "c", "legs": [{"origin": {"plannedDateTime": "2026-05-09T10:00:00"}}]},
        ],
    }
    coord = _coord(
        hass,
        filter_time="07:00",
        filter_window_minutes=60,
    )
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, trips_payload))
    with patch(
        "custom_components.ns_reisadvies.coordinator.datetime",
        wraps=_dt,
    ) as mock_dt:
        mock_dt.now.return_value = fixed_now
        out = await coord._async_update_data()
    ctxs = {t["ctxRecon"] for t in out}
    assert ctxs == {"a", "b"}


async def test_update_data_specific_date_in_past_falls_back_to_now(
    hass: HomeAssistant,
) -> None:
    """Specific-date filter that's fully in the past → fall back to now."""
    coord = _coord(
        hass,
        filter_date="2020-01-01",
        filter_time="08:00",
    )
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": []}))
    out = await coord._async_update_data()
    # Doesn't crash; returns whatever (empty here).
    assert out == []
