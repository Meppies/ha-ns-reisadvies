"""Dienstkaartje: railway staff publishing their own shift (v2.27.0).

The payloads below are trimmed copies of what data.dienstkaartje.nl
answered on 2026-11-20, usernames replaced. Everything the site serves
is published by the person it is about, and the three privacy switches
in ``settings.privacy`` are theirs to set — most of what is tested
here is that those switches are obeyed.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies import (
    _ws_dienstkaartje,
    _ws_dienstkaartje_on_train,
)
from custom_components.ns_reisadvies._dienstkaartje import (
    annotate_trips,
    clean_username,
    current_leg,
    leg_on_train,
    on_train,
    parse_follow_list,
    parse_list,
    parse_profile,
    parse_usernames,
    service_numbers_of,
    trains_of,
)
from custom_components.ns_reisadvies.const import DIENSTKAARTJE_AVAILABLE, DOMAIN
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator
from custom_components.ns_reisadvies.sensor import NSReisadviesStaffSensor


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
        "dienstkaartje": True,
        "dienstkaartje_users": "machinist_jan",
    }
    defaults.update(kw)
    coord = NSUpdateCoordinator(hass, **defaults)
    coord._store = MagicMock()
    coord._store.async_save = AsyncMock()
    hass.data.setdefault(DOMAIN, {}).pop("_dienstkaartje", None)
    hass.data[DOMAIN].pop("_dienstkaartje_sweep", None)
    hass.data[DOMAIN].pop("_dk_backoff_until", None)
    return coord


PROFILE = {
    "user": {
        "username": "machinist_jan",
        "avatar": "https://s3.dutchbeard.nl/prod/public/avatar.png",
        "supporter_badge_expires_at": "2026-07-12T11:12:05+02:00",
    },
    "analytics": {"shifts": 109, "legs": 703},
    "settings": {"privacy": {
        "profile_public": True,
        "profile_unlisted": False,
        "trip_number_public": True,
        "trip_time_public": True,
        "meetups_public": True,
    }},
    "shift": {"started_at": "2026-11-20 11:18:00", "ended_at": "2026-11-20 19:12:00"},
    "legs": [
        {
            "departure_time": "2026-11-20 11:28:00",
            "departure_station": "Zutphen",
            "service_number": "3635",
            "arrival_time": "2026-11-20 12:36:00",
            "arrival_station": "'s-Hertogenbosch",
            # The site offers the route as well; it is never asked for.
            "coordinates": [[52.145, 6.195], [52.0, 6.0]],
        },
        {
            "departure_time": "2026-11-20 13:02:00",
            "departure_station": "'s-Hertogenbosch",
            "service_number": "1537",
            "arrival_time": "2026-11-20 14:10:00",
            "arrival_station": "Deventer",
            "coordinates": [],
        },
    ],
}

NOW_PAGE = {
    "data": [
        {
            "user": {"username": "conducteur_lies", "avatar": None},
            "shift": {"started_at": "2026-11-20 07:08:00",
                      "ended_at": "2026-11-20 15:30:00"},
            "meetings_count": 0,
            "same_train_count": 0,
        },
        {"user": "nope"},
        "nope",
    ],
    "meta": {"per_page": 10, "total": 28, "next_cursor": "CURSOR2"},
}


# --------------------------------------------------------------------
# usernames
# --------------------------------------------------------------------

def test_a_username_is_taken_at_face_value_but_not_blindly() -> None:
    assert clean_username(" @machinist_jan ") == "machinist_jan"
    assert clean_username("") == ""
    assert clean_username(None) == ""
    # Nothing that would leave the one endpoint it is meant for.
    assert clean_username("../admin") == ""
    assert clean_username("jan?date=2026-01-01") == ""
    assert clean_username("jan en piet") == ""
    assert clean_username("x" * 65) == ""


def test_a_name_may_carry_the_users_own_role_label() -> None:
    """Dienstkaartje publishes no role, so the label is the user's.

    Written after a colon in the follow list, shown as written, and
    never guessed at from anything the site says.
    """
    assert parse_follow_list("machinist_jan:machinist, lies : conducteur, piet") == [
        {"username": "machinist_jan", "role": "machinist"},
        {"username": "lies", "role": "conducteur"},
        {"username": "piet", "role": None},
    ]
    # A label is their word, not a code: it is trimmed, not matched.
    assert parse_follow_list("jan:  hoofd conducteur  ")[0]["role"] == "hoofd conducteur"
    assert parse_follow_list("jan:" + "x" * 50)[0]["role"] == "x" * 24
    # The same shape may also be given as objects.
    assert parse_follow_list([{"username": "jan", "role": "machinist"}]) == [
        {"username": "jan", "role": "machinist"},
    ]
    assert parse_follow_list(None) == []


def test_the_follow_list_is_read_the_way_people_type_it() -> None:
    assert parse_usernames("jan, lies;piet\nkees") == ["jan", "lies", "piet", "kees"]
    assert parse_usernames(["jan", "JAN", " jan "]) == ["jan"]
    assert parse_usernames("") == []
    assert parse_usernames(None) == []
    assert parse_usernames(42) == []


# --------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------

def test_parse_reads_a_shift_and_its_legs() -> None:
    profile = parse_profile(PROFILE)
    assert profile is not None
    assert profile["username"] == "machinist_jan"
    assert profile["on_shift"] is True
    assert profile["shift_start"] == "2026-11-20 11:18:00"
    assert [leg["service_number"] for leg in profile["legs"]] == ["3635", "1537"]
    assert profile["legs"][0]["departure_station"] == "Zutphen"
    # Only usable coordinate pairs survive.
    # A train number is all this site has to give: the route of a leg
    # is hundreds of points, and NS's own feeds already draw the train.
    assert "coordinates" not in profile["legs"][0]


def test_parse_ignores_what_is_not_a_profile() -> None:
    assert parse_profile(None) is None
    assert parse_profile([]) is None
    assert parse_profile({"user": "nope"}) is None
    assert parse_profile({"user": {"username": ""}}) is None


def test_parse_survives_a_profile_full_of_rubbish() -> None:
    odd = {
        "user": {"username": "machinist_jan"},
        "settings": {"privacy": "nope"},
        "shift": "nope",
        "legs": ["nope", {"service_number": None}],
    }
    profile = parse_profile(odd)
    assert profile is not None
    assert profile["public"] is True and profile["shift_start"] is None
    assert profile["legs"] == [{
        "service_number": None, "departure_station": None,
        "arrival_station": None, "departure_time": None,
        "arrival_time": None,
    }]
    assert trains_of(profile) == set()
    # A leg without a train number cannot match one.
    assert leg_on_train(profile, "3635") is None
    assert leg_on_train(None, "3635") is None


def test_parse_reads_a_page_of_who_is_on_a_shift() -> None:
    people, cursor = parse_list(NOW_PAGE)
    assert [person["username"] for person in people] == ["conducteur_lies"]
    assert people[0]["shift_end"] == "2026-11-20 15:30:00"
    assert cursor == "CURSOR2"
    assert parse_list(None) == ([], None)
    assert parse_list({"data": []}) == ([], None)
    # A row without a usable username is skipped, not guessed at.
    assert parse_list({"data": [{"user": {"username": "  "}}]}) == ([], None)


# --------------------------------------------------------------------
# the privacy switches
# --------------------------------------------------------------------

def _private(**privacy) -> dict:
    payload = {**PROFILE, "settings": {"privacy": {**PROFILE["settings"]["privacy"],
                                                   **privacy}}}
    return payload


def test_a_hidden_profile_tells_nobody_anything() -> None:
    profile = parse_profile(_private(profile_public=False))
    assert profile is not None and profile["public"] is False
    assert trains_of(profile) == set()
    assert leg_on_train(profile, "3635") is None
    assert on_train([profile], "3635") == []
    assert current_leg(profile, "2026-11-20 11:30:00") is None
    assert current_leg(None, "2026-11-20 11:30:00") is None


def test_hidden_train_numbers_mean_nobody_is_matched_to_a_train() -> None:
    profile = parse_profile(_private(trip_number_public=False))
    assert profile is not None and profile["shows_train_numbers"] is False
    assert trains_of(profile) == set()
    assert on_train([profile], "3635") == []


def test_what_is_withheld_is_dropped_on_the_way_in() -> None:
    """The API answers with it anyway; it stops here, not at the card.

    dienstkaartje.nl's own site drops the numbers and times while
    drawing the page, so the data arrives whatever the switches say.
    Dropping it in the parser means no websocket answer, sensor
    attribute or card has to remember to.
    """
    quiet = parse_profile(_private(trip_number_public=False, trip_time_public=False))
    assert quiet is not None
    assert [leg["service_number"] for leg in quiet["legs"]] == [None, None]
    assert [leg["departure_time"] for leg in quiet["legs"]] == [None, None]
    assert quiet["shift_start"] is None and quiet["shift_end"] is None
    # The stations are not one of the three switches, so they stay.
    assert quiet["legs"][0]["departure_station"] == "Zutphen"

    hidden = parse_profile(_private(profile_public=False))
    assert hidden is not None
    assert [leg["service_number"] for leg in hidden["legs"]] == [None, None]


def test_hidden_times_leave_the_times_out_rather_than_guessing() -> None:
    profile = parse_profile(_private(trip_time_public=False))
    found = on_train([profile], "3635")
    assert len(found) == 1
    assert found[0]["from"] == "Zutphen" and found[0]["to"] == "'s-Hertogenbosch"
    assert found[0]["departure"] is None and found[0]["arrival"] is None


def test_a_public_profile_says_which_train_and_which_stretch() -> None:
    profile = parse_profile(PROFILE)
    assert trains_of(profile) == {"3635", "1537"}
    found = on_train([profile], "1537")
    assert found == [{
        "username": "machinist_jan",
        "avatar": "https://s3.dutchbeard.nl/prod/public/avatar.png",
        "role": None,
        "from": "'s-Hertogenbosch",
        "to": "Deventer",
        "departure": "2026-11-20 13:02:00",
        "arrival": "2026-11-20 14:10:00",
    }]
    assert on_train([profile], "9999") == []
    assert on_train([profile], None) == []
    assert on_train([], "1537") == []


# --------------------------------------------------------------------
# hanging people on a journey
# --------------------------------------------------------------------

def _trips() -> list[dict]:
    return [{
        "legs": [
            {"product": {"number": "1537"}, "name": "IC 1537"},
            {"product": {"number": "4321"}, "name": "SPR 4321"},
            "nope",
        ],
    }, "nope"]


def test_train_numbers_are_read_off_a_journey() -> None:
    assert service_numbers_of(_trips()) == ["1537", "4321"]
    assert service_numbers_of(None) == []
    # The same train twice in one journey is one number, and a leg
    # without a product is skipped rather than guessed at.
    twice = [{"legs": [{"product": {"number": "1537"}}, {"product": {}},
                       {"product": {"number": "1537"}}]}]
    assert service_numbers_of(twice) == ["1537"]


def test_annotating_puts_the_people_on_the_leg_they_are_on() -> None:
    trips = _trips()
    annotate_trips(trips, [parse_profile(PROFILE)])
    legs = trips[0]["legs"]
    assert [person["username"] for person in legs[0]["staff"]] == ["machinist_jan"]
    assert "staff" not in legs[1]


def test_annotating_clears_what_is_no_longer_true() -> None:
    trips = _trips()
    trips[0]["legs"][0]["staff"] = [{"username": "someone_who_went_home"}]
    annotate_trips(trips, [parse_profile(_private(trip_number_public=False))])
    assert "staff" not in trips[0]["legs"][0]
    # And with nobody followed at all, nothing is touched.
    trips = _trips()
    trips[0]["legs"][0]["staff"] = [{"username": "left_alone"}]
    annotate_trips(trips, [])
    assert trips[0]["legs"][0]["staff"] == [{"username": "left_alone"}]


# --------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------

async def test_fetch_asks_the_one_endpoint_and_caches_it(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, PROFILE))

    profile = await coord.async_fetch_dienstkaartje("machinist_jan")
    assert profile is not None and profile["username"] == "machinist_jan"
    url = coord._session.get.call_args[0][0]
    assert url.endswith("/dienstkaartje/machinist_jan")
    assert coord._session.get.call_args.kwargs["params"] is None

    # Second ask inside the cache window costs nothing.
    await coord.async_fetch_dienstkaartje("machinist_jan")
    assert coord._session.get.call_count == 1

    # Another date is its own question, and its own cache entry. The
    # route of a leg is never asked for at all: a train number is
    # enough, and NS's own feeds draw the train.
    await coord.async_fetch_dienstkaartje("machinist_jan", date="2026-11-21")
    assert coord._session.get.call_args.kwargs["params"] == {"date": "2026-11-21"}
    assert "include_route" not in str(coord._session.get.call_args)


async def test_fetch_leaves_a_private_profile_alone(hass: HomeAssistant) -> None:
    """401, 403 and 404 are answers, not errors."""
    coord = _coord(hass)
    coord._session = MagicMock()
    for status in (401, 403, 404):
        hass.data[DOMAIN].pop("_dienstkaartje", None)
        coord._session.get = MagicMock(return_value=_resp(status))
        assert await coord.async_fetch_dienstkaartje("machinist_jan") is None


async def test_fetch_takes_a_rate_limit_at_its_word(hass: HomeAssistant) -> None:
    """A 429 buys the whole site a rest, not a retry."""
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(429))
    assert await coord.async_fetch_dienstkaartje("machinist_jan") is None
    assert coord._session.get.call_count == 1

    # Nothing else is asked while the backoff runs, not even about
    # somebody else.
    assert await coord.async_fetch_dienstkaartje("conducteur_lies") is None
    assert await coord.async_sweep_dienstkaartje() == []
    assert coord._session.get.call_count == 1


async def test_fetch_keeps_what_it_knew_when_the_site_is_quiet(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, PROFILE))
    assert await coord.async_fetch_dienstkaartje("machinist_jan") is not None

    # Expire the cache, then let the site fail.
    cache = hass.data[DOMAIN]["_dienstkaartje"]
    for entry in cache.values():
        entry["at"] = 0.0
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("down"))
    stale = await coord.async_fetch_dienstkaartje("machinist_jan")
    assert stale is not None and stale["username"] == "machinist_jan"

    coord._session.get = MagicMock(side_effect=asyncio.TimeoutError())
    assert await coord.async_fetch_dienstkaartje("machinist_jan") is not None


async def test_fetch_needs_a_usable_name(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, PROFILE))
    assert await coord.async_fetch_dienstkaartje("../admin") is None
    coord._session.get.assert_not_called()


async def test_followed_is_empty_until_it_is_switched_on(
    hass: HomeAssistant,
) -> None:
    off = _coord(hass, dienstkaartje=False)
    off._session = MagicMock()
    assert await off.async_fetch_dienstkaartje_followed() == []
    off._session.get.assert_not_called()

    nobody = _coord(hass, dienstkaartje_users="")
    nobody._session = MagicMock()
    assert await nobody.async_fetch_dienstkaartje_followed() == []
    nobody._session.get.assert_not_called()


async def test_the_role_label_travels_with_the_person(
    hass: HomeAssistant,
) -> None:
    """It is the user's label, so it is attached here, not read."""
    coord = _coord(hass, dienstkaartje_users="machinist_jan:machinist")
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, PROFILE))
    people = await coord.async_fetch_dienstkaartje_followed()
    assert people[0]["role"] == "machinist"
    # The shared cache keeps the profile as the site sent it, so one
    # user's label cannot leak into another installation's view.
    cached = await coord.async_fetch_dienstkaartje("machinist_jan")
    assert cached is not None and "role" not in cached

    trips = _trips()
    annotate_trips(trips, people)
    assert trips[0]["legs"][0]["staff"][0]["role"] == "machinist"


