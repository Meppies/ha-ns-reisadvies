"""Live train positions and whole-run journeys (v2.21.0).

Two halves: the pure parsing in ``_live`` against the shapes NS really
returns, and the coordinator methods that fetch and cache them.

The journey payloads here mirror the live API: a stop carries its
station under ``stop``, its times under ``arrivals``/``departures``,
and a station the train races past has ``status: PASSING`` with both
lists empty.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies._live import (
    parse_journey,
    position_along,
    run_window,
    vehicle_index,
)
from custom_components.ns_reisadvies.const import (
    ARCGIS_FAILURES_BEFORE_BACKOFF,
    DOMAIN,
)
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator

NOW = datetime(2026, 11, 19, 21, 45, tzinfo=timezone.utc)


def _resp(status, payload=None):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=payload if payload is not None else {})
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


def _coord(hass, **kw) -> NSUpdateCoordinator:
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


# --------------------------------------------------------------------
# the vehicle feed
# --------------------------------------------------------------------

def _train(number=1825, ride=None, **kw):
    out = {
        "treinNummer": number,
        "ritId": str(ride if ride is not None else number),
        "lat": 52.39261,
        "lng": 4.809091,
        "snelheid": 67.711,
        "richting": 127.26,
        "horizontaleNauwkeurigheid": 427.77777,
        "type": "IC",
        "bron": "OBIS",
    }
    out.update(kw)
    return out


def test_vehicle_index_reads_the_real_payload_shape() -> None:
    index = vehicle_index({"payload": {"treinen": [_train()]}})
    assert set(index) == {"1825"}
    fix = index["1825"]
    assert fix["lat"] == pytest.approx(52.39261)
    assert fix["speed"] == pytest.approx(67.711)
    assert fix["heading"] == pytest.approx(127.26)
    assert fix["accuracy"] == pytest.approx(427.77777)
    assert fix["train_type"] == "IC"
    assert fix["train_number"] == "1825"
    assert fix["source"] == "ns-obis"


def test_vehicle_index_accepts_the_other_shapes_nes_api_has_used() -> None:
    train = _train()
    assert vehicle_index({"payload": [train]})["1825"]["lat"]
    assert vehicle_index([train])["1825"]["lat"]
    assert vehicle_index({"treinen": [train]})["1825"]["lat"]


def test_vehicle_index_indexes_ride_as_well_as_number() -> None:
    index = vehicle_index({"payload": {"treinen": [_train(number=1825, ride=9915)]}})
    assert set(index) == {"1825", "9915"}
    assert index["9915"] is index["1825"]


def test_vehicle_index_shrugs_off_rubbish() -> None:
    assert vehicle_index(None) == {}
    assert vehicle_index("nope") == {}
    assert vehicle_index({"payload": {"treinen": "nope"}}) == {}
    assert vehicle_index({"payload": {"treinen": ["nope"]}}) == {}
    # Missing or unparseable coordinates: nothing to show on a map.
    assert vehicle_index({"payload": {"treinen": [_train(lat=None)]}}) == {}
    assert vehicle_index({"payload": {"treinen": [_train(lng="here")]}}) == {}


def test_vehicle_index_without_a_source_still_names_one() -> None:
    index = vehicle_index({"payload": {"treinen": [_train(bron=None)]}})
    assert index["1825"]["source"] == "ns-vehicle"


def test_vehicle_index_skips_a_train_without_any_identifier() -> None:
    assert vehicle_index(
        {"payload": {"treinen": [_train(treinNummer=None, ritId=None)]}},
    ) == {}


# --------------------------------------------------------------------
# the journey
# --------------------------------------------------------------------

def _stop(name, lat, lng, *, uic="", status="STOP", arr=None, dep=None,
          arr_actual=None, dep_actual=None, cancelled=False):
    entry: dict = {
        "stop": {"name": name, "lat": lat, "lng": lng, "uicCode": uic or name},
        "status": status,
        "arrivals": [],
        "departures": [],
    }
    if arr or arr_actual:
        entry["arrivals"] = [{
            "plannedTime": arr, "actualTime": arr_actual, "cancelled": cancelled,
        }]
    if dep or dep_actual:
        entry["departures"] = [{
            "plannedTime": dep, "actualTime": dep_actual, "cancelled": cancelled,
        }]
    return entry


def _journey() -> dict:
    """Three stopping stations with one passed through in between."""
    return {"payload": {"stops": [
        _stop("Amsterdam Centraal", 52.3788, 4.9002, status="ORIGIN",
              dep="2026-11-19T21:30:00+00:00", dep_actual="2026-11-19T21:32:00+00:00"),
        _stop("Amsterdam Muiderpoort", 52.3605, 4.9440, status="PASSING"),
        _stop("Duivendrecht", 52.3233, 4.9391,
              arr="2026-11-19T21:50:00+00:00", dep="2026-11-19T21:52:00+00:00"),
        _stop("Hilversum", 52.2270, 5.1810, status="DESTINATION",
              arr="2026-11-19T22:10:00+00:00"),
    ]}}


def test_parse_journey_keeps_the_whole_run_with_its_times() -> None:
    stops = parse_journey(_journey(), NOW)
    assert [s["name"] for s in stops] == [
        "Amsterdam Centraal", "Amsterdam Muiderpoort",
        "Duivendrecht", "Hilversum",
    ]
    first = stops[0]
    assert first["lat"] == pytest.approx(52.3788)
    assert first["uicCode"] == "Amsterdam Centraal"
    assert first["actualDepartureDateTime"] == "2026-11-19T21:32:00+00:00"
    assert first["passed"] is True  # it left before `NOW`
    assert stops[-1]["passed"] is False
    assert stops[-1]["plannedArrivalDateTime"] == "2026-11-19T22:10:00+00:00"


def test_parse_journey_gives_a_passed_station_a_time_of_its_own() -> None:
    """Otherwise the estimate would jump from stop to stop."""
    stops = parse_journey(_journey(), NOW)
    passing = stops[1]
    assert passing["status"] == "PASSING"
    assert passing["estimated"] is True
    moment = datetime.fromisoformat(passing["plannedArrivalDateTime"])
    # Between the departure before it and the arrival after it, and
    # placed by distance rather than halfway by default.
    assert datetime.fromisoformat("2026-11-19T21:30:00+00:00") < moment
    assert moment < datetime.fromisoformat("2026-11-19T21:50:00+00:00")
    # The stations NS does give times for keep them untouched.
    assert stops[2]["estimated"] is False


def test_parse_journey_splits_a_gap_evenly_without_distance() -> None:
    payload = {"payload": {"stops": [
        _stop("A", 52.0, 5.0, dep="2026-11-19T21:00:00+00:00"),
        _stop("B", 52.0, 5.0, status="PASSING"),
        _stop("C", 52.0, 5.0, status="PASSING"),
        _stop("D", 52.0, 5.0, arr="2026-11-19T21:30:00+00:00"),
    ]}}
    stops = parse_journey(payload, NOW)
    assert stops[1]["plannedArrivalDateTime"] == "2026-11-19T21:10:00+00:00"
    assert stops[2]["plannedArrivalDateTime"] == "2026-11-19T21:20:00+00:00"


def test_parse_journey_leaves_a_backwards_gap_alone() -> None:
    payload = {"payload": {"stops": [
        _stop("A", 52.0, 5.0, dep="2026-11-19T21:30:00+00:00"),
        _stop("B", 52.1, 5.1, status="PASSING"),
        _stop("C", 52.2, 5.2, arr="2026-11-19T21:00:00+00:00"),
    ]}}
    stops = parse_journey(payload, NOW)
    assert stops[1]["estimated"] is False
    assert stops[1]["plannedArrivalDateTime"] is None


def test_parse_journey_marks_a_cancelled_stop() -> None:
    payload = {"payload": {"stops": [
        _stop("A", 52.0, 5.0, dep="2026-11-19T21:00:00+00:00", cancelled=True),
        _stop("B", 52.1, 5.1, arr="2026-11-19T21:20:00+00:00"),
    ]}}
    assert parse_journey(payload, NOW)[0]["cancelled"] is True


def test_parse_journey_handles_what_is_not_a_journey() -> None:
    assert parse_journey(None) == []
    assert parse_journey({"payload": {}}) == []
    assert parse_journey({"stops": []}) == []
    assert parse_journey({"payload": {"stops": "nope"}}) == []
    assert parse_journey({"payload": {"stops": ["nope"]}}) == []
    assert parse_journey({"payload": {"stops": [{"stop": "nope"}]}}) == []
    assert parse_journey(
        {"payload": {"stops": [{"stop": {"name": "A", "lat": None, "lng": 5}}]}},
    ) == []
    assert parse_journey(
        {"payload": {"stops": [{"stop": {"name": "A", "lat": "here", "lng": 5}}]}},
    ) == []
    assert parse_journey(
        {"payload": {"stops": [{"stop": {"name": "A", "lng": 5}}]}},
    ) == []


def test_parse_journey_without_a_now_uses_the_clock() -> None:
    """No moment passed in: the wall clock decides what has been passed."""
    stops = parse_journey(_journey())
    assert len(stops) == 4
    assert all(isinstance(s["passed"], bool) for s in stops)


def test_run_window_is_the_trains_own_run() -> None:
    stops = parse_journey(_journey(), NOW)
    start, end = run_window(stops)
    assert start == datetime.fromisoformat("2026-11-19T21:32:00+00:00")
    assert end == datetime.fromisoformat("2026-11-19T22:10:00+00:00")


def test_run_window_falls_back_through_the_times_it_has() -> None:
    assert run_window([]) == (None, None)
    only_arrival = parse_journey({"payload": {"stops": [
        _stop("A", 52.0, 5.0, arr="2026-11-19T21:00:00+00:00"),
        _stop("B", 52.1, 5.1, status="PASSING"),
    ]}}, NOW)
    start, end = run_window(only_arrival)
    assert start == datetime.fromisoformat("2026-11-19T21:00:00+00:00")
    assert end is None


# --------------------------------------------------------------------
# fetching and caching
# --------------------------------------------------------------------

async def test_vehicles_need_a_key(hass: HomeAssistant) -> None:
    coord = _coord(hass, api_key="")
    assert await coord.async_fetch_vehicles() == {}


async def test_vehicles_are_fetched_without_a_bounding_box(
    hass: HomeAssistant,
) -> None:
    """The regression this release is about.

    NS reads ``radius`` in metres, so the parameters the integration
    used to send asked for trains within 300 m of a point in the middle
    of the country and got an empty list back. The request now carries
    no parameters at all.
    """
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(
        return_value=_resp(200, {"payload": {"treinen": [_train()]}}),
    )
    index = await coord.async_fetch_vehicles()
    assert index["1825"]["lat"] == pytest.approx(52.39261)
    assert "params" not in coord._session.get.call_args.kwargs


async def test_vehicles_fall_back_to_the_second_url(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(503),
        _resp(200, {"payload": {"treinen": [_train()]}}),
    ])
    assert "1825" in await coord.async_fetch_vehicles()
    assert coord._session.get.call_count == 2


async def test_vehicles_survive_a_feed_that_is_down(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))
    assert await coord.async_fetch_vehicles() == {}


async def test_vehicles_are_fetched_once_for_every_caller(
    hass: HomeAssistant,
) -> None:
    """One national request serves every route and every open map."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(
        return_value=_resp(200, {"payload": {"treinen": [_train()]}}),
    )
    first, second = await asyncio.gather(
        coord.async_fetch_vehicles(), coord.async_fetch_vehicles(),
    )
    assert first == second
    await coord.async_fetch_vehicles()
    assert coord._session.get.call_count == 1


