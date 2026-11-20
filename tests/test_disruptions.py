"""NS disruptions (v2.25.0).

The feed answers with two different kinds of thing under one roof: a
stretch of railway with a problem (DISRUPTION, MAINTENANCE), which
carries timespans and every affected station with its coordinates, and
an announcement (CALAMITY), which carries a description and no stations
at all. The payloads below are trimmed copies of what the live API
returned on 2026-11-20.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies import _ws_disruptions
from custom_components.ns_reisadvies._disruptions import (
    affecting,
    of_types,
    parse_disruptions,
    station_keys_of,
)
from custom_components.ns_reisadvies.const import DOMAIN
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator


def _resp(status, payload=None):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=payload if payload is not None else [])
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


def _coord(hass: HomeAssistant, **kw) -> NSUpdateCoordinator:
    defaults = {"api_key": "k", "from_station": "A", "to_station": "B"}
    defaults.update(kw)
    coord = NSUpdateCoordinator(hass, **defaults)
    coord._store = MagicMock()
    coord._store.async_save = AsyncMock()
    return coord


DISRUPTION = {
    "id": "6069064",
    "isActive": True,
    "title": "Arnhem - Doetinchem.",
    "type": "DISRUPTION",
    "start": "2026-11-11T06:27:00+0100",
    "end": "2026-11-20T20:30:00+0100",
    "phase": {"id": "2", "label": "Impact bekend"},
    "impact": {"value": 3},
    "expectedDuration": {
        "description": "Dit duurt ten minste tot vrijdag 20 november 20:30 uur.",
    },
    "timespans": [{
        "period": "Woensdag 11 november 6:27 uur t/m vrijdag 20 november.",
        "situation": {"label": "Door een wisselstoring rijden er minder treinen."},
        "cause": {"label": "wisselstoring", "type": "OTHER"},
        "additionalTravelTime": {
            "label": "Tot 30 minuten extra reistijd.",
            "shortLabel": "+30 min",
        },
        "alternativeTransport": {"label": "er rijden stopbussen",
                                 "shortLabel": "stopbussen"},
        "advices": ["Reis via Zutphen.", "  Houd rekening met drukte.  "],
    }],
    "publicationSections": [{
        "section": {
            "stations": [
                {"uicCode": "8400071", "stationCode": "AH", "name": "Arnhem Centraal",
                 "coordinate": {"lat": 51.985, "lng": 5.899}},
                {"uicCode": "8400193", "stationCode": "DTC", "name": "Doetinchem",
                 "coordinate": {"lat": 51.966, "lng": 6.295}},
                # The same station twice: NS repeats it across sections.
                {"uicCode": "8400071", "stationCode": "AH", "name": "Arnhem Centraal",
                 "coordinate": {"lat": 51.985, "lng": 5.899}},
                # And one without usable coordinates.
                {"uicCode": "8400999", "stationCode": "XXX", "name": "Ergens"},
            ],
        },
    }],
}

# A disruption that hits two separate lines. NS publishes one section
# per stretch, and the two stretches do not join up: drawing them as one
# run puts a line straight across country between Emmen and Almelo.
# Coordinates are the real ones from /v2/stations.
def _station(name, lat, lng, uic, code):
    return {"uicCode": uic, "stationCode": code, "name": name,
            "coordinate": {"lat": lat, "lng": lng}}


TWO_SECTIONS = {
    "id": "6069100",
    "isActive": True,
    "title": "Zwolle - Emmen en Almelo - Hardenberg.",
    "type": "MAINTENANCE",
    "timespans": [{"situation": {"label": "Er rijden bussen."}}],
    "publicationSections": [
        {"section": {"stations": [
            _station("Zwolle", 52.50472, 6.09194, "8400747", "ZL"),
            _station("Dalfsen", 52.49833, 6.25861, "8400167", "DL"),
            _station("Ommen", 52.50945, 6.41583, "8400487", "OMN"),
            _station("Mariënberg", 52.50945, 6.57528, "8400428", "MRB"),
            _station("Hardenberg", 52.57278, 6.62861, "8400293", "HDB"),
            _station("Gramsbergen", 52.60917, 6.67583, "8400259", "GBG"),
            _station("Coevorden", 52.66361, 6.73556, "8400153", "CO"),
            _station("Dalen", 52.69417, 6.75806, "8400161", "DLN"),
            _station("Nieuw Amsterdam", 52.71861, 6.84861, "8400454", "NA"),
            _station("Emmen Zuid", 52.74887, 6.87478, "8400407", "EMNZ"),
            _station("Emmen", 52.79, 6.89944, "8400208", "EMN"),
        ]}},
        {"section": {"stations": [
            _station("Almelo", 52.35806, 6.65389, "8400051", "AML"),
            _station("Vriezenveen", 52.40203, 6.60041, "8400664", "VZ"),
            _station("Vroomshoop", 52.45719, 6.56967, "8400666", "VHP"),
            _station("Daarlerveen", 52.44077, 6.57599, "8400164", "DA"),
            _station("Mariënberg", 52.50945, 6.57528, "8400428", "MRB"),
            _station("Hardenberg", 52.57278, 6.62861, "8400293", "HDB"),
        ]}},
    ],
}

CALAMITY = {
    "id": "5ac72127",
    "isActive": True,
    "title": "Werkzaamheden Meppel-Leeuwarden",
    "type": "CALAMITY",
    "description": "Tussen Meppel en Leeuwarden rijden bussen.",
    "priority": "PRIO_3",
    "bodyItems": [{"type": "TEXT", "content": {"text": "<p>NS zet bussen in. </p>"}}],
    "url": "https://www.ns.nl/reizen/berichten/gevolgen",
}


# --------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------

def test_parse_reads_a_stretch_of_railway() -> None:
    parsed = parse_disruptions([DISRUPTION])
    assert len(parsed) == 1
    item = parsed[0]
    assert item["id"] == "6069064"
    assert item["type"] == "DISRUPTION"
    assert item["summary"] == "Door een wisselstoring rijden er minder treinen."
    assert item["cause"] == "wisselstoring"
    assert item["impact"] == 3
    assert item["phase"] == "Impact bekend"
    assert item["extra_travel_time"] == "+30 min"
    assert item["alternative_transport"] == "stopbussen"
    assert item["advices"] == ["Reis via Zutphen.", "Houd rekening met drukte."]
    assert item["expected_until"].startswith("Dit duurt")


def test_parse_keeps_each_station_once_with_its_coordinates() -> None:
    item = parse_disruptions([DISRUPTION])[0]
    names = [s["name"] for s in item["stations"]]
    assert names == ["Arnhem Centraal", "Doetinchem", "Ergens"]
    assert item["stations"][0]["lat"] == pytest.approx(51.985)
    # No coordinates is not a reason to drop a station from the list.
    assert item["stations"][2]["lat"] is None
    assert "8400071" in item["station_keys"] and "AH" in item["station_keys"]


def test_parse_keeps_one_stretch_as_one_run() -> None:
    item = parse_disruptions([DISRUPTION])[0]
    assert [[s["name"] for s in run] for run in item["sections"]] == [
        ["Arnhem Centraal", "Doetinchem", "Ergens"],
    ]


def test_parse_keeps_two_stretches_apart() -> None:
    """One disruption, two lines: two runs, so the map draws two lines.

    Joined into one list, the map would draw Emmen - Almelo straight
    across country, which is the artefact this guards against.
    """
    item = parse_disruptions([TWO_SECTIONS])[0]
    runs = item["sections"]
    assert len(runs) == 2
    assert [runs[0][0]["name"], runs[0][-1]["name"]] == ["Zwolle", "Emmen"]
    assert [runs[1][0]["name"], runs[1][-1]["name"]] == ["Almelo", "Hardenberg"]
    assert all(s["lat"] is not None for run in runs for s in run)

    # The flat list behind matching and the attributes holds each
    # station once, even where two stretches share one.
    names = [s["name"] for s in item["stations"]]
    assert len(names) == len(set(names)) == 15
    assert names.count("Mariënberg") == 1
    assert "8400428" in item["station_keys"] and "MRB" in item["station_keys"]


def test_parse_reads_an_announcement() -> None:
    """A calamity has no stretch: a title, a description and a link."""
    item = parse_disruptions([CALAMITY])[0]
    assert item["type"] == "CALAMITY"
    assert item["summary"] == "Tussen Meppel en Leeuwarden rijden bussen."
    assert item["stations"] == [] and item["station_keys"] == []
    assert item["sections"] == []
    assert item["url"].endswith("/gevolgen")
    assert item["impact"] is None and item["cause"] is None


def test_parse_falls_back_through_what_it_has() -> None:
    bare = {"id": "1", "type": "CALAMITY", "title": "Stroomstoring",
            "bodyItems": [{"content": {"text": "<b>Geen treinverkeer.</b>"}}]}
    assert parse_disruptions([bare])[0]["summary"] == "Geen treinverkeer."
    title_only = {"id": "2", "type": "CALAMITY", "title": "Alleen een titel"}
    assert parse_disruptions([title_only])[0]["summary"] == "Alleen een titel"


def test_parse_ignores_what_is_not_a_disruption() -> None:
    assert parse_disruptions(None) == []
    assert parse_disruptions({"payload": []}) == []
    assert parse_disruptions(["nope"]) == []
    assert parse_disruptions([{"id": "1", "type": "SOMETHING_ELSE"}]) == []
    odd = {"id": "1", "type": "DISRUPTION", "title": "T",
           "timespans": "nope", "publicationSections": ["nope", {"section": "nope"},
                                                        {"section": {"stations": ["x"]}}]}
    item = parse_disruptions([odd])[0]
    assert item["stations"] == [] and item["sections"] == []
    assert item["summary"] == "T"


# --------------------------------------------------------------------
# matching a route
# --------------------------------------------------------------------

def _trips() -> list[dict]:
    return [{
        "legs": [{
            "origin": {"name": "Arnhem Centraal", "uicCode": "8400071"},
            "destination": {"name": "Zutphen", "uicCode": "8400712"},
            "stops": [
                {"name": "Arnhem Velperpoort", "uicCode": "8400072"},
                {"name": "Dieren", "stationCode": "DVN"},
                "nope",
            ],
        }, "nope"],
    }, "nope"]


def test_station_keys_cover_the_whole_journey() -> None:
    """Not just the ends: the trouble is usually somewhere in between."""
    keys = station_keys_of(_trips())
    assert "8400071" in keys and "8400712" in keys
    assert "8400072" in keys and "DVN" in keys
    assert station_keys_of(None) == set()


def test_affecting_matches_a_station_on_the_journey() -> None:
    items = parse_disruptions([DISRUPTION, CALAMITY])
    mine = affecting(items, station_keys_of(_trips()))
    assert {item["type"] for item in mine} == {"DISRUPTION", "CALAMITY"}


def test_affecting_leaves_out_other_parts_of_the_country() -> None:
    items = parse_disruptions([DISRUPTION, CALAMITY])
    elsewhere = affecting(items, {"8400621", "ASD"})
    # The announcement is national news and stays; the stretch does not.
    assert [item["type"] for item in elsewhere] == ["CALAMITY"]


def test_affecting_without_a_journey_keeps_only_the_announcements() -> None:
    items = parse_disruptions([DISRUPTION, CALAMITY])
    assert [item["type"] for item in affecting(items, set())] == ["CALAMITY"]


def test_of_types_narrows_to_what_was_asked_for() -> None:
    items = parse_disruptions([DISRUPTION, CALAMITY])
    assert len(of_types(items, None)) == 2
    assert len(of_types(items, [])) == 2
    assert [i["type"] for i in of_types(items, ["calamity"])] == ["CALAMITY"]
    assert of_types(items, ["MAINTENANCE"]) == []


# --------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------

async def test_fetch_needs_a_key(hass: HomeAssistant) -> None:
    assert await _coord(hass, api_key="").async_fetch_disruptions() == []


async def test_fetch_parses_and_shares(hass: HomeAssistant) -> None:
    """One national request serves every route that asks."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, [DISRUPTION, CALAMITY]))
    items = await coord.async_fetch_disruptions()
    assert [item["type"] for item in items] == ["DISRUPTION", "CALAMITY"]
    assert coord._session.get.call_args.kwargs["params"] == {"isActive": "true"}

    other = _coord(hass)
    other._session = MagicMock()
    other._session.get = MagicMock(return_value=_resp(200, []))
    assert len(await other.async_fetch_disruptions()) == 2
    other._session.get.assert_not_called()