async def test_followed_asks_after_the_named_people_only(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, dienstkaartje_users="machinist_jan, conducteur_lies")
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, PROFILE))
    people = await coord.async_fetch_dienstkaartje_followed()
    assert len(people) == 2
    asked = [call[0][0].rsplit("/", 1)[-1] for call in coord._session.get.call_args_list]
    assert sorted(asked) == ["conducteur_lies", "machinist_jan"]


async def test_the_follow_list_has_a_ceiling(hass: HomeAssistant) -> None:
    """Every name costs a request per refresh on someone else's server."""
    coord = _coord(hass, dienstkaartje_users=",".join(f"user{n}" for n in range(25)))
    assert len(coord.dienstkaartje_users) == 10


async def test_sweep_walks_the_list_then_asks_about_each_person(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    last_page = {"data": NOW_PAGE["data"], "meta": {"next_cursor": None}}
    coord._session.get = MagicMock(side_effect=[
        _resp(200, NOW_PAGE), _resp(200, last_page),
        _resp(200, PROFILE), _resp(200, PROFILE),
    ])
    profiles = await coord.async_sweep_dienstkaartje()
    assert [p["username"] for p in profiles] == ["machinist_jan", "machinist_jan"]
    first, second = coord._session.get.call_args_list[:2]
    assert first.kwargs["params"] is None
    assert second.kwargs["params"] == {"cursor": "CURSOR2"}

    # It is the expensive question, so the answer is shared.
    coord._session.get = MagicMock(return_value=_resp(200, NOW_PAGE))
    await coord.async_sweep_dienstkaartje()
    coord._session.get.assert_not_called()


async def test_sweep_stays_off_until_it_is_switched_on(hass: HomeAssistant) -> None:
    coord = _coord(hass, dienstkaartje=False)
    coord._session = MagicMock()
    assert await coord.async_sweep_dienstkaartje() == []
    coord._session.get.assert_not_called()


# --------------------------------------------------------------------
# the refresh and the search
# --------------------------------------------------------------------

def _ns_trips() -> list[dict]:
    from datetime import datetime, timedelta, timezone
    soon = datetime.now(timezone.utc) + timedelta(minutes=30)
    return [{
        "ctxRecon": "CTX-1",
        "legs": [{
            "product": {"number": "1537", "categoryCode": "IC"},
            "origin": {"name": "Deventer", "plannedDateTime": soon.isoformat()},
            "destination": {"name": "Zwolle",
                            "plannedDateTime": (soon + timedelta(minutes=30)).isoformat()},
        }],
    }]


async def test_a_refresh_hangs_the_followed_people_on_the_trains(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, disruptions=False)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"trips": _ns_trips()}), _resp(200, PROFILE),
    ])
    trips = await coord._async_update_data()
    assert [p["username"] for p in trips[0]["legs"][0]["staff"]] == ["machinist_jan"]
    assert [p["username"] for p in coord.dienstkaartje] == ["machinist_jan"]


