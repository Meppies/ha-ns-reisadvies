"""Favourite tracking in the coordinator (v2.18.0).

Covers the wall-clock leg selection, the gating that keeps the ProRail
feed untouched outside a trip's travel window, the listener plumbing the
device_tracker platform hangs off, and the interval lifecycle.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies import _start_favourite_tracking
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator, parse_iso

CTX = "CTX-ONE"
DEP = "2026-10-07T07:52:00+02:00"
ARR = "2026-10-07T08:06:00+02:00"


def _leg(number="1825", dep=DEP, arr=ARR, origin="Duivendrecht", dest="Hilversum"):
    return {
        "product": {
            "number": number,
            "shortCategoryName": "ICD",
            "displayName": "NS Intercity direct",
            "operatorName": "NS",
        },
        "origin": {"name": origin, "plannedDateTime": dep},
        "destination": {"name": dest, "plannedDateTime": arr},
        "direction": "Amersfoort Schothorst",
    }


def _trip(ctx=CTX, legs=None):
    return {"ctxRecon": ctx, "legs": legs if legs is not None else [_leg()]}


def _make(hass: HomeAssistant, **kw) -> NSUpdateCoordinator:
    defaults = {
        "api_key": "k",
        "from_station": "Duivendrecht",
        "to_station": "Hilversum",
        "scan_interval_minutes": 5,
        "fav_hours": 6,
        "track_favourites": True,
    }
    defaults.update(kw)
    coord = NSUpdateCoordinator(hass, **defaults)
    coord._store = MagicMock()
    coord._store.async_save = AsyncMock(return_value=None)
    coord.data = [_trip()]
    coord.tracked_trips = {CTX: time.time()}
    coord.async_fetch_arcgis_position = AsyncMock(return_value=None)
    coord._async_station_based_position = AsyncMock(return_value=None)
    return coord


def test_parse_iso_handles_offsets_naive_and_junk() -> None:
    assert parse_iso(DEP).hour == 7
    naive = parse_iso("2026-10-07T07:52:00")
    assert naive is not None and naive.tzinfo is timezone.utc
    assert parse_iso("not a timestamp") is None
    assert parse_iso(None) is None
    assert parse_iso(12345) is None


async def test_favourite_state_phases(hass: HomeAssistant) -> None:
    coord = _make(hass)
    during = parse_iso(DEP) + timedelta(minutes=5)
    before = parse_iso(DEP) - timedelta(hours=2)
    after = parse_iso(ARR) + timedelta(hours=1)

    en_route = coord.favourite_state(CTX, during)
    assert en_route["active"] is True
    assert en_route["phase"] == "en_route"
    assert en_route["leg"]["product"]["number"] == "1825"

    upcoming = coord.favourite_state(CTX, before)
    assert upcoming["active"] is False
    assert upcoming["phase"] == "upcoming"

    arrived = coord.favourite_state(CTX, after)
    assert arrived["active"] is False
    assert arrived["phase"] == "arrived"

    assert coord.favourite_state("nope", during) is None


async def test_favourite_state_follows_the_current_leg(hass: HomeAssistant) -> None:
    """At a transfer the state moves to the train actually being ridden."""
    first = _leg(number="1825", dep=DEP, arr=ARR)
    second = _leg(
        number="5720",
        dep="2026-10-07T08:12:00+02:00",
        arr="2026-10-07T08:41:00+02:00",
        origin="Hilversum",
        dest="Utrecht Centraal",
    )
    coord = _make(hass)
    coord.data = [_trip(legs=[first, second])]

    on_first = coord.favourite_state(CTX, parse_iso(DEP) + timedelta(minutes=2))
    assert on_first["leg"]["product"]["number"] == "1825"

    on_second = coord.favourite_state(
        CTX, parse_iso("2026-10-07T08:20:00+02:00"),
    )
    assert on_second["leg"]["product"]["number"] == "5720"
    assert on_second["active"] is True

    # Between the two legs the traveller is on the platform: the lead
    # window already counts that as the next train.
    between = coord.favourite_state(CTX, parse_iso("2026-10-07T08:09:00+02:00"))
    assert between["leg"]["product"]["number"] == "5720"


async def test_refresh_fetches_only_while_en_route(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.async_fetch_arcgis_position = AsyncMock(
        return_value={"lat": 52.3, "lng": 4.94, "speed": 112, "heading": 90}
    )

    await coord.async_refresh_favourite_positions(parse_iso(DEP) - timedelta(hours=3))
    record = coord.favourite_positions[CTX]
    assert record["active"] is False
    assert record["position"] is None
    coord.async_fetch_arcgis_position.assert_not_awaited()

    await coord.async_refresh_favourite_positions(parse_iso(DEP) + timedelta(minutes=3))
    record = coord.favourite_positions[CTX]
    assert record["active"] is True
    assert record["position"]["lat"] == 52.3
    assert record["position_fresh"] is True
    assert record["train_number"] == "1825"
    assert record["trip_origin"] == "Duivendrecht"
    assert record["trip_destination"] == "Hilversum"
    coord.async_fetch_arcgis_position.assert_awaited_once()


async def test_refresh_falls_back_to_station_position(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord._async_station_based_position = AsyncMock(
        return_value={"lat": 52.1, "lng": 5.1, "source": "at-stop"}
    )
    await coord.async_refresh_favourite_positions(parse_iso(DEP) + timedelta(minutes=3))
    assert coord.favourite_positions[CTX]["position"]["source"] == "at-stop"
    coord._async_station_based_position.assert_awaited_once()


async def test_refresh_keeps_last_fix_between_reports(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.async_fetch_arcgis_position = AsyncMock(return_value={"lat": 52.3, "lng": 4.9})
    moment = parse_iso(DEP) + timedelta(minutes=3)
    await coord.async_refresh_favourite_positions(moment)

    coord.async_fetch_arcgis_position = AsyncMock(return_value=None)
    coord._async_station_based_position = AsyncMock(return_value=None)
    await coord.async_refresh_favourite_positions(moment + timedelta(seconds=30))
    record = coord.favourite_positions[CTX]
    assert record["position"]["lat"] == 52.3
    assert record["position_fresh"] is False


async def test_refresh_prunes_and_respects_the_option(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.favourite_positions["GONE"] = {"active": False}
    await coord.async_refresh_favourite_positions(parse_iso(DEP))
    assert "GONE" not in coord.favourite_positions

    # Trip no longer in the data set — nothing to show.
    coord.data = []
    await coord.async_refresh_favourite_positions(parse_iso(DEP))
    assert coord.favourite_positions == {}

    coord.data = [_trip()]
    coord.track_favourites = False
    coord.favourite_positions[CTX] = {"active": True}
    await coord.async_refresh_favourite_positions(parse_iso(DEP))
    assert coord.favourite_positions == {}


async def test_listeners_fire_and_unsubscribe(hass: HomeAssistant) -> None:
    coord = _make(hass)
    calls: list[int] = []
    remove = coord.async_add_favourite_listener(lambda: calls.append(1))
    await coord.async_refresh_favourite_positions(parse_iso(DEP))
    assert calls == [1]
    remove()
    remove()  # idempotent
    await coord.async_refresh_favourite_positions(parse_iso(DEP))
    assert calls == [1]


async def test_interval_lifecycle(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.async_start_favourite_tracking()
    first = coord._fav_unsub
    assert first is not None
    coord.async_start_favourite_tracking()
    assert coord._fav_unsub is first  # idempotent

    coord.favourite_positions[CTX] = {"active": True}
    coord.async_stop_favourite_tracking()
    assert coord._fav_unsub is None
    assert coord.favourite_positions == {}
    coord.async_stop_favourite_tracking()  # safe twice


async def test_interval_not_scheduled_when_disabled(hass: HomeAssistant) -> None:
    coord = _make(hass, track_favourites=False)
    coord.async_start_favourite_tracking()
    assert coord._fav_unsub is None


async def test_tick_delegates_to_refresh(hass: HomeAssistant) -> None:
    coord = _make(hass)
    coord.async_refresh_favourite_positions = AsyncMock()
    now = datetime.now(timezone.utc)
    await coord._async_favourite_tick(now)
    coord.async_refresh_favourite_positions.assert_awaited_once_with(now)


async def test_interval_is_clamped(hass: HomeAssistant) -> None:
    assert _make(hass, favourite_track_seconds=1).favourite_track_seconds == 15
    assert _make(hass, favourite_track_seconds=9999).favourite_track_seconds == 120
    assert _make(hass, favourite_track_seconds=0).favourite_track_seconds == 30


async def test_leg_window_and_endpoints_tolerate_junk(hass: HomeAssistant) -> None:
    coord = _make(hass)
    assert coord.leg_window({}) == (None, None)
    assert coord._trip_endpoint({"legs": []}, first=True) is None
    assert coord._trip_endpoint({"legs": [{"origin": {}}]}, first=True) is None
    # A leg without usable timestamps is skipped rather than crashing.
    coord.data = [_trip(legs=[{"product": {"number": "1"}}])]
    state = coord.favourite_state(CTX, parse_iso(DEP))
    assert state["phase"] == "arrived"


def _rec(ctx, phase, dep):
    return {"ctx_recon": ctx, "phase": phase, "departure": dep}


async def test_current_favourite_prefers_the_running_trip(hass: HomeAssistant) -> None:
    """A train already moving beats one that leaves later."""
    coord = _make(hass)
    coord.favourite_positions = {
        "A": _rec("A", "upcoming", "2026-10-07T09:00:00+02:00"),
        "B": _rec("B", "en_route", "2026-10-07T10:00:00+02:00"),
    }
    assert coord.current_favourite()["ctx_recon"] == "B"


async def test_current_favourite_takes_the_earliest_in_a_phase(
    hass: HomeAssistant,
) -> None:
    coord = _make(hass)
    coord.favourite_positions = {
        "LATE": _rec("LATE", "upcoming", "2026-10-07T11:00:00+02:00"),
        "SOON": _rec("SOON", "upcoming", "2026-10-07T09:00:00+02:00"),
        "NOTIME": _rec("NOTIME", "upcoming", None),
    }
    assert coord.current_favourite()["ctx_recon"] == "SOON"


async def test_current_favourite_ignores_finished_and_empty(
    hass: HomeAssistant,
) -> None:
    coord = _make(hass)
    assert coord.current_favourite() is None  # nothing pinned
    coord.favourite_positions = {
        "OLD": _rec("OLD", "arrived", "2026-10-07T06:00:00+02:00"),
    }
    assert coord.current_favourite() is None


async def test_start_helper_schedules_and_registers_teardown(hass: HomeAssistant) -> None:
    """The setup-time helper starts, refreshes and arms the unload hook."""
    coord = _make(hass)
    coord.async_fetch_arcgis_position = AsyncMock(return_value={"lat": 52.0, "lng": 5.0})
    unloads: list = []
    entry = SimpleNamespace(async_on_unload=unloads.append)

    _start_favourite_tracking(hass, entry, {"sub1": coord})
    await hass.async_block_till_done()

    assert coord._fav_unsub is not None
    assert coord.favourite_positions  # the immediate refresh ran
    assert unloads == [coord.async_stop_favourite_tracking]

    # The registered hook really does stop the interval.
    unloads[0]()
    assert coord._fav_unsub is None