async def test_vehicles_use_a_cache_another_tick_filled(
    hass: HomeAssistant,
) -> None:
    """Two ticks at once: the one that waited takes what the other got."""
    coord = _coord(hass)
    bucket = hass.data.setdefault(DOMAIN, {})
    lock = bucket["_vehicles_lock"] = asyncio.Lock()
    coord._session = MagicMock()
    coord._session.get = MagicMock(
        return_value=_resp(200, {"payload": {"treinen": [_train()]}}),
    )
    async with lock:
        waiting = asyncio.create_task(coord.async_fetch_vehicles())
        await asyncio.sleep(0)
        bucket["_vehicles"] = {
            "at": time.monotonic(), "by_ride": {"9999": {"lat": 1.0}},
        }
    assert set(await waiting) == {"9999"}
    coord._session.get.assert_not_called()


async def test_vehicles_ignore_a_stale_cache(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    bucket = hass.data.setdefault(DOMAIN, {})
    bucket["_vehicles"] = {"at": 0.0, "by_ride": {"old": {}}}
    coord._session = MagicMock()
    coord._session.get = MagicMock(
        return_value=_resp(200, {"payload": {"treinen": [_train()]}}),
    )
    assert set(await coord.async_fetch_vehicles()) == {"1825"}
    bucket["_vehicles"] = "not a dict"
    assert set(await coord.async_fetch_vehicles()) == {"1825"}


async def test_vehicle_position_looks_up_one_train(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.async_fetch_vehicles = AsyncMock(return_value={"1825": {"lat": 52.0}})
    assert await coord.async_fetch_vehicle_position("") is None
    assert await coord.async_fetch_vehicle_position(" 1825 ") == {"lat": 52.0}
    assert await coord.async_fetch_vehicle_position("9999") is None


async def test_train_position_prefers_ns_then_arcgis_then_stations(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord.async_fetch_vehicles = AsyncMock(return_value={"1825": {"lat": 1.0}})
    coord.async_fetch_arcgis_position = AsyncMock(return_value={"lat": 2.0})
    coord._async_station_based_position = AsyncMock(return_value={"lat": 3.0})

    assert (await coord.async_fetch_train_position("1825"))["lat"] == 1.0
    coord.async_fetch_arcgis_position.assert_not_awaited()

    coord.async_fetch_vehicles = AsyncMock(return_value={})
    assert (await coord.async_fetch_train_position("1825"))["lat"] == 2.0

    coord.async_fetch_arcgis_position = AsyncMock(return_value=None)
    assert (await coord.async_fetch_train_position("1825"))["lat"] == 3.0


async def test_journey_stops_need_a_train_and_a_key(hass: HomeAssistant) -> None:
    assert await _coord(hass).async_journey_stops("") == []
    assert await _coord(hass, api_key="").async_journey_stops("1825") == []


async def test_journey_stops_parse_and_cache(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, _journey()))
    stops = await coord.async_journey_stops("1825")
    assert [s["name"] for s in stops][0] == "Amsterdam Centraal"
    assert coord._session.get.call_args.kwargs["params"] == {
        "train": "1825", "omitCrowdForecast": "true",
    }
    # Second call inside the cache window: no second request.
    assert await coord.async_journey_stops(" 1825 ") == stops
    assert coord._session.get.call_count == 1


async def test_journey_stops_tolerate_a_missing_endpoint(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(404))
    assert await coord.async_journey_stops("1825") == []

    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=asyncio.TimeoutError())
    assert await coord.async_journey_stops("1826") == []


async def test_journey_cache_forgets_trains_nobody_asks_about(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    cache = hass.data.setdefault(DOMAIN, {}).setdefault("_journeys", {})
    # Far enough in the past to be stale whatever the clock reads: a
    # literal 0.0 only looks old on a machine that has been up for a
    # while, which made this pass here and fail on a fresh CI runner.
    cache["999"] = {"at": time.monotonic() - 10_000, "stops": []}
    cache["bad"] = "not a dict"
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, _journey()))
    await coord.async_journey_stops("1825")
    assert "999" not in cache
    assert "1825" in cache


