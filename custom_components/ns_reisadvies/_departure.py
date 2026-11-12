"""Pure helpers behind the per-route delay and next-train sensors (v2.20.0).

Both sensors read the route's coordinator data: the trip list after the
train-type and time-window filters. Kept free of Home Assistant imports
so the logic is unit-tested on its own, like ``_filter.py``.

Every NS field read here is one the integration or its card already
relies on: ``origin.plannedDateTime`` / ``actualDateTime``,
``origin.plannedTrack`` / ``actualTrack``, ``product.categoryCode`` /
``shortCategoryName`` / ``number`` and ``trip.status == "CANCELLED"``.
"""
from __future__ import annotations

from typing import Any

from ._filter import leg_category_codes
from .coordinator import parse_iso

STATUS_ON_TIME = "on_time"
STATUS_DELAYED = "delayed"
STATUS_CANCELLED = "cancelled"

# The words the one-line summary needs. The sensor state is plain text,
# so it cannot go through HA's entity translations; the two languages
# the integration ships are covered here, English for everything else.
_WORDS = {
    "nl": {"track": "spoor", "cancelled": "vervalt"},
    "en": {"track": "platform", "cancelled": "cancelled"},
}


def _first_boarded_leg(trip: dict[str, Any]) -> dict[str, Any] | None:
    """The first leg with a train product; walking legs have none."""
    for leg in trip.get("legs") or []:
        if isinstance(leg, dict) and leg_category_codes(leg):
            return leg
    return None


def next_departure(trips: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Describe the departure of the first trip, or None without one.

    Keys: ``delay`` (whole minutes, never negative), ``train``
    (``"IC 3222"``), ``planned`` / ``expected`` (``"HH:MM"``), ``track``,
    ``track_changed``, ``status`` (``on_time`` / ``delayed`` /
    ``cancelled``).
    """
    for trip in trips or []:
        if not isinstance(trip, dict):
            continue
        leg = _first_boarded_leg(trip)
        if leg is None:
            continue
        origin = leg.get("origin") or {}
        product = leg.get("product") or {}
        planned = parse_iso(origin.get("plannedDateTime"))
        expected = parse_iso(origin.get("actualDateTime")) or planned
        delay = 0
        if planned and expected:
            delay = max(0, round((expected - planned).total_seconds() / 60))
        cancelled = str(trip.get("status") or "").upper() == "CANCELLED"
        planned_track = origin.get("plannedTrack")
        actual_track = origin.get("actualTrack")
        code = product.get("shortCategoryName") or product.get("categoryCode") or ""
        train = f"{code} {product.get('number') or ''}".strip()
        if cancelled:
            status = STATUS_CANCELLED
        elif delay > 0:
            status = STATUS_DELAYED
        else:
            status = STATUS_ON_TIME
        return {
            "delay": delay,
            "train": train or None,
            "planned": planned.strftime("%H:%M") if planned else None,
            "expected": expected.strftime("%H:%M") if expected else None,
            "track": actual_track or planned_track,
            "track_changed": bool(
                actual_track and planned_track and actual_track != planned_track
            ),
            "status": status,
        }
    return None


def summary_line(info: dict[str, Any] | None, language: str | None) -> str | None:
    """One line for a small screen: ``IC 08:09 +4, spoor 3``.

    Only plain ASCII punctuation, so it renders on displays with a
    limited font. A changed track ends in ``!``; a cancelled trip reads
    ``IC 08:09 vervalt``. ``language`` is HA's configured language.
    """
    if not info:
        return None
    lang = (language or "en").split("-")[0].lower()
    words = _WORDS.get(lang, _WORDS["en"])
    code = (info.get("train") or "").split(" ")[0]
    line = " ".join(p for p in (code, info.get("planned")) if p)
    if info["status"] == STATUS_CANCELLED:
        return f"{line} {words['cancelled']}".strip()
    if info.get("delay"):
        line += f" +{info['delay']}"
    if info.get("track"):
        line += f", {words['track']} {info['track']}"
        if info.get("track_changed"):
            line += "!"
    return line.strip() or None
