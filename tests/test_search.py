"""Looking a journey up on the spot (v2.24.0).

The search card's backend: a one-off trip lookup that touches none of
the coordinator's own state, plus the two websocket commands behind
the card — the station list it completes on, and the search itself.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies import _ws_search, _ws_stations
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator

search_inner = _ws_search.__wrapped__  # type: ignore[attr-defined]


def _resp(status, payload=None):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=payload if payload is not None else {})
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


def _coord(hass: HomeAssistant, **kw) -> NSUpdateCoordinator:
    defaults = {
        "api_key": "k",
        "from_station": "Duivendrecht",
        "to_station": "Hilversum",
    }
    defaults.update(kw)
    coord = NSUpdateCoordinator(hass, **defaults)
    coord._store = MagicMock()
    coord._store.async_save = AsyncMock()
    return coord


def _trip(category: str = "IC", number: str = "1825") -> dict:
    return {
        "ctxRecon": f"CTX-{number}",
        "legs": [{
            "product": {
                "number": number, "categoryCode": category,
                "shortCategoryName": category, "operatorName": "NS",
            },
            "origin": {"name": "Amsterdam Centraal",
                       "plannedDateTime": "2026-11-20T08:24:00+0100"},
            "destination": {"name": "Utrecht Centraal",
                            "plannedDateTime": "2026-11-20T08:51:00+0100"},
        }],
    }


# --------------------------------------------------------------------
# the lookup itself
# --------------------------------------------------------------------

async def test_search_asks_ns_exactly_what_was_typed(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": [_trip()]}))

    trips, problem = await coord.async_search_trips(
        "Amsterdam Centraal", "Utrecht Centraal",
        via="Amersfoort Centraal", when="2026-11-20T18:00:00+01:00",
        arrival=True,
    )
    assert problem is None
    assert len(trips) == 1
    assert coord._session.get.call_args.kwargs["params"] == {
        "fromStation": "Amsterdam Centraal",
        "toStation": "Utrecht Centraal",
        "viaStation": "Amersfoort Centraal",
        "dateTime": "2026-11-20T18:00:00+01:00",
        "searchForArrival": "true",
    }


async def test_search_leaves_out_what_was_not_asked(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": [_trip()]}))
    await coord.async_search_trips("Amsterdam Centraal", "Utrecht Centraal")
    assert coord._session.get.call_args.kwargs["params"] == {
        "fromStation": "Amsterdam Centraal",
        "toStation": "Utrecht Centraal",
    }


async def test_search_changes_nothing_about_the_route(hass: HomeAssistant) -> None:
    """A lookup is not a route: it must leave the coordinator alone."""
    coord = _coord(hass)
    coord.data = ["untouched"]
    coord.tracked_trips = {"CTX-PINNED": 1.0}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": [_trip()]}))

    await coord.async_search_trips("Amsterdam Centraal", "Utrecht Centraal")
    assert coord.data == ["untouched"]
    assert coord.tracked_trips == {"CTX-PINNED": 1.0}
    assert coord.from_station == "Duivendrecht"


async def test_search_needs_a_key_and_two_stations(hass: HomeAssistant) -> None:
    assert await _coord(hass, api_key="").async_search_trips("A", "B") == (
        [], "no_api_key",
    )
    assert await _coord(hass).async_search_trips("", "Utrecht Centraal") == (
        [], "missing_station",
    )
    assert await _coord(hass).async_search_trips("Amsterdam Centraal", "") == (
        [], "missing_station",
    )


@pytest.mark.parametrize(
    ("status", "problem"),
    [(401, "rejected"), (403, "rejected"), (400, "unknown_station"),
     (500, "unavailable")],
)
async def test_search_names_what_went_wrong(
    hass: HomeAssistant, status: int, problem: str,
) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(status))
    assert await coord.async_search_trips("A", "B") == ([], problem)


async def test_search_survives_a_silent_ns(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=asyncio.TimeoutError())
    assert await coord.async_search_trips("A", "B") == ([], "unavailable")

    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("down"))
    assert await coord.async_search_trips("A", "B") == ([], "unavailable")


async def test_search_applies_the_train_type_filter(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": [
        _trip("IC", "1825"), _trip("SPR", "4385"),
    ]}))
    trips, problem = await coord.async_search_trips("A", "B", train_types=["SPR"])
    assert problem is None
    assert [t["legs"][0]["product"]["number"] for t in trips] == ["4385"]


async def test_search_says_so_when_the_filter_empties_the_list(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": [_trip("IC")]}))
    assert await coord.async_search_trips("A", "B", train_types=["ICE"]) == (
        [], "no_match",
    )


async def test_search_ignores_rubbish_in_the_answer(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": ["nope", _trip()]}))
    trips, problem = await coord.async_search_trips("A", "B")
    assert problem is None and len(trips) == 1


# --------------------------------------------------------------------
# the websocket commands behind the card
# --------------------------------------------------------------------

def _hass_with(coord):
    runtime = MagicMock()
    runtime.coordinators = {"sub": coord}
    runtime.live_sessions = {}
    entry = MagicMock()
    entry.runtime_data = runtime
    fake = MagicMock()
    fake.config_entries.async_entries.return_value = [entry]
    return fake


def test_ws_stations_offers_the_bundled_list() -> None:
    conn = MagicMock()
    _ws_stations(MagicMock(), conn, {"id": 1})
    names = conn.send_result.call_args[0][1]["stations"]
    assert "Amsterdam Centraal" in names
    assert len(names) > 300


async def test_ws_search_passes_the_query_through() -> None:
    coord = MagicMock()
    coord.async_search_trips = AsyncMock(return_value=([_trip()], None))
    conn = MagicMock()
    await search_inner(_hass_with(coord), conn, {
        "id": 1,
        "from_station": "Amsterdam Centraal",
        "to_station": "Utrecht Centraal",
        "via": "Amersfoort Centraal",
        "when": "2026-11-20T18:00:00+01:00",
        "arrival": True,
        "train_types": ["IC"],
    })
    result = conn.send_result.call_args[0][1]
    assert len(result["trips"]) == 1 and result["problem"] is None
    assert coord.async_search_trips.await_args.kwargs == {
        "via": "Amersfoort Centraal",
        "when": "2026-11-20T18:00:00+01:00",
        "arrival": True,
        "train_types": ["IC"],
    }


async def test_ws_search_turns_blanks_into_nothing() -> None:
    coord = MagicMock()
    coord.async_search_trips = AsyncMock(return_value=([], "no_trips"))
    conn = MagicMock()
    await search_inner(_hass_with(coord), conn, {
        "id": 1, "from_station": "A", "to_station": "B", "via": "",
    })
    assert coord.async_search_trips.await_args.kwargs["via"] is None
    assert coord.async_search_trips.await_args.kwargs["when"] is None
    assert conn.send_result.call_args[0][1]["problem"] == "no_trips"


async def test_ws_search_needs_a_hub() -> None:
    fake = MagicMock()
    fake.config_entries.async_entries.return_value = []
    conn = MagicMock()
    await search_inner(fake, conn, {"id": 1, "from_station": "A", "to_station": "B"})
    assert conn.send_error.call_args[0][1] == "no_hub"