async def test_a_refresh_asks_nobody_when_it_is_switched_off(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, disruptions=False, dienstkaartje=False)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": _ns_trips()}))
    trips = await coord._async_update_data()
    assert "staff" not in trips[0]["legs"][0]
    assert coord.dienstkaartje == []
    assert coord._session.get.call_count == 1


async def test_a_search_is_annotated_the_same_way(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"trips": _ns_trips()}), _resp(200, PROFILE),
    ])
    trips, problem = await coord.async_search_trips("Deventer", "Zwolle")
    assert problem is None
    assert [p["username"] for p in trips[0]["legs"][0]["staff"]] == ["machinist_jan"]


# --------------------------------------------------------------------
# the websocket commands behind the cards
# --------------------------------------------------------------------

dienstkaartje_inner = _ws_dienstkaartje.__wrapped__  # type: ignore[attr-defined]
on_train_inner = _ws_dienstkaartje_on_train.__wrapped__  # type: ignore[attr-defined]


def _hass_with(coord):
    runtime = MagicMock()
    runtime.coordinators = {"sub": coord}
    runtime.live_sessions = {}
    entry = MagicMock()
    entry.runtime_data = runtime
    fake = MagicMock()
    fake.config_entries.async_entries.return_value = [entry]
    return fake


def _mock_coord(profiles, *, enabled=True):
    coord = MagicMock()
    coord.watch_dienstkaartje = enabled
    coord.dienstkaartje_users = ["machinist_jan"]
    coord.dienstkaartje_follow = [{"username": "machinist_jan", "role": "machinist"}]
    coord.async_fetch_dienstkaartje_followed = AsyncMock(return_value=profiles)
    coord.async_sweep_dienstkaartje = AsyncMock(return_value=profiles)
    return coord


