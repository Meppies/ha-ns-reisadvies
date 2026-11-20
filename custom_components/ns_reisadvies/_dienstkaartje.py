"""Pure parsing for Dienstkaartje, kept free of Home Assistant imports.

`dienstkaartje.nl <https://dienstkaartje.nl>`_ is a hobby project by
Dutchbeard where railway staff publish the shift they are working:
which trains they are on, between which stations and at what times.
Nothing here is scraped from a roster — every profile belongs to the
person it is about, and they choose what it shows. The API answers
with their choice, so this module reads it rather than guessing:

* ``profile_public`` off, or a password set, means there is nothing to
  show; the API answers 401 or 404 and the integration leaves it there.
* ``trip_number_public`` off means the train numbers are withheld, and
  without a train number nobody can be matched to a train.
* ``trip_time_public`` off means the times are withheld, so a shift is
  shown without them rather than guessed at.

The integration therefore never knows more about someone than their
own profile page shows a stranger, and the whole feature is off until
the user switches it on and names the people to follow.

Endpoints (no key, rate limited — a 429 means slow down):

* ``/api/v1/dienstkaartje`` — who is on a shift right now
* ``/api/v1/dienstkaartje/upcoming`` — whose shift starts soon
* ``/api/v1/dienstkaartje/{username}`` — one shift and its legs

The route of a leg can be asked for as well, a few hundred coordinate
pairs per leg, and is deliberately not: a train number is enough. The
integration already draws trains from NS's own journey and vehicle
feeds and the ProRail network, so the number is all this site has to
supply, and it is the cheapest thing it can give.
"""
from __future__ import annotations

from typing import Any

#: What a username may look like before it is worth a request.
USERNAME_MAX_LENGTH = 64


def clean_username(value: Any) -> str:
    """A username as the site writes it, or an empty string."""
    name = str(value or "").strip().lstrip("@")
    if not name or len(name) > USERNAME_MAX_LENGTH:
        return ""
    if any(character in name for character in "/?&# \t"):
        return ""
    return name


#: How long a hand-written role label may be.
ROLE_MAX_LENGTH = 24


def clean_role(value: Any) -> str | None:
    """A role as the user wrote it: their own word, trimmed."""
    role = " ".join(str(value or "").split())
    if not role:
        return None
    return role[:ROLE_MAX_LENGTH]


def parse_follow_list(value: Any) -> list[dict[str, Any]]:
    """The follow list as typed in the options, in order, without duplicates.

    A name may carry a role after a colon — ``machinist_jan:machinist``
    — because Dienstkaartje publishes no such thing: its API knows a
    username, a picture and a shift, and nothing about what the person
    does on the train. The label is therefore the user's own word for
    somebody they know, not a fact read off the site, and it is shown
    as written rather than matched against a list.
    """
    if isinstance(value, str):
        parts: list[Any] = value.replace(";", ",").replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for part in parts:
        if isinstance(part, dict):
            raw_name: Any = part.get("username")
            raw_role: Any = part.get("role")
        else:
            text = str(part or "")
            raw_name, _, raw_role = text.partition(":")
        name = clean_username(raw_name)
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        out.append({"username": name, "role": clean_role(raw_role)})
    return out


def parse_usernames(value: Any) -> list[str]:
    """Just the names from the follow list, in order."""
    return [entry["username"] for entry in parse_follow_list(value)]


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _leg(
    entry: Any, *, with_numbers: bool = True, with_times: bool = True,
) -> dict[str, Any] | None:
    """One leg of a shift, minus whatever its owner withholds.

    The API answers with the train numbers and times even when the
    profile hides them — its own website drops them while drawing the
    page. Dropping them here instead means nothing downstream has to
    remember to: not the websocket, not the sensor attributes, not the
    card.
    """
    if not isinstance(entry, dict):
        return None
    return {
        "service_number": _text(entry.get("service_number")) if with_numbers else None,
        "departure_station": _text(entry.get("departure_station")),
        "arrival_station": _text(entry.get("arrival_station")),
        "departure_time": _text(entry.get("departure_time")) if with_times else None,
        "arrival_time": _text(entry.get("arrival_time")) if with_times else None,
    }


def parse_profile(payload: Any) -> dict[str, Any] | None:
    """One person's shift, as much of it as they publish."""
    if not isinstance(payload, dict):
        return None
    user = payload.get("user")
    if not isinstance(user, dict):
        return None
    username = clean_username(user.get("username"))
    if not username:
        return None

    privacy = ((payload.get("settings") or {}).get("privacy") or {})
    if not isinstance(privacy, dict):
        privacy = {}
    public = privacy.get("profile_public") is not False
    shows_numbers = public and privacy.get("trip_number_public") is not False
    shows_times = public and privacy.get("trip_time_public") is not False
    shift = payload.get("shift") if isinstance(payload.get("shift"), dict) else None
    legs = [
        leg
        for leg in (
            _leg(item, with_numbers=shows_numbers, with_times=shows_times)
            for item in payload.get("legs") or []
        )
        if leg
    ]

    return {
        "username": username,
        "avatar": _text(user.get("avatar")),
        "supporter_until": _text(user.get("supporter_badge_expires_at")),
        # The three switches the person themselves set.
        "public": public,
        "shows_train_numbers": shows_numbers,
        "shows_times": shows_times,
        "shift_start": _text((shift or {}).get("started_at")) if shows_times else None,
        "shift_end": _text((shift or {}).get("ended_at")) if shows_times else None,
        "legs": legs,
        "on_shift": bool(shift) or bool(legs),
    }


