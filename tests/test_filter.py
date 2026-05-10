"""Unit tests for the pure filter helpers (v2.14.0)."""
from __future__ import annotations

from datetime import date, datetime, time

from custom_components.ns_reisadvies._filter import (
    apply_window_filter,
    compute_target_datetime,
)


# ---- compute_target_datetime ------------------------------------------------


def test_target_no_filter_returns_now_today():
    """No filter at all → candidate is today at now-time."""
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(now)
    assert out == datetime(2026, 5, 9, 14, 30)


def test_target_specific_date_future_uses_that_date():
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(
        now, specific_date=date(2026, 12, 24), target_time=time(8, 0),
    )
    assert out == datetime(2026, 12, 24, 8, 0)


def test_target_specific_date_in_past_returns_none():
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(
        now, specific_date=date(2020, 1, 1), target_time=time(8, 0),
    )
    assert out is None


def test_target_specific_date_in_past_but_within_window_returns_date():
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(
        now,
        specific_date=date(2026, 5, 9),
        target_time=time(13, 0),  # 1.5 h ago
        window_minutes=120,  # 2 h window → still in range
    )
    assert out == datetime(2026, 5, 9, 13, 0)


def test_target_specific_date_no_time_uses_midnight():
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(now, specific_date=date(2026, 12, 24))
    # eff_time defaults to now.time() (14:30) since no target_time given.
    assert out == datetime(2026, 12, 24, 14, 30)


def test_target_time_today_in_future():
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(now, target_time=time(18, 0))
    assert out == datetime(2026, 5, 9, 18, 0)


def test_target_time_today_passed_rolls_to_tomorrow():
    """Time + window has already passed → advance to next day."""
    now = datetime(2026, 5, 9, 14, 30)  # Sat
    out = compute_target_datetime(now, target_time=time(8, 0), window_minutes=60)
    # 08:00 + 60min = 09:00, well past 14:30 → roll to Sun 08:00.
    assert out == datetime(2026, 5, 10, 8, 0)


def test_target_time_today_within_window_stays_today():
    """We're past the time but still inside the window → stay today."""
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(now, target_time=time(14, 0), window_minutes=60)
    # 14:00 + 60 = 15:00, still ahead of 14:30 → stay today.
    assert out == datetime(2026, 5, 9, 14, 0)


def test_target_days_only_skips_today_when_not_selected():
    """Today is Tue (1); only Wed/Fri allowed → roll to Wed."""
    now = datetime(2026, 5, 12, 9, 0)  # Tuesday
    out = compute_target_datetime(now, days=[2, 4])
    assert out is not None
    assert out.weekday() == 2  # Wednesday
    assert out.date() == date(2026, 5, 13)


def test_target_days_only_today_selected_returns_today():
    now = datetime(2026, 5, 13, 9, 0)  # Wednesday
    out = compute_target_datetime(now, days=[2, 4])
    assert out is not None
    assert out.weekday() == 2
    assert out.date() == date(2026, 5, 13)


def test_target_days_plus_time_today_passed_rolls_to_next_selected():
    now = datetime(2026, 5, 13, 14, 0)  # Wed 14:00
    out = compute_target_datetime(
        now, days=[2, 4], target_time=time(8, 0), window_minutes=0,
    )
    # Wed 08:00 already passed → next selected day is Fri (4).
    assert out == datetime(2026, 5, 15, 8, 0)


def test_target_empty_days_treated_as_every_day():
    now = datetime(2026, 5, 9, 14, 30)
    out = compute_target_datetime(now, days=[])
    assert out == datetime(2026, 5, 9, 14, 30)


# ---- apply_window_filter ----------------------------------------------------


def _make_trip(planned_iso: str) -> dict:
    return {"legs": [{"origin": {"plannedDateTime": planned_iso}}]}


def test_window_zero_pick_single_returns_closest_trip():
    """v2.16.0: window=0 + pick_single returns exactly one trip — the
    closest to the anchor. Used when the user set a time-of-day filter."""
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        _make_trip("2026-05-09T13:50:00"),  # 10 min before
        _make_trip("2026-05-09T14:05:00"),  # 5 min after — closest
        _make_trip("2026-05-09T14:10:00"),  # 10 min after
    ]
    out = apply_window_filter(trips, target, window_minutes=0, pick_single=True)
    assert len(out) == 1
    assert out[0]["legs"][0]["origin"]["plannedDateTime"] == "2026-05-09T14:05:00"


