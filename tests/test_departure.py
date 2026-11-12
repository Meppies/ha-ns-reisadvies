"""Pure helpers behind the delay and next-train sensors (v2.20.0)."""
from __future__ import annotations

from custom_components.ns_reisadvies._departure import next_departure, summary_line


def _leg(planned="2026-11-02T08:09:00+0100", actual=None, *, code="IC",
         number="1522", ptrack="5", atrack=None, product=True):
    origin = {"plannedDateTime": planned, "plannedTrack": ptrack}
    if actual:
        origin["actualDateTime"] = actual
    if atrack:
        origin["actualTrack"] = atrack
    leg = {"origin": origin}
    if product:
        leg["product"] = {"categoryCode": code, "shortCategoryName": code, "number": number}
    return leg


def _trip(*legs, status="NORMAL"):
    return {"status": status, "legs": list(legs)}


def test_no_trips() -> None:
    assert next_departure(None) is None
    assert next_departure([]) is None
    assert summary_line(None, "nl") is None


def test_trip_without_a_boarded_leg_is_skipped() -> None:
    walk_only = _trip(_leg(product=False))
    assert next_departure([walk_only, "not a trip"]) is None


def test_walking_leg_before_the_train_is_skipped() -> None:
    info = next_departure([_trip(_leg(product=False, ptrack=None), _leg())])
    assert info["train"] == "IC 1522"
    assert info["track"] == "5"


def test_on_time() -> None:
    info = next_departure([_trip(_leg())])
    assert info == {
        "delay": 0, "train": "IC 1522", "planned": "08:09", "expected": "08:09",
        "track": "5", "track_changed": False, "status": "on_time",
    }


def test_delayed_with_track_change() -> None:
    info = next_departure([_trip(_leg(actual="2026-11-02T08:13:00+0100", atrack="4b"))])
    assert info["delay"] == 4
    assert info["expected"] == "08:13"
    assert info["status"] == "delayed"
    assert info["track"] == "4b" and info["track_changed"] is True


def test_early_departure_is_not_negative_delay() -> None:
    info = next_departure([_trip(_leg(actual="2026-11-02T08:08:00+0100"))])
    assert info["delay"] == 0 and info["status"] == "on_time"


def test_cancelled_trip() -> None:
    info = next_departure([_trip(_leg(), status="CANCELLED")])
    assert info["status"] == "cancelled"


def test_missing_times_and_codes() -> None:
    info = next_departure([_trip({"origin": {}, "product": {"categoryCode": "SPR"}})])
    assert info["train"] == "SPR"
    assert info["planned"] is None and info["expected"] is None
    assert info["delay"] == 0 and info["track"] is None


def test_summary_dutch_and_english() -> None:
    late = next_departure([_trip(_leg(actual="2026-11-02T08:13:00+0100", atrack="4"))])
    assert summary_line(late, "nl") == "IC 08:09 +4, spoor 4!"
    assert summary_line(late, "en-GB") == "IC 08:09 +4, platform 4!"
    assert summary_line(late, "de") == "IC 08:09 +4, platform 4!"
    assert summary_line(late, None) == "IC 08:09 +4, platform 4!"
    on_time = next_departure([_trip(_leg())])
    assert summary_line(on_time, "nl") == "IC 08:09, spoor 5"
    gone = next_departure([_trip(_leg(), status="CANCELLED")])
    assert summary_line(gone, "nl") == "IC 08:09 vervalt"
    assert summary_line(gone, "en") == "IC 08:09 cancelled"


def test_summary_is_plain_ascii() -> None:
    """Small displays lack glyphs like the middle dot or arrows."""
    late = next_departure([_trip(_leg(actual="2026-11-02T08:13:00+0100", atrack="4"))])
    assert summary_line(late, "nl").isascii()


def test_summary_without_track_or_train() -> None:
    bare = next_departure([_trip({"origin": {}, "product": {"categoryCode": "IC"}})])
    assert summary_line(bare, "nl") == "IC"
    assert summary_line({"status": "on_time", "train": None}, "nl") is None