async def test_ws_hands_over_the_follow_list() -> None:
    coord = _mock_coord([parse_profile(PROFILE)])
    conn = MagicMock()
    await dienstkaartje_inner(_hass_with(coord), conn, {"id": 1})
    answer = conn.send_result.call_args[0][1]
    assert answer["enabled"] is True
    assert answer["following"] == [{"username": "machinist_jan", "role": "machinist"}]
    assert [p["username"] for p in answer["people"]] == ["machinist_jan"]
    coord.async_fetch_dienstkaartje_followed.assert_awaited_once()


async def test_ws_never_asks_the_site_for_a_route() -> None:
    """A train number is enough; NS's own feeds draw the train."""
    coord = _mock_coord([parse_profile(PROFILE)])
    await dienstkaartje_inner(_hass_with(coord), MagicMock(), {"id": 1})
    coord.async_fetch_dienstkaartje_followed.assert_awaited_once_with()


async def test_ws_says_so_when_it_is_switched_off() -> None:
    coord = _mock_coord([], enabled=False)
    conn = MagicMock()
    await dienstkaartje_inner(_hass_with(coord), conn, {"id": 1})
    assert conn.send_result.call_args[0][1] == {"enabled": False, "people": []}
    coord.async_fetch_dienstkaartje_followed.assert_not_awaited()

    conn = MagicMock()
    await on_train_inner(_hass_with(coord), conn, {"id": 1, "trains": ["1537"]})
    assert conn.send_result.call_args[0][1] == {"enabled": False, "trains": {}}
    coord.async_sweep_dienstkaartje.assert_not_awaited()


