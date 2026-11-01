"""Tests for the per-route train-type filter."""
from __future__ import annotations

from custom_components.ns_reisadvies._filter import apply_train_type_filter


def _trip(*codes: str, walk: bool = False) -> dict:
    legs = [
        {"product": {"type": "TRAIN", "categoryCode": c, "shortCategoryName": c}}
        for c in codes
    ]
    if walk:
        legs.insert(0, {"product": {"type": "WALK"}})
    return {"ctxRecon": "+".join(codes), "legs": legs}


def test_empty_filter_keeps_everything() -> None:
    trips = [_trip("IC"), _trip("SPR")]
    assert apply_train_type_filter(trips, []) == trips
    assert apply_train_type_filter(trips, None) == trips


def test_keeps_only_chosen_types() -> None:
    trips = [_trip("IC"), _trip("SPR"), _trip("ICD"), _trip("ICD", "SPR")]
    kept = apply_train_type_filter(trips, ["IC", "ICD"])
    assert [t["ctxRecon"] for t in kept] == ["IC", "ICD"]


def test_transfer_between_allowed_types_is_kept() -> None:
    kept = apply_train_type_filter([_trip("IC", "ICD")], ["IC", "ICD"])
    assert len(kept) == 1


def test_walking_leg_is_ignored() -> None:
    kept = apply_train_type_filter([_trip("IC", walk=True)], ["IC"])
    assert len(kept) == 1


def test_case_insensitive_and_either_field() -> None:
    trip = {"legs": [{"product": {"type": "TRAIN", "shortCategoryName": "ic"}}]}
    assert apply_train_type_filter([trip], ["IC"]) == [trip]
    trip2 = {"legs": [{"product": {"categoryCode": "SPR"}}]}
    assert apply_train_type_filter([trip2], ["spr"]) == [trip2]


def test_trip_without_train_legs_is_dropped() -> None:
    trips = [{"legs": [{"product": {"type": "WALK"}}]}, {"legs": []}, {}]
    assert apply_train_type_filter(trips, ["IC"]) == []