async def test_fetch_survives_a_bad_answer(hass: HomeAssistant) -> None:
    hass.data.setdefault(DOMAIN, {}).pop("_disruptions", None)
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(503))
    assert await coord.async_fetch_disruptions() == []

    hass.data[DOMAIN].pop("_disruptions", None)
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("down"))
    assert await coord.async_fetch_disruptions() == []

    hass.data[DOMAIN].pop("_disruptions", None)
    coord._session.get = MagicMock(side_effect=asyncio.TimeoutError())
    assert await coord.async_fetch_disruptions() == []


def _clean_trips() -> list[dict]:
    """What NS really returns, without the rubbish the parser tolerates.

    Timed from now, because a trip that has already left is dropped
    before the disruptions are matched against it.
    """
    soon = datetime.now(timezone.utc) + timedelta(minutes=30)
    later = soon + timedelta(minutes=30)
    return [{
        "ctxRecon": "CTX-1",
        "legs": [{
            "origin": {"name": "Arnhem Centraal", "uicCode": "8400071",
                       "plannedDateTime": soon.isoformat()},
            "destination": {"name": "Zutphen", "uicCode": "8400712",
                            "plannedDateTime": later.isoformat()},
            "stops": [{"name": "Dieren", "stationCode": "DVN"}],
        }],
    }]


