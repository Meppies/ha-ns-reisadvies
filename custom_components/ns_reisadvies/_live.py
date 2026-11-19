"""Pure parsing for the two live sources behind the train map.

Kept free of Home Assistant and aiohttp imports so the shapes NS
returns can be tested on their own, the way ``_filter`` and
``_departure`` are.

Two feeds live here:

* ``/virtual-train-api/vehicle`` — every train NS currently has a GPS
  fix for. ``vehicle_index`` turns the payload into a lookup by ride
  number.
* ``/reisinformatie-api/api/v2/journey`` — the complete run of one
  train, from where it started to where it ends, including the stops
  before the traveller boards and after they get out.
  ``parse_journey`` flattens it into the stop list the card draws, and
  ``run_window`` says when that run starts and finishes.

The journey payload only carries times for stops where the train
actually stops; a station it races through has ``status: PASSING`` and
empty ``arrivals``/``departures``. Those gaps are filled in here by
spreading the time between the surrounding timed stops over the
distance travelled, and the stops that get such a time are flagged
``estimated`` so nothing downstream presents a guess as NS's own
schedule.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

from ._filter import parse_iso

# A stop that NS gives no time for is placed between its neighbours by
# distance. Below this the gap is treated as zero-length and the time is
# split evenly, which avoids a division by zero for two stops that
# resolve to the same coordinates.
_MIN_GAP_KM = 0.01


def _first(entries: Any) -> dict[str, Any]:
    """The first arrival/departure entry, or an empty mapping."""
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                return entry
    return {}


def vehicle_index(payload: Any) -> dict[str, dict[str, Any]]:
    """Index NS's live vehicle feed by ride number.

    The feed is national: one request covers every train that is
    reporting, so a single fetch serves every pinned favourite and every
    open map at once. Each entry is normalised to the same shape the
    ArcGIS fallback returns, so callers do not care which source a fix
    came from beyond the ``source`` field.

    Both ``treinNummer`` and ``ritId`` are indexed because NS is not
    consistent about which one a planning refers to.
    """
    if isinstance(payload, dict):
        inner = payload.get("payload")
        if isinstance(inner, dict):
            trains = inner.get("treinen")
        elif isinstance(inner, list):
            trains = inner
        else:
            trains = payload.get("treinen")
    elif isinstance(payload, list):
        trains = payload
    else:
        trains = None
    if not isinstance(trains, list):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for train in trains:
        if not isinstance(train, dict):
            continue
        lat = train.get("lat")
        lng = train.get("lng")
        if lat is None or lng is None:
            continue
        fix: dict[str, Any]
        try:
            fix = {"lat": float(lat), "lng": float(lng)}
        except (TypeError, ValueError):
            continue
        number = str(train.get("treinNummer") or "").strip()
        ride = str(train.get("ritId") or "").strip()
        source = str(train.get("bron") or "").strip().lower()
        fix.update({
            "speed": train.get("snelheid"),
            "heading": train.get("richting"),
            "accuracy": train.get("horizontaleNauwkeurigheid"),
            "train_type": train.get("type"),
            "train_number": number or ride,
            "source": f"ns-{source}" if source else "ns-vehicle",
        })
        for key in (number, ride):
            if key:
                out[key] = fix
    return out


def _distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Great-circle distance between two stops, in kilometres.

    Both stops come out of ``parse_journey``, which has already thrown
    away anything without usable coordinates.
    """
    lat1, lng1 = radians(float(a["lat"])), radians(float(a["lng"]))
    lat2, lng2 = radians(float(b["lat"])), radians(float(b["lng"]))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * 6371.0 * asin(min(1.0, sqrt(h)))


