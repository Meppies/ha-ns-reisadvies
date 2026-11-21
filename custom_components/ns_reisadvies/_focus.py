"""The one trip a route's automation sensors describe (v2.28.0).

A route returns several trips, but an automation wants one answer:
"which platform", "how late", "where is the train". This module
picks that trip — the *focus* — and derives everything the sensors,
binary sensors and events report about it. It is kept free of Home
Assistant and aiohttp so every rule can be tested on its own, the way
``_departure`` and ``_live`` are.

Which trip:

* a pinned favourite, when there is one that is not over yet — the
  journey the user said they are taking;
* otherwise the first trip that has not left yet.

What is derived falls into two groups. *Departure facts* come from
the planner and change on every route refresh: times, platform,
cancellation, transfers, crowding, carriages. *Live facts* come from
NS's vehicle feed and the train's own run, and only exist while that
train is somewhere on its run: speed, heading, the station it is at
or heading for, and how far along the traveller's stretch it is.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any

from ._filter import parse_iso
from ._live import position_along

#: A trip still counts as current for this long after it arrives, so
#: an "arrived" event and the last live readings are not cut short.
FOCUS_GRACE = timedelta(minutes=5)

#: Below this speed a train standing at a station counts as stopped.
STANDING_KMH = 5.0

#: A train does not leave this much before its expected departure. A
#: fix that puts it past the traveller's station earlier than that
#: belongs to another ride with the same number, or is stale.
EARLY_TOLERANCE = timedelta(minutes=2)

#: A connection with less than this many minutes left is at risk.
TRANSFER_RISK = 2

FOCUS_FAVOURITE = "favourite"
FOCUS_NEXT = "next"


def _boarded_legs(trip: dict[str, Any]) -> list[dict[str, Any]]:
    """The legs on a train; a walk between stations has no number."""
    return [
        leg
        for leg in trip.get("legs") or []
        if isinstance(leg, dict) and (leg.get("product") or {}).get("number")
    ]


def _when(side: dict[str, Any] | None, *, actual: bool = True) -> datetime | None:
    side = side or {}
    if actual:
        return parse_iso(side.get("actualDateTime")) or parse_iso(side.get("plannedDateTime"))
    return parse_iso(side.get("plannedDateTime"))


def trip_window(trip: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """When a trip leaves its first station and reaches its last."""
    legs = _boarded_legs(trip)
    if not legs:
        return None, None
    return _when(legs[0].get("origin")), _when(legs[-1].get("destination"))


def focus_trip(
    trips: Any, favourites: Any, now: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    """The trip to describe, and why it was chosen.

    A favourite under way beats one still to come, and among either
    the earliest wins. Without a live favourite the first trip that has
    not left yet is the one — a cancelled trip included, because "my
    train is cancelled" is exactly what an automation is for.
    """
    pinned = {str(ctx) for ctx in (favourites or [])}
    usable = [trip for trip in trips or [] if isinstance(trip, dict)]

    best: tuple[tuple[int, float], dict[str, Any]] | None = None
    for trip in usable:
        if not pinned or str(trip.get("ctxRecon") or "") not in pinned:
            continue
        start, end = trip_window(trip)
        if start is None or end is None or end + FOCUS_GRACE < now:
            continue
        under_way = 0 if start <= now else 1
        key = (under_way, start.timestamp())
        if best is None or key < best[0]:
            best = (key, trip)
    if best is not None:
        return best[1], FOCUS_FAVOURITE

    for trip in usable:
        start, _ = trip_window(trip)
        if start is not None and start >= now:
            return trip, FOCUS_NEXT
    return None, None


def trip_identity(trip: dict[str, Any] | None) -> str | None:
    """What makes a trip the same trip on the next refresh.

    ``ctxRecon`` where NS gives one; otherwise the first train's number
    and planned departure, which together pin down one run on one day.
    Events compare old and new state only when this matches, so a
    refresh that moves the focus to the next trip never reads as "the
    platform changed".
    """
    if not trip:
        return None
    ctx = trip.get("ctxRecon")
    if ctx:
        return str(ctx)
    legs = _boarded_legs(trip)
    if not legs:
        return None
    number = (legs[0].get("product") or {}).get("number")
    planned = (legs[0].get("origin") or {}).get("plannedDateTime")
    return f"{number}@{planned}" if number and planned else None


def _minutes(later: datetime | None, earlier: datetime | None) -> int | None:
    if later is None or earlier is None:
        return None
    return int(round((later - earlier).total_seconds() / 60))


def transfers_of(trip: dict[str, Any]) -> list[dict[str, Any]]:
    """Every change of train, with the minutes it leaves.

    The margin is what is left *now*: the expected arrival of one train
    against the expected departure of the next. NS keeps a connection
    in the advice as long as it is possible on paper, so a delay can
    shrink it to nothing without the trip changing — which is exactly
    when someone on the first train wants to know.
    """
    legs = _boarded_legs(trip)
    out: list[dict[str, Any]] = []
    for earlier, later in zip(legs, legs[1:]):
        arrive = (earlier.get("destination") or {})
        leave = (later.get("origin") or {})
        margin = _minutes(_when(leave), _when(arrive))
        planned = _minutes(_when(leave, actual=False), _when(arrive, actual=False))
        out.append({
            "station": arrive.get("name") or leave.get("name"),
            "arrival_platform": arrive.get("actualTrack") or arrive.get("plannedTrack"),
            "departure_platform": leave.get("actualTrack") or leave.get("plannedTrack"),
            "margin": margin,
            "planned_margin": planned,
            "next_train": (
                f"{(later.get('product') or {}).get('shortCategoryName') or ''} "
                f"{(later.get('product') or {}).get('number') or ''}"
            ).strip() or None,
            "at_risk": bool(later.get("cancelled"))
            or (margin is not None and margin < TRANSFER_RISK),
        })
    return out


def is_shorter(composition: dict[str, Any] | None) -> bool | None:
    """Whether the train runs with fewer carriages than planned.

    NS publishes the stock it planned and the stock it is running at
    every stop; fewer carriages, or fewer seats where NS itself flags
    the change as significant, is a shorter train. None without both.
    """
    comp = composition or {}
    actual = comp.get("numberOfParts")
    planned = comp.get("plannedNumberOfParts")
    if not isinstance(actual, int) or not isinstance(planned, int):
        return None
    if actual < planned:
        return True
    seats = comp.get("numberOfSeats")
    planned_seats = comp.get("plannedNumberOfSeats")
    return bool(
        comp.get("significantChange")
        and isinstance(seats, int) and isinstance(planned_seats, int)
        and seats < planned_seats
    )


def departure_facts(
    trip: dict[str, Any] | None, now: datetime, minutes_to_station: int = 0,
) -> dict[str, Any]:
    """Everything the planner says about the focus trip.

    Times are aware datetimes so a timestamp sensor can carry them as
    they are; everything else is a plain value or None. With the time
    it takes to get to the station — on foot, by bike, bus or car — the
    moment to leave is worked out from the expected departure, so a
    delay gives you those minutes back.
    """
    if not trip:
        return {}
    legs = _boarded_legs(trip)
    if not legs:
        return {}
    first, last = legs[0], legs[-1]
    origin = first.get("origin") or {}
    destination = last.get("destination") or {}
    product = first.get("product") or {}

    departure = _when(origin)
    planned_departure = _when(origin, actual=False)
    arrival = _when(destination)
    planned_arrival = _when(destination, actual=False)
    planned_track = origin.get("plannedTrack")
    actual_track = origin.get("actualTrack")
    composition = first.get("composition") or {}

    cancelled = (
        str(trip.get("status") or "").upper() == "CANCELLED"
        or any(bool(leg.get("cancelled")) for leg in legs)
    )
    duration = trip.get("actualDurationInMinutes") or trip.get("plannedDurationInMinutes")
    transfers = trip.get("transfers")
    if not isinstance(transfers, int):
        transfers = max(0, len(legs) - 1)
    code = product.get("shortCategoryName") or product.get("categoryCode") or ""
    until = _minutes(departure, now)
    arrival_planned_track = destination.get("plannedTrack")
    arrival_actual_track = destination.get("actualTrack")
    changes = transfers_of(trip)
    margins = [c["margin"] for c in changes if c["margin"] is not None]
    risky = [c for c in changes if c["at_risk"]]
    to_station = max(0, int(minutes_to_station or 0))
    leave_at = (
        departure - timedelta(minutes=to_station) if (to_station and departure) else None
    )

    return {
        "identity": trip_identity(trip),
        "ctx_recon": trip.get("ctxRecon"),
        "train_number": str(product.get("number")) if product.get("number") else None,
        "train": f"{code} {product.get('number') or ''}".strip() or None,
        "train_type": product.get("displayName") or product.get("longCategoryName") or code or None,
        "operator": product.get("operatorName"),
        "direction": first.get("direction"),
        "origin": origin.get("name"),
        "origin_uic": origin.get("uicCode"),
        "destination": destination.get("name"),
        "destination_uic": destination.get("uicCode"),
        # The traveller's own first and last train: where they board
        # and where they leave the train they are tracked on.
        "leg_origin": origin.get("name"),
        "leg_origin_uic": origin.get("uicCode"),
        "leg_destination": (first.get("destination") or {}).get("name"),
        "leg_destination_uic": (first.get("destination") or {}).get("uicCode"),
        "departure": departure,
        "planned_departure": planned_departure,
        "arrival": arrival,
        "planned_arrival": planned_arrival,
        "departure_delay": max(0, _minutes(departure, planned_departure) or 0),
        "arrival_delay": max(0, _minutes(arrival, planned_arrival) or 0),
        "minutes_to_departure": max(0, until) if until is not None else None,
        "platform": actual_track or planned_track,
        "planned_platform": planned_track,
        "platform_changed": bool(
            actual_track and planned_track and str(actual_track) != str(planned_track)
        ),
        "cancelled": cancelled,
        "travel_time": int(duration) if isinstance(duration, (int, float)) else None,
        "transfers": transfers,
        "crowd": str(first.get("crowdForecast") or "").lower() or None,
        "carriages": composition.get("numberOfParts"),
        "planned_carriages": composition.get("plannedNumberOfParts"),
        "seats": composition.get("numberOfSeats"),
        "rolling_stock": composition.get("trainType"),
        "shorter_train": is_shorter(composition) if composition else None,
        "arrival_platform": arrival_actual_track or arrival_planned_track,
        "planned_arrival_platform": arrival_planned_track,
        "arrival_platform_changed": bool(
            arrival_actual_track and arrival_planned_track
            and str(arrival_actual_track) != str(arrival_planned_track)
        ),
        "transfer_list": changes,
        "transfer_margin": min(margins) if margins else None,
        "transfer_at_risk": bool(risky) if changes else False,
        "transfer_station": (risky[0] if risky else (changes[0] if changes else {})).get("station"),
        "leave_at": leave_at,
        "time_to_leave": bool(
            leave_at is not None and departure is not None and not cancelled
            and leave_at <= now < departure
        ),
    }


def following_trip(
    trips: Any, focus: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """The trip after the focus: what to take if you miss yours.

    The first trip that leaves after the focus trip does, skipping a
    cancelled one, because a cancelled train is no fallback.
    """
    start = (focus or {}).get("departure")
    if not isinstance(start, datetime):
        return None
    best: tuple[datetime, dict[str, Any]] | None = None
    for trip in trips or []:
        if not isinstance(trip, dict) or trip_identity(trip) == focus.get("identity"):  # type: ignore[union-attr]
            continue
        if str(trip.get("status") or "").upper() == "CANCELLED":
            continue
        leaves, _ = trip_window(trip)
        if leaves is None or leaves <= start:
            continue
        if best is None or leaves < best[0]:
            best = (leaves, trip)
    return best[1] if best else None


def last_trip(trips: Any, day_ends: datetime) -> dict[str, Any] | None:
    """The last trip that leaves before the service day ends.

    NS's day runs past midnight, so the caller passes the moment it
    rolls over (four in the morning); a cancelled trip does not count
    as the last one, because nobody can take it.
    """
    best: tuple[datetime, dict[str, Any]] | None = None
    for trip in trips or []:
        if not isinstance(trip, dict):
            continue
        if str(trip.get("status") or "").upper() == "CANCELLED":
            continue
        leaves, _ = trip_window(trip)
        if leaves is None or leaves >= day_ends:
            continue
        if best is None or leaves > best[0]:
            best = (leaves, trip)
    return best[1] if best else None


def summary(trip: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """The few facts a "train after" or "last train" sensor carries."""
    facts = departure_facts(trip, now)
    if not facts:
        return {}
    return {
        key: facts.get(key)
        for key in ("departure", "planned_departure", "arrival", "train",
                    "train_number", "platform", "departure_delay", "transfers",
                    "travel_time", "cancelled")
    }


def _distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lng1, lat2, lng2 = map(radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * asin(min(1.0, sqrt(h)))


def _find(stops: list[dict[str, Any]], uic: Any, name: Any, after: int = 0) -> int | None:
    """Index of a station on the run, by UIC code first, then by name."""
    code = str(uic or "").strip()
    label = str(name or "").strip().casefold()
    for index in range(after, len(stops)):
        stop = stops[index]
        if code and str(stop.get("uicCode") or "") == code:
            return index
    for index in range(after, len(stops)):
        if label and str(stops[index].get("name") or "").strip().casefold() == label:
            return index
    return None


def _along(stops: list[dict[str, Any]], start: float, end: float) -> float:
    """Kilometres along the run between two fractional indexes."""
    if end <= start:
        return 0.0
    total = 0.0
    index = int(start)
    while index < len(stops) - 1 and index < end:
        seg = _distance_km(stops[index], stops[index + 1])
        lo = max(start, float(index))
        hi = min(end, float(index + 1))
        if hi > lo:
            total += seg * (hi - lo)
        index += 1
    return total


def live_facts(
    stops: list[dict[str, Any]],
    position: dict[str, Any] | None,
    facts: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Where the focus train is, put in the traveller's terms.

    ``stops`` is the train's whole run, ``position`` its latest fix, and
    ``facts`` the departure facts, which say where the traveller gets on
    and off. Returns only what can be stated: no fix, no live facts —
    and no facts from a fix that cannot be this ride, one that puts the
    train past the traveller's station well before it is due to leave.
    """
    if not position or len(stops) < 2:
        return {}
    index = position_along(stops, position.get("lat"), position.get("lng"))
    if index is None:
        return {}

    speed = position.get("speed")
    speed_kmh = round(float(speed), 1) if isinstance(speed, (int, float)) else None
    heading = position.get("heading")

    current: str | None = None
    if abs(index - round(index)) < 1e-9:
        stop = stops[int(round(index))]
        if stop.get("status") != "PASSING":
            current = stop.get("name")
    standing = speed_kmh is None or speed_kmh < STANDING_KMH
    at_station = bool(current) and standing

    next_station: str | None = None
    for later in range(int(index) + 1, len(stops)):
        stop = stops[later]
        if stop.get("status") == "PASSING" or stop.get("cancelled"):
            continue
        next_station = stop.get("name")
        break

    board = _find(stops, facts.get("leg_origin_uic"), facts.get("leg_origin"))
    alight = _find(
        stops, facts.get("leg_destination_uic"), facts.get("leg_destination"),
        after=board or 0,
    )
    departure = facts.get("departure")
    if (
        now is not None and board is not None and isinstance(departure, datetime)
        and index > board + 0.02 and now < departure - EARLY_TOLERANCE
    ):
        return {}
    progress: float | None = None
    remaining: float | None = None
    if board is not None and alight is not None and alight > board:
        share = (index - board) / (alight - board)
        progress = round(max(0.0, min(1.0, share)) * 100.0, 1)
        remaining = round(_along(stops, max(index, float(board)), float(alight)), 1)

    return {
        "position_index": index,
        "latitude": position.get("lat"),
        "longitude": position.get("lng"),
        "speed": speed_kmh,
        "heading": round(float(heading)) if isinstance(heading, (int, float)) else None,
        "current_station": current,
        "at_station": at_station,
        "moving": speed_kmh is not None and speed_kmh >= STANDING_KMH,
        "next_station": next_station,
        "progress": progress,
        "remaining_km": remaining,
        "boarding_index": board,
        "alighting_index": alight,
        "source": position.get("source"),
    }