async def test_refresh_fills_both_lists(hass: HomeAssistant) -> None:
    """The route list is the national one, narrowed to this journey."""
    coord = _coord(hass)
    coord.async_fetch_disruptions = AsyncMock(
        return_value=parse_disruptions([DISRUPTION, CALAMITY]),
    )
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": _clean_trips()}))
    await coord._async_update_data()
    assert len(coord.disruptions) == 2
    assert {item["type"] for item in coord.route_disruptions} == {
        "DISRUPTION", "CALAMITY",
    }


async def test_refresh_leaves_them_empty_when_switched_off(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, disruptions=False)
    coord.async_fetch_disruptions = AsyncMock(return_value=["should not be used"])
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": _clean_trips()}))
    await coord._async_update_data()
    assert coord.disruptions == [] and coord.route_disruptions == []
    coord.async_fetch_disruptions.assert_not_awaited()


# --------------------------------------------------------------------
# the websocket command behind the card
# --------------------------------------------------------------------

disruptions_inner = _ws_disruptions.__wrapped__  # type: ignore[attr-defined]


def _hass_with(coord, trips=None):
    runtime = MagicMock()
    runtime.coordinators = {"sub": coord}
    runtime.live_sessions = {}
    entry = MagicMock()
    entry.runtime_data = runtime
    fake = MagicMock()
    fake.config_entries.async_entries.return_value = [entry]
    coord.data = trips if trips is not None else []
    return fake