def parse_list(payload: Any) -> tuple[list[dict[str, Any]], str | None]:
    """A page of who is on a shift: the people and the next cursor."""
    if not isinstance(payload, dict):
        return [], None
    people: list[dict[str, Any]] = []
    for entry in payload.get("data") or []:
        if not isinstance(entry, dict):
            continue
        user = entry.get("user")
        if not isinstance(user, dict):
            continue
        username = clean_username(user.get("username"))
        if not username:
            continue
        people.append({
            "username": username,
            "avatar": _text(user.get("avatar")),
            "shift_start": _text((entry.get("shift") or {}).get("started_at")),
            "shift_end": _text((entry.get("shift") or {}).get("ended_at")),
        })
    raw_meta = payload.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    cursor = _text(meta.get("next_cursor"))
    return people, cursor


def trains_of(profile: dict[str, Any] | None) -> set[str]:
    """The train numbers in a shift, where the person publishes them."""
    if not profile or not profile.get("public") or not profile.get("shows_train_numbers"):
        return set()
    return {
        str(leg["service_number"])
        for leg in profile.get("legs") or []
        if leg.get("service_number")
    }


def leg_on_train(
    profile: dict[str, Any] | None, service_number: Any,
) -> dict[str, Any] | None:
    """The leg of this shift that is on that train, if any."""
    number = _text(service_number)
    if not number or not profile:
        return None
    if not profile.get("public") or not profile.get("shows_train_numbers"):
        return None
    for leg in profile.get("legs") or []:
        if str(leg.get("service_number") or "") == number:
            found: dict[str, Any] = leg
            return found
    return None


def current_leg(
    profile: dict[str, Any] | None, now_text: str,
) -> dict[str, Any] | None:
    """The leg being worked at ``now_text``, if there is one.

    The site writes its times as Dutch wall clock without a zone
    ("2026-11-20 13:02:00"), so the caller passes the same clock and
    the comparison is a string one — no zone guessing in here.
    """
    if not profile or not profile.get("public"):
        return None
    for leg in profile.get("legs") or []:
        start = leg.get("departure_time")
        end = leg.get("arrival_time")
        if start and end and str(start) <= now_text <= str(end):
            running: dict[str, Any] = leg
            return running
    return None


def on_train(
    profiles: list[dict[str, Any]], service_number: Any,
) -> list[dict[str, Any]]:
    """Everyone in this set of profiles who is on that train.

    The answer carries only what the card shows: who, their picture,
    and which stretch of the train's run they are on.
    """
    out: list[dict[str, Any]] = []
    for profile in profiles or []:
        leg = leg_on_train(profile, service_number)
        if leg is None:
            continue
        out.append({
            "username": profile["username"],
            "avatar": profile.get("avatar"),
            # The user's own label for this person, where they gave one.
            "role": profile.get("role"),
            "from": leg.get("departure_station"),
            "to": leg.get("arrival_station"),
            "departure": leg.get("departure_time") if profile.get("shows_times") else None,
            "arrival": leg.get("arrival_time") if profile.get("shows_times") else None,
        })
    return out


def service_numbers_of(trips: Any) -> list[str]:
    """Every train number in a set of planned journeys, in order."""
    numbers: list[str] = []
    seen: set[str] = set()
    for trip in trips or []:
        if not isinstance(trip, dict):
            continue
        for leg in trip.get("legs") or []:
            if not isinstance(leg, dict):
                continue
            number = _text((leg.get("product") or {}).get("number"))
            if not number or number in seen:
                continue
            seen.add(number)
            numbers.append(number)
    return numbers


def annotate_trips(
    trips: Any, profiles: list[dict[str, Any]],
) -> None:
    """Hang the people on each leg's train under ``leg["staff"]``.

    Mutating the trips in place is how the composition is attached as
    well, so the cards find both in the same place.
    """
    if not profiles:
        return
    for trip in trips or []:
        if not isinstance(trip, dict):
            continue
        for leg in trip.get("legs") or []:
            if not isinstance(leg, dict):
                continue
            people = on_train(profiles, (leg.get("product") or {}).get("number"))
            if people:
                leg["staff"] = people
            else:
                leg.pop("staff", None)