async def test_ws_on_train_answers_only_about_the_trains_it_was_asked() -> None:
    coord = _mock_coord([parse_profile(PROFILE)])
    conn = MagicMock()
    await on_train_inner(
        _hass_with(coord), conn, {"id": 1, "trains": ["1537", "9999", "  "]},
    )
    answer = conn.send_result.call_args[0][1]
    assert list(answer["trains"]) == ["1537"]
    assert answer["checked"] == 1


# --------------------------------------------------------------------
# dormant until dienstkaartje.nl has been asked
# --------------------------------------------------------------------

def test_the_whole_thing_is_switched_off_at_the_source() -> None:
    """Shipped but not running, pending the site author's answer.

    The code is here and tested; the flag is what lets anyone use it,
    and until dienstkaartje.nl says the traffic is welcome it stays
    false. Flipping it is the whole release.
    """
    assert DIENSTKAARTJE_AVAILABLE is False


async def test_the_hub_ignores_the_option_while_it_is_dormant(
    hass: HomeAssistant, monkeypatch,
) -> None:
    """Even an option set by hand does not start it."""
    from custom_components.ns_reisadvies import _option

    entry = MagicMock()
    entry.options = {"dienstkaartje": True, "dienstkaartje_users": "machinist_jan"}
    entry.data = {}
    assert _option(entry, "dienstkaartje", False) is True
    # ...but what the hub passes to a coordinator is the flag first.
    assert (DIENSTKAARTJE_AVAILABLE and _option(entry, "dienstkaartje", False)) is False