def test_window_zero_pick_single_tie_breaks_prefer_before_anchor():
    """When two trips are equidistant from the anchor, the one that
    departs at-or-before the anchor wins (user's stated rule)."""
    target = datetime(2026, 5, 9, 9, 0)
    trips = [
        _make_trip("2026-05-09T08:50:00"),  # 10 min before
        _make_trip("2026-05-09T09:10:00"),  # 10 min after
    ]
    out = apply_window_filter(trips, target, window_minutes=0, pick_single=True)
    assert len(out) == 1
    assert out[0]["legs"][0]["origin"]["plannedDateTime"] == "2026-05-09T08:50:00"


def test_window_zero_pick_single_tie_breaks_then_shorter_duration():
    """If both offset and after-anchor flag tie, shortest travel time wins."""
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        {**_make_trip("2026-05-09T14:05:00"), "actualDurationInMinutes": 60},
        {**_make_trip("2026-05-09T14:05:00"), "actualDurationInMinutes": 30},
    ]
    out = apply_window_filter(trips, target, window_minutes=0, pick_single=True)
    assert len(out) == 1
    assert out[0]["actualDurationInMinutes"] == 30


def test_window_zero_pick_single_returns_empty_when_no_valid_trips():
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        _make_trip(""),
        _make_trip("not-a-date"),
        {"legs": []},
    ]
    out = apply_window_filter(trips, target, window_minutes=0, pick_single=True)
    assert out == []


def test_window_zero_no_pick_single_keeps_at_or_after_target():
    """Without pick_single (days-only / specific-date routes), window=0
    just filters out the trips before the anchor — same as v2.14.x."""
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        _make_trip("2026-05-09T13:50:00"),  # before — drop
        _make_trip("2026-05-09T14:00:00"),  # exact — keep
        _make_trip("2026-05-09T14:10:00"),  # after — keep
    ]
    out = apply_window_filter(trips, target, window_minutes=0)
    assert len(out) == 2


def test_window_zero_falls_back_to_duration_default():
    """When neither actual nor planned duration is present, the
    duration tie-break treats it as 99999 — both trips compare equal,
    list order survives."""
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        _make_trip("2026-05-09T14:05:00"),
        _make_trip("2026-05-09T14:05:00"),
    ]
    out = apply_window_filter(trips, target, window_minutes=0, pick_single=True)
    assert len(out) == 1


def test_window_zero_pick_single_uses_planned_duration_fallback():
    """When actualDurationInMinutes is missing, plannedDurationInMinutes
    is used for the tie-break."""
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        {**_make_trip("2026-05-09T14:05:00"), "plannedDurationInMinutes": 60},
        {**_make_trip("2026-05-09T14:05:00"), "plannedDurationInMinutes": 30},
    ]
    out = apply_window_filter(trips, target, window_minutes=0, pick_single=True)
    assert out[0]["plannedDurationInMinutes"] == 30


def test_window_keeps_trips_inside_interval():
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        _make_trip("2026-05-09T13:00:00"),   # 60 min before — outside
        _make_trip("2026-05-09T13:31:00"),   # inside (-29)
        _make_trip("2026-05-09T14:00:00"),   # exact
        _make_trip("2026-05-09T14:29:00"),   # inside (+29)
        _make_trip("2026-05-09T15:00:00"),   # 60 min after — outside
    ]
    out = apply_window_filter(trips, target, window_minutes=30)
    assert len(out) == 3


def test_window_handles_z_suffix_iso():
    target = datetime(2026, 5, 9, 14, 0)
    trips = [_make_trip("2026-05-09T14:00:00Z")]
    out = apply_window_filter(trips, target, window_minutes=15)
    # Z suffix → tz-aware → stripped to naive for comparison; matches.
    assert len(out) == 1


def test_window_drops_trips_with_missing_or_invalid_iso():
    target = datetime(2026, 5, 9, 14, 0)
    trips = [
        {"legs": [{"origin": {}}]},  # no plannedDateTime
        _make_trip(""),               # empty
        _make_trip("not-a-date"),     # garbage
        _make_trip("2026-05-09T14:00:00"),  # valid, in range
    ]
    out = apply_window_filter(trips, target, window_minutes=15)
    assert len(out) == 1


def test_window_handles_trip_without_legs():
    target = datetime(2026, 5, 9, 14, 0)
    trips = [{"legs": []}, _make_trip("2026-05-09T14:00:00")]
    # window=0 returns the single closest trip — empty-legs is skipped.
    out = apply_window_filter(trips, target, window_minutes=0)
    assert len(out) == 1