def _stop_times(stop: dict[str, Any]) -> tuple[
    datetime | None, datetime | None, datetime | None, datetime | None, bool
]:
    """Planned and actual arrival/departure of one journey stop."""
    arrival = _first(stop.get("arrivals"))
    departure = _first(stop.get("departures"))
    cancelled = bool(arrival.get("cancelled")) or bool(departure.get("cancelled"))
    return (
        parse_iso(arrival.get("plannedTime")),
        parse_iso(arrival.get("actualTime")),
        parse_iso(departure.get("plannedTime")),
        parse_iso(departure.get("actualTime")),
        cancelled,
    )


def _fill_gaps(stops: list[dict[str, Any]]) -> None:
    """Give the untimed stops a time, spread out by distance.

    A train that passes a station without stopping gets no time from NS,
    which would leave a hole in the middle of the run. Rather than
    skipping those stops — the map would then jump from one stopping
    station to the next — the time between the two surrounding timed
    stops is divided over the distance between them.
    """
    timed = [i for i, s in enumerate(stops) if s["_dep"] is not None]
    for left, right in zip(timed, timed[1:]):
        if right - left < 2:
            continue
        start: datetime = stops[left]["_dep"]
        end: datetime = stops[right]["_arr"]
        span = (end - start).total_seconds()
        if span <= 0:
            continue
        legs = [
            _distance_km(stops[i], stops[i + 1]) for i in range(left, right)
        ]
        total = sum(legs) or 0.0
        walked = 0.0
        for offset, i in enumerate(range(left + 1, right)):
            walked += legs[offset]
            share = (walked / total) if total > _MIN_GAP_KM else (
                (offset + 1) / (right - left)
            )
            moment = start + timedelta(seconds=span * share)
            stops[i]["_arr"] = moment
            stops[i]["_dep"] = moment
            stops[i]["estimated"] = True