def test_the_options_form_does_not_offer_it_while_it_is_dormant() -> None:
    from custom_components.ns_reisadvies.config_flow import NSReisadviesOptionsFlowHandler

    handler = NSReisadviesOptionsFlowHandler.__new__(NSReisadviesOptionsFlowHandler)
    handler._read = lambda key, default=None: default  # type: ignore[method-assign]
    keys = {str(key) for key in handler._build_schema().schema}
    assert "dienstkaartje" not in keys
    assert "dienstkaartje_users" not in keys
    # The settings it does offer are untouched.
    assert "disruptions" in keys


def test_one_flag_is_all_that_stands_between_it_and_the_user(
    monkeypatch,
) -> None:
    """What flipping DIENSTKAARTJE_AVAILABLE does, without shipping it."""
    from custom_components.ns_reisadvies import config_flow

    monkeypatch.setattr(config_flow, "DIENSTKAARTJE_AVAILABLE", True)
    handler = config_flow.NSReisadviesOptionsFlowHandler.__new__(
        config_flow.NSReisadviesOptionsFlowHandler,
    )
    handler._read = lambda key, default=None: default  # type: ignore[method-assign]
    keys = {str(key) for key in handler._build_schema().schema}
    assert "dienstkaartje" in keys and "dienstkaartje_users" in keys


