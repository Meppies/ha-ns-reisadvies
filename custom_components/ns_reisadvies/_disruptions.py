"""Pure parsing for NS's disruptions feed.

Kept free of Home Assistant imports, like ``_filter``, ``_departure``
and ``_live``, so the shapes NS returns can be tested on their own.

``/v3/disruptions`` answers with two different kinds of thing under
one roof:

* **DISRUPTION** and **MAINTENANCE** — a stretch of railway with a
  problem. These carry ``timespans`` (what is wrong, why, what to do
  instead) and ``publicationSections`` listing every station on the
  affected stretch, each with its coordinates. That is what lets the
  card draw where the trouble is.
* **CALAMITY** — an announcement rather than a stretch: a title, a
  description, a link, and no stations at all.

``parse_disruptions`` flattens both into one shape so nothing
downstream has to know which it is holding.
"""
from __future__ import annotations

import re
from typing import Any

#: The three kinds NS publishes.
DISRUPTION_TYPES = ("DISRUPTION", "MAINTENANCE", "CALAMITY")

_TAGS = re.compile(r"<[^>]+>")


def _text(value: Any) -> str:
    """Strip the bit of HTML NS puts in calamity bodies."""
    if not isinstance(value, str):
        return ""
    return " ".join(_TAGS.sub(" ", value).split())


def _first(entries: Any) -> dict[str, Any]:
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                return entry
    return {}


def _label(entry: Any, key: str = "label") -> str | None:
    if isinstance(entry, dict):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _stations(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Every station on the affected stretch, with its coordinates."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section in entry.get("publicationSections") or []:
        if not isinstance(section, dict):
            continue
        inner = section.get("section")
        if not isinstance(inner, dict):
            continue
        for station in inner.get("stations") or []:
            if not isinstance(station, dict):
                continue
            uic = str(station.get("uicCode") or "")
            code = str(station.get("stationCode") or "").upper()
            key = uic or code or str(station.get("name") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            where = station.get("coordinate") or {}
            try:
                lat = float(where["lat"])
                lng = float(where["lng"])
            except (KeyError, TypeError, ValueError):
                lat = lng = None  # type: ignore[assignment]
            out.append({
                "name": str(station.get("name") or "").strip(),
                "uicCode": uic,
                "stationCode": code,
                "lat": lat,
                "lng": lng,
            })
    return out


def parse_disruptions(payload: Any) -> list[dict[str, Any]]:
    """Flatten NS's answer into one shape per disruption."""
    if not isinstance(payload, list):
        return []

    out: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("type") or "").upper()
        if kind not in DISRUPTION_TYPES:
            continue
        span = _first(entry.get("timespans"))
        stations = _stations(entry)
        advices = [
            " ".join(str(line).split())
            for line in (span.get("advices") or [])
            if isinstance(line, str) and line.strip()
        ]
        body = " ".join(
            _text((item.get("content") or {}).get("text"))
            for item in entry.get("bodyItems") or []
            if isinstance(item, dict)
        ).strip()
        summary = (
            _label(span.get("situation"))
            or _text(entry.get("description"))
            or body
            or str(entry.get("title") or "").strip()
        )
        out.append({
            "id": str(entry.get("id") or ""),
            "type": kind,
            "title": str(entry.get("title") or "").strip(),
            "summary": summary,
            "cause": _label(span.get("cause")),
            "period": _label(span, "period"),
            "start": entry.get("start") or span.get("start"),
            "end": entry.get("end") or span.get("end"),
            "expected_until": _label(entry.get("expectedDuration"), "description"),
            "extra_travel_time": (
                _label(span.get("additionalTravelTime"), "shortLabel")
                or _label(span.get("additionalTravelTime"))
            ),
            "alternative_transport": (
                _label(span.get("alternativeTransport"), "shortLabel")
                or _label(span.get("alternativeTransport"))
            ),
            "impact": (entry.get("impact") or {}).get("value"),
            "phase": _label(entry.get("phase")),
            "advices": advices,
            "url": entry.get("url") or None,
            "stations": stations,
            # Both spellings, because a route is matched on whichever
            # the planner happens to carry.
            "station_keys": sorted(
                {s["uicCode"] for s in stations if s["uicCode"]}
                | {s["stationCode"] for s in stations if s["stationCode"]}
            ),
        })
    return out


def station_keys_of(trips: Any) -> set[str]:
    """Every station a route's planned journeys touch.

    Not just the two ends: a disruption between two stations halfway
    along the journey is exactly the one worth being told about.
    """
    keys: set[str] = set()
    for trip in trips or []:
        if not isinstance(trip, dict):
            continue
        for leg in trip.get("legs") or []:
            if not isinstance(leg, dict):
                continue
            places: list[Any] = [leg.get("origin"), leg.get("destination")]
            places.extend(leg.get("stops") or [])
            for place in places:
                if not isinstance(place, dict):
                    continue
                for field in ("uicCode", "stationCode", "code"):
                    value = place.get(field)
                    if value:
                        keys.add(str(value).upper())
    return keys


def affecting(
    disruptions: list[dict[str, Any]], keys: set[str],
) -> list[dict[str, Any]]:
    """The disruptions that touch any of these stations.

    A calamity has no stations of its own, so it is national news and
    never filtered out: NS publishes those exactly when everyone needs
    to know.
    """
    if not keys:
        return [d for d in disruptions if d.get("type") == "CALAMITY"]
    out: list[dict[str, Any]] = []
    for disruption in disruptions:
        if disruption.get("type") == "CALAMITY":
            out.append(disruption)
            continue
        if keys & {str(key).upper() for key in disruption.get("station_keys") or []}:
            out.append(disruption)
    return out


def of_types(
    disruptions: list[dict[str, Any]], types: list[str] | None,
) -> list[dict[str, Any]]:
    """Narrow to the kinds the card asked for."""
    if not types:
        return list(disruptions)
    wanted = {str(kind).upper() for kind in types}
    return [d for d in disruptions if d.get("type") in wanted]
