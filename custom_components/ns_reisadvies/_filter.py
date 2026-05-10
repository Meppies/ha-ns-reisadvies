"""Per-route filter helpers for the NS Reisadvies integration.

A route can declare an optional filter that says "I only travel
Mon/Wed/Fri at around 08:00 ±60 minutes" or "show me only the trips
of 24 December 2026". The coordinator passes the resulting target
datetime to NS as the trip-search anchor and post-filters the
returned trips by the configured window.

This module is intentionally pure: it has no Home Assistant or
aiohttp imports, so it can be tested in isolation without bringing
up a hass fixture.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any


def compute_target_datetime(
    now: datetime,
    *,
    days: list[int] | None = None,
    target_time: time | None = None,
    window_minutes: int = 0,
    specific_date: date | None = None,
) -> datetime | None:
    """Return the moment NS should base the trip search on.

    * ``specific_date`` set: use that exact date plus ``target_time``
      (or 00:00 if not supplied). No rollover, no day-of-week filter.
      Returns ``None`` if the date is so far in the past that even the
      window has elapsed — caller may then drop the filter or show no
      trips.
    * Otherwise: pick today's ``target_time`` (default = now-time);
      if that moment plus the window has already passed, advance one
      day at a time. If ``days`` is non-empty, keep advancing until
      the candidate weekday is in the allowed set.
    """
    valid_days: set[int] = set(days) if days else {0, 1, 2, 3, 4, 5, 6}
    eff_time: time = (
        target_time
        if target_time is not None
        else now.time().replace(second=0, microsecond=0)
    )

    if specific_date is not None:
        candidate = datetime.combine(specific_date, eff_time, tzinfo=now.tzinfo)
        # If the date + window is fully in the past, return None: the
        # caller decides whether to fall back to "no filter" or
        # surface an empty list.
        if now > candidate + timedelta(minutes=window_minutes):
            return None
        return candidate

    # No filter at all (no time, no days) → just hand back ``now`` so
    # the coordinator searches around the current moment. Without this
    # short-circuit the rollover comparison below would fire whenever
    # ``now`` has sub-minute precision: ``eff_time`` is floored to the
    # minute, making ``candidate`` microscopically older than ``now``,
    # so the function would advance to tomorrow at the same minute.
    if target_time is None and not days:
        return now

    candidate_date = now.date()
    candidate = datetime.combine(candidate_date, eff_time, tzinfo=now.tzinfo)
    if now > candidate + timedelta(minutes=window_minutes):
        candidate_date += timedelta(days=1)
        candidate = datetime.combine(candidate_date, eff_time, tzinfo=now.tzinfo)

    # Walk forward at most a week to find a matching weekday.
    for _ in range(8):
        if candidate.weekday() in valid_days:
            return candidate
        candidate_date += timedelta(days=1)
        candidate = datetime.combine(candidate_date, eff_time, tzinfo=now.tzinfo)
    # Defensive: with valid_days never empty this loop always returns
    # within seven iterations. Keep a safe fallback for the type checker.
    return candidate  # pragma: no cover


def apply_window_filter(
    trips: list[dict[str, Any]],
    target: datetime,
    window_minutes: int,
    *,
    pick_single: bool = False,
) -> list[dict[str, Any]]:
    """Return only the trips whose planned departure matches the window.

    * ``pick_single=True`` AND ``window_minutes == 0``: return **exactly
      one** trip — the one whose planned departure sits closest to
      ``target``. Tie-breaks, in order:

      1. Prefer the trip that departs **at or before** the anchor over
         a trip the same number of minutes after it (e.g. anchor 09:00:
         a 08:50 train wins over a 09:10 train).
      2. Prefer the shorter total travel time.

      An empty list is returned when no trip has a valid planned time.
      This mode is used when the user explicitly set the *Time of day*
      filter — they're asking "give me the train at this time".
    * ``pick_single=False`` AND ``window_minutes == 0``: keep every
      trip whose planned departure is at or after ``target`` — the
      historic behaviour for routes without a time filter (only days
      or specific date set), where we just want to hide trips before
      the anchor.
    * ``window_minutes > 0``: keep trips whose planned departure falls
      in the closed interval ``[target - window, target + window]``.
    """
    def _planned_dt(trip: dict[str, Any]) -> datetime | None:
        dep_iso = (
            (trip.get("legs") or [{}])[0]
            .get("origin", {})
            .get("plannedDateTime", "")
        )
        if not dep_iso:
            return None
        try:
            dep = datetime.fromisoformat(str(dep_iso).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if dep.tzinfo is not None and target.tzinfo is None:
            dep = dep.replace(tzinfo=None)
        return dep

    def _duration(trip: dict[str, Any]) -> int:
        for key in ("actualDurationInMinutes", "plannedDurationInMinutes"):
            v = trip.get(key)
            if isinstance(v, (int, float)):
                return int(v)
        return 99999

    if window_minutes == 0 and pick_single:
        # Exact-one selection: rank by (|offset|, after_anchor?, duration).
        scored: list[tuple[float, int, int, dict[str, Any]]] = []
        for trip in trips:
            dep = _planned_dt(trip)
            if dep is None:
                continue
            offset = abs((dep - target).total_seconds())
            after = 1 if dep > target else 0  # prefer ≤ anchor → 0 wins
            scored.append((offset, after, _duration(trip), trip))
        if not scored:
            return []
        scored.sort(key=lambda row: (row[0], row[1], row[2]))
        return [scored[0][3]]

    if window_minutes == 0:
        # Historic behaviour for routes without a time filter: just hide
        # trips that already departed.
        out: list[dict[str, Any]] = []
        for trip in trips:
            dep = _planned_dt(trip)
            if dep is None:
                continue
            if dep >= target:
                out.append(trip)
        return out

    earliest = target - timedelta(minutes=window_minutes)
    latest = target + timedelta(minutes=window_minutes)
    out = []
    for trip in trips:
        dep = _planned_dt(trip)
        if dep is None:
            continue
        if earliest <= dep <= latest:
            out.append(trip)
    return out