def parse_journey(
    payload: Any, now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Flatten ``/v2/journey`` into the stop list the live map draws.

    Coordinates come straight from the payload, so this needs no station
    cache. Every stop carries the planned and actual times NS reported
    plus a ``passed`` flag, which is what splits the drawn line into the
    part already travelled and the part still to come.
    """
    if isinstance(payload, dict):
        inner = payload.get("payload")
        raw = (inner or {}).get("stops") if isinstance(inner, dict) else None
        if raw is None:
            raw = payload.get("stops")
    else:
        raw = None
    if not isinstance(raw, list):
        return []

    moment = now or datetime.now(timezone.utc)
    stops: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        where = entry.get("stop")
        if not isinstance(where, dict):
            continue
        try:
            lat = float(where["lat"])
            lng = float(where["lng"])
        except (KeyError, TypeError, ValueError):
            # A stop with no usable coordinates cannot be drawn and
            # cannot carry the estimate; the run simply skips it.
            continue
        plan_arr, act_arr, plan_dep, act_dep, cancelled = _stop_times(entry)
        stops.append({
            "name": (where.get("name") or "").strip(),
            "lat": lat,
            "lng": lng,
            "uicCode": str(where.get("uicCode") or ""),
            "status": str(entry.get("status") or "").upper(),
            "cancelled": cancelled,
            "estimated": False,
            "plannedArrivalDateTime": plan_arr.isoformat() if plan_arr else None,
            "actualArrivalDateTime": act_arr.isoformat() if act_arr else None,
            "plannedDepartureDateTime": plan_dep.isoformat() if plan_dep else None,
            "actualDepartureDateTime": act_dep.isoformat() if act_dep else None,
            # Working fields: when the train reaches this stop and when
            # it leaves again. A gap in the middle of the run is spread
            # between the departure on its left and the arrival on its
            # right, so both are kept separately.
            "_arr": plan_arr or plan_dep,
            "_dep": plan_dep or plan_arr,
        })

    if not stops:
        return []
    _fill_gaps(stops)

    for stop in stops:
        if stop["estimated"]:
            arrived_iso = stop["_arr"].isoformat() if stop["_arr"] else None
            left_iso = stop["_dep"].isoformat() if stop["_dep"] else None
            stop["plannedArrivalDateTime"] = arrived_iso
            stop["plannedDepartureDateTime"] = left_iso
        reached = (
            parse_iso(stop["actualDepartureDateTime"])
            or parse_iso(stop["actualArrivalDateTime"])
            or stop["_dep"]
        )
        stop["passed"] = bool(reached and reached <= moment)
        del stop["_arr"]
        del stop["_dep"]
    return stops


def position_along(
    stops: list[dict[str, Any]],
    lat: Any,
    lng: Any,
    max_km: float = 25.0,
    snap_km: float = 0.5,
) -> float | None:
    """Where a GPS fix sits along the run, as an index with a fraction.

    ``6.4`` means four tenths of the way from the seventh stop to the
    eighth. That single number is all the card needs: every station
    before it has been passed, every one after it has not, and the
    stretch of line in between is divided at the fraction.

    This is what a timetable cannot tell you. NS reports a time for
    every stop whether or not the train has been there yet — a stop
    still to come carries the time it is expected to be reached — so a
    train running behind its own expectation looks, to the clock, as
    though it has already passed the next station.

    A train within ``snap_km`` of a station counts as being at it, and
    the answer is that station's index exactly. Standing at a platform
    the fix is tens or hundreds of metres from the station's own
    coordinates, which would otherwise read as "not there yet" and
    leave the station uncoloured while the train sits in it.

    Returns None when there is no fix, when the run is too short to
    place one on, or when the fix is further than ``max_km`` from the
    line, which means it belongs to another train than the one drawn.
    """
    if len(stops) < 2:
        return None
    try:
        point = (float(lat), float(lng))
    except (TypeError, ValueError):
        return None

    # Degrees are not metres: a degree of longitude is shorter the
    # further north you are, so scale it before measuring.
    scale = cos(radians(point[0])) or 1.0
    best: tuple[float, float] | None = None
    for index in range(len(stops) - 1):
        try:
            ax, ay = float(stops[index]["lat"]), float(stops[index]["lng"]) * scale
            bx, by = float(stops[index + 1]["lat"]), float(stops[index + 1]["lng"]) * scale
        except (KeyError, TypeError, ValueError):
            continue
        px, py = point[0], point[1] * scale
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        if span <= 0:
            share = 0.0
        else:
            share = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / span))
        nx, ny = ax + dx * share, ay + dy * share
        gap = sqrt((px - nx) ** 2 + (py - ny) ** 2) * 111.0
        if best is None or gap < best[1]:
            best = (index + share, gap)
    if best is None or best[1] > max_km:
        return None

    here = {"lat": point[0], "lng": point[1]}
    nearest: tuple[int, float] | None = None
    for index, stop in enumerate(stops):
        try:
            gap = _distance_km(stop, here)
        except (KeyError, TypeError, ValueError):
            continue
        if nearest is None or gap < nearest[1]:
            nearest = (index, gap)
    if nearest is not None and nearest[1] <= snap_km:
        return float(nearest[0])
    return best[0]


def run_window(
    stops: list[dict[str, Any]],
) -> tuple[datetime | None, datetime | None]:
    """When the train leaves its first stop and reaches its last.

    Used to decide whether a train is running at all: the position of a
    favourite is worth fetching for exactly as long as this window is
    open, whether or not the traveller is on board yet.
    """
    if not stops:
        return None, None
    first = stops[0]
    last = stops[-1]
    start = (
        parse_iso(first.get("actualDepartureDateTime"))
        or parse_iso(first.get("plannedDepartureDateTime"))
        or parse_iso(first.get("actualArrivalDateTime"))
        or parse_iso(first.get("plannedArrivalDateTime"))
    )
    end = (
        parse_iso(last.get("actualArrivalDateTime"))
        or parse_iso(last.get("plannedArrivalDateTime"))
        or parse_iso(last.get("actualDepartureDateTime"))
        or parse_iso(last.get("plannedDepartureDateTime"))
    )
    return start, end