# --------------------------------------------------------------------
# the sensor per followed person
# --------------------------------------------------------------------

def _sensor(hass: HomeAssistant, profiles, username="machinist_jan"):
    coord = _coord(hass)
    coord.dienstkaartje = profiles
    coord.last_update_success = True
    return NSReisadviesStaffSensor(coord, hub_id="hub1", username=username)


async def test_the_sensor_is_named_after_the_person(hass: HomeAssistant) -> None:
    sensor = _sensor(hass, [])
    assert sensor.entity_id == "sensor.ns_dienstkaartje_machinist_jan"
    assert sensor.unique_id == "hub1_dienstkaartje_machinist_jan"
    assert sensor.name == "Dienstkaartje machinist_jan"


async def test_the_sensor_says_off_duty_when_there_is_no_shift(
    hass: HomeAssistant,
) -> None:
    sensor = _sensor(hass, [])
    assert sensor.native_value == "off_duty"
    assert sensor.extra_state_attributes == {
        "username": "machinist_jan", "on_shift": False,
    }
    assert sensor.available is True


async def test_the_sensor_states_the_train_being_worked_right_now(
    hass: HomeAssistant, freezer,
) -> None:
    freezer.move_to("2026-11-20 13:30:00+01:00")
    sensor = _sensor(hass, [parse_profile(PROFILE)])
    assert sensor.native_value == "1537"
    attributes = sensor.extra_state_attributes
    assert attributes["on_shift"] is True
    assert attributes["trains"] == ["1537", "3635"]
    assert attributes["shift_end"] == "2026-11-20 19:12:00"
    assert attributes["legs"][0]["from"] == "Zutphen"


async def test_the_sensor_says_idle_between_trains(
    hass: HomeAssistant, freezer,
) -> None:
    freezer.move_to("2026-11-20 12:50:00+01:00")
    assert _sensor(hass, [parse_profile(PROFILE)]).native_value == "idle"


async def test_the_sensor_keeps_hidden_detail_hidden(
    hass: HomeAssistant, freezer,
) -> None:
    freezer.move_to("2026-11-20 13:30:00+01:00")
    quiet = parse_profile(_private(trip_number_public=False, trip_time_public=False))
    sensor = _sensor(hass, [quiet])
    attributes = sensor.extra_state_attributes
    assert attributes["legs"] == [] and attributes["trains"] == []
    assert attributes["shift_start"] is None and attributes["shift_end"] is None
    # Without published train numbers there is no train to name.
    assert sensor.native_value == "idle"


async def test_ws_needs_a_hub() -> None:
    fake = MagicMock()
    fake.config_entries.async_entries.return_value = []
    for handler in (dienstkaartje_inner, on_train_inner):
        conn = MagicMock()
        await handler(fake, conn, {"id": 1, "trains": []})
        assert conn.send_error.call_args[0][1] == "no_hub"