async def test_journey_run_is_the_window_of_the_parsed_run(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord.async_journey_stops = AsyncMock(
        return_value=parse_journey(_journey(), NOW),
    )
    start, end = await coord.async_journey_run("1825")
    assert start == datetime.fromisoformat("2026-11-19T21:32:00+00:00")
    assert end == datetime.fromisoformat("2026-11-19T22:10:00+00:00")


async def test_train_is_running_is_unknown_without_a_journey(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord.async_journey_run = AsyncMock(return_value=(None, None))
    assert await coord._async_train_is_running("1825", NOW) is None

    coord.async_journey_run = AsyncMock(return_value=(
        NOW - timedelta(minutes=10), NOW + timedelta(minutes=10),
    ))
    assert await coord._async_train_is_running("1825", NOW) is True

    coord.async_journey_run = AsyncMock(return_value=(
        NOW - timedelta(hours=2), NOW - timedelta(hours=1),
    ))
    assert await coord._async_train_is_running("1825", NOW) is False


async def test_nothing_is_followed_without_a_time_to_go_on(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    assert coord._worth_following({}, NOW) is False
    assert coord._worth_following({"departure": "not a datetime"}, NOW) is False
    assert coord._worth_following({"arrival": NOW}, NOW) is True


async def test_arcgis_goes_quiet_after_repeated_errors(
    hass: HomeAssistant,
) -> None:
    """The feed answers "Error invoking service" inside an HTTP 200."""
    coord = _coord(hass)
    bucket = hass.data.setdefault(DOMAIN, {})
    coord._session = MagicMock()
    broken = {"error": {"code": 500, "message": "Error invoking service"}}
    coord._session.get = MagicMock(return_value=_resp(200, broken))

    for _ in range(ARCGIS_FAILURES_BEFORE_BACKOFF):
        assert await coord.async_fetch_arcgis_position("1825") is None
    assert "_arcgis_quiet_until" in bucket
    calls = coord._session.get.call_count

    # Quiet now: no further requests leave the house.
    assert await coord.async_fetch_arcgis_position("1825") is None
    assert coord._session.get.call_count == calls


async def test_arcgis_failure_count_resets_on_a_good_answer(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    bucket = hass.data.setdefault(DOMAIN, {})
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(500),
        _resp(200, {"features": [{"attributes": {
            "lat": 52.1, "lng": 5.1, "snelheid": 90,
        }}]}),
    ])
    assert await coord.async_fetch_arcgis_position("1825") is None
    assert bucket["_arcgis_failures"] == 1
    position = await coord.async_fetch_arcgis_position("1825")
    assert position is not None and position["source"] == "prorail-obis"
    assert bucket["_arcgis_failures"] == 0


async def test_arcgis_network_error_counts_as_a_failure(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    bucket = hass.data.setdefault(DOMAIN, {})
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("down"))
    assert await coord.async_fetch_arcgis_position("1825") is None
    assert bucket["_arcgis_failures"] == 1


# --------------------------------------------------------------------
# placing a fix on the run
# --------------------------------------------------------------------

def _line() -> list[dict]:
    """Four stops roughly due south of each other."""
    return [
        {"name": "A", "lat": 52.40, "lng": 4.90},
        {"name": "B", "lat": 52.30, "lng": 4.90},
        {"name": "C", "lat": 52.20, "lng": 4.90},
        {"name": "D", "lat": 52.10, "lng": 4.90},
    ]


def test_position_along_reads_as_index_plus_fraction() -> None:
    stops = _line()
    assert position_along(stops, 52.40, 4.90) == pytest.approx(0.0)
    assert position_along(stops, 52.30, 4.90) == pytest.approx(1.0)
    assert position_along(stops, 52.25, 4.90) == pytest.approx(1.5, abs=0.01)
    assert position_along(stops, 52.10, 4.90) == pytest.approx(3.0)


def test_position_along_is_what_the_timetable_cannot_say() -> None:
    """Halfway between two stops is 1.5, whatever the clock thinks."""
    stops = _line()
    where = position_along(stops, 52.26, 4.902)
    assert where is not None
    assert 1.0 < where < 2.0


def test_position_along_counts_standing_in_a_station_as_being_there() -> None:
    """A platform is a few hundred metres from the station's own point.

    Without this the station stays uncoloured while the train sits in
    it, which is what a traveller on the platform sees and does not
    believe.
    """
    stops = _line()
    # Roughly 300 m short of stop B, which is where a stopped train's
    # fix tends to sit.
    where = position_along(stops, 52.2973, 4.90)
    assert where == pytest.approx(1.0)
    # Far enough out to be on its way again.
    moving = position_along(stops, 52.29, 4.90)
    assert moving is not None and moving > 1.05


def test_position_along_snapping_can_be_turned_off() -> None:
    stops = _line()
    free = position_along(stops, 52.2973, 4.90, snap_km=0.0)
    assert free is not None and free != pytest.approx(1.0)


def test_position_along_refuses_a_fix_that_is_somewhere_else() -> None:
    stops = _line()
    # Groningen is nowhere near this line.
    assert position_along(stops, 53.21, 6.56) is None
    # Unless you allow it to be.
    assert position_along(stops, 53.21, 6.56, max_km=400) is not None


def test_position_along_needs_a_run_and_a_fix() -> None:
    assert position_along([], 52.3, 4.9) is None
    assert position_along([{"lat": 52.3, "lng": 4.9}], 52.3, 4.9) is None
    assert position_along(_line(), None, 4.9) is None
    assert position_along(_line(), "here", 4.9) is None


def test_position_along_skips_a_stop_it_cannot_read() -> None:
    """A broken stop takes the two stretches touching it with it."""
    stops = [
        {"name": "A", "lat": 52.40, "lng": 4.90},
        {"name": "B", "lat": "?", "lng": 4.90},
        {"name": "C", "lat": 52.20, "lng": 4.90},
        {"name": "D", "lat": 52.10, "lng": 4.90},
    ]
    assert position_along(stops, 52.15, 4.90) == pytest.approx(2.5, abs=0.01)
    # Nothing readable at all: nothing to place a train on.
    assert position_along(stops[:2], 52.40, 4.90) is None


def test_position_along_handles_two_stops_at_one_spot() -> None:
    stops = [
        {"name": "A", "lat": 52.30, "lng": 4.90},
        {"name": "B", "lat": 52.30, "lng": 4.90},
    ]
    assert position_along(stops, 52.30, 4.90) == pytest.approx(0.0)