def _mock_coord(items):
    coord = MagicMock()
    coord.async_fetch_disruptions = AsyncMock(return_value=items)
    return coord


async def test_ws_disruptions_hands_over_the_whole_country() -> None:
    coord = _mock_coord(parse_disruptions([DISRUPTION, CALAMITY]))
    conn = MagicMock()
    await disruptions_inner(_hass_with(coord), conn, {"id": 1, "scope": "all"})
    items = conn.send_result.call_args[0][1]["disruptions"]
    assert [item["type"] for item in items] == ["DISRUPTION", "CALAMITY"]


async def test_ws_disruptions_narrows_to_the_kinds_asked_for() -> None:
    coord = _mock_coord(parse_disruptions([DISRUPTION, CALAMITY]))
    conn = MagicMock()
    await disruptions_inner(
        _hass_with(coord), conn, {"id": 1, "types": ["MAINTENANCE"]},
    )
    assert conn.send_result.call_args[0][1]["disruptions"] == []


async def test_ws_disruptions_narrows_to_my_routes() -> None:
    coord = _mock_coord(parse_disruptions([DISRUPTION, CALAMITY]))
    conn = MagicMock()
    hass = _hass_with(coord, trips=_trips())
    await disruptions_inner(hass, conn, {"id": 1, "scope": "routes"})
    assert len(conn.send_result.call_args[0][1]["disruptions"]) == 2

    elsewhere = _mock_coord(parse_disruptions([DISRUPTION, CALAMITY]))
    conn = MagicMock()
    hass = _hass_with(elsewhere, trips=[{"legs": [{
        "origin": {"uicCode": "8400621"}, "destination": {"uicCode": "8400058"},
    }]}])
    await disruptions_inner(hass, conn, {"id": 1, "scope": "routes"})
    kinds = [i["type"] for i in conn.send_result.call_args[0][1]["disruptions"]]
    assert kinds == ["CALAMITY"]


async def test_ws_disruptions_narrows_to_chosen_stations() -> None:
    coord = _mock_coord(parse_disruptions([DISRUPTION, CALAMITY]))
    conn = MagicMock()
    await disruptions_inner(_hass_with(coord), conn, {
        "id": 1, "scope": "stations", "stations": [" doetinchem "],
    })
    assert len(conn.send_result.call_args[0][1]["disruptions"]) == 2

    conn = MagicMock()
    coord = _mock_coord(parse_disruptions([DISRUPTION, CALAMITY]))
    await disruptions_inner(_hass_with(coord), conn, {
        "id": 1, "scope": "stations", "stations": ["Groningen"],
    })
    kinds = [i["type"] for i in conn.send_result.call_args[0][1]["disruptions"]]
    assert kinds == ["CALAMITY"]

    # An empty list means no narrowing at all rather than nothing shown.
    conn = MagicMock()
    coord = _mock_coord(parse_disruptions([DISRUPTION, CALAMITY]))
    await disruptions_inner(_hass_with(coord), conn, {
        "id": 1, "scope": "stations", "stations": ["  "],
    })
    assert len(conn.send_result.call_args[0][1]["disruptions"]) == 2


async def test_ws_disruptions_needs_a_hub() -> None:
    fake = MagicMock()
    fake.config_entries.async_entries.return_value = []
    conn = MagicMock()
    await disruptions_inner(fake, conn, {"id": 1})
    assert conn.send_error.call_args[0][1] == "no_hub"