def journey_events(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
    previous_live: dict[str, Any] | None,
    current_live: dict[str, Any] | None,
    fired: set[str],
    now: datetime,
) -> list[tuple[str, dict[str, Any]]]:
    """What happened to the focus trip since the last look.

    Old and new are only compared when they describe the same trip, so
    the focus moving on to the next train is never mistaken for a
    change. ``departed`` and ``arrived`` fire once per trip — the
    ``fired`` set remembers — from the train's position where there is
    one, and from the clock where there is not.
    """
    if not current or not current.get("identity"):
        return []
    identity = str(current["identity"])
    out: list[tuple[str, dict[str, Any]]] = []
    same = bool(previous) and previous.get("identity") == identity  # type: ignore[union-attr]

    def base() -> dict[str, Any]:
        return {
            "train": current.get("train"),
            "train_number": current.get("train_number"),
            "origin": current.get("origin"),
            "destination": current.get("destination"),
            "departure": current["departure"].isoformat() if current.get("departure") else None,
        }

    if same and previous is not None:
        old_track = previous.get("platform")
        new_track = current.get("platform")
        if old_track and new_track and str(old_track) != str(new_track):
            out.append(("platform_changed", {
                **base(), "platform": new_track, "previous_platform": old_track,
            }))
        old_delay = previous.get("departure_delay") or 0
        new_delay = current.get("departure_delay") or 0
        if new_delay != old_delay:
            out.append(("delay_changed", {
                **base(), "delay": new_delay, "previous_delay": old_delay,
            }))
        if current.get("cancelled") and not previous.get("cancelled"):
            out.append(("cancelled", base()))

    def once(kind: str) -> bool:
        key = f"{identity}|{kind}"
        if key in fired:
            return False
        fired.add(key)
        return True

    live = current_live or {}
    board = live.get("boarding_index")
    alight = live.get("alighting_index")
    index = live.get("position_index")
    departed = arrived = False
    if isinstance(index, (int, float)) and board is not None:
        departed = index > board + 0.02
    elif current.get("departure") is not None:
        departed = now >= current["departure"]
    if isinstance(index, (int, float)) and alight is not None:
        arrived = index >= alight and bool(live.get("at_station") or index > alight)
    elif current.get("arrival") is not None:
        arrived = now >= current["arrival"]

    if departed and not current.get("cancelled") and once("departed"):
        out.append(("departed", base()))
    if arrived and not current.get("cancelled") and once("arrived"):
        out.append(("arrived", {**base(), "arrival": (
            current["arrival"].isoformat() if current.get("arrival") else None
        )}))
    return out


def disruption_events(
    previous_ids: set[str] | None,
    items: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """Disruptions that started or ended on a route since last time.

    ``previous_ids`` is None on the very first look, which fires
    nothing: a disruption that was already there when Home Assistant
    started is not news.
    """
    if previous_ids is None:
        return []
    current = {str(item.get("id")): item for item in items if item.get("id")}
    out: list[tuple[str, dict[str, Any]]] = []
    for disruption_id, item in current.items():
        if disruption_id not in previous_ids:
            out.append(("disruption_started", {
                "id": disruption_id,
                # Not "type": that key names the event itself.
                "disruption_type": item.get("type"),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "extra_travel_time": item.get("extra_travel_time"),
            }))
    for disruption_id in sorted(previous_ids - set(current)):
        out.append(("disruption_ended", {"id": disruption_id}))
    return out
