"""Per-route train-type filter (v2.19.0).

Covers the pure helper, the coordinator wiring that actually decides
what a route publishes, the follow-up search that keeps a strict
filter from emptying the list, and the config-flow persistence.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies._filter import (
    apply_train_type_filter,
    leg_category_codes,
    train_types_in,
)
from custom_components.ns_reisadvies.config_flow import (
    NSRouteSubentryFlowHandler,
    _train_type_options,
)
from custom_components.ns_reisadvies.const import (
    CONF_FILTER_TRAIN_TYPES,
    CONF_FROM_STATION,
    CONF_TO_STATION,
    TRAIN_TYPE_CODES,
)
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator

# Far enough ahead that the stale-trip pass never drops these.
DEP = "2099-05-04T08:00:00+02:00"


def _leg(code: str | None, *, walk: bool = False) -> dict:
    if walk:
        return {"origin": {"plannedDateTime": DEP}}
    return {
        "product": {"categoryCode": code, "shortCategoryName": code},
        "origin": {"plannedDateTime": DEP},
    }


def _trip(*codes: str, ctx: str | None = None, walk: bool = False) -> dict:
    legs = [_leg(c) for c in codes]
    if walk:
        legs.insert(0, _leg(None, walk=True))
    return {"ctxRecon": ctx or "+".join(codes), "legs": legs}


# ---- the helper -----------------------------------------------------


def test_no_selection_returns_the_trips_untouched() -> None:
    trips = [_trip("IC"), _trip("SPR")]
    assert apply_train_type_filter(trips, []) is trips
    assert apply_train_type_filter(trips, None) is trips
    assert apply_train_type_filter(trips, ["   "]) is trips


def test_every_boarded_leg_must_match() -> None:
    trips = [_trip("IC"), _trip("SPR"), _trip("ICD"), _trip("ICD", "SPR")]
    kept = [t["ctxRecon"] for t in apply_train_type_filter(trips, ["IC", "ICD"])]
    # The ICD+SPR trip goes: you would still have to take that sprinter.
    assert kept == ["IC", "ICD"]


def test_transfer_between_two_allowed_types_is_kept() -> None:
    kept = apply_train_type_filter([_trip("IC", "ICD")], ["IC", "ICD"])
    assert len(kept) == 1


def test_legs_without_a_product_do_not_count() -> None:
    """Walking to the platform must not disqualify a trip."""
    assert len(apply_train_type_filter([_trip("IC", walk=True)], ["IC"])) == 1
    # A product with no category code at all is equally uninformative.
    trip = {"legs": [{"product": {"operatorName": "NS"}}, _leg("IC")]}
    assert apply_train_type_filter([trip], ["IC"]) == [trip]


def test_matching_ignores_case_and_takes_either_field() -> None:
    lower = {"legs": [{"product": {"shortCategoryName": "ic"}}]}
    assert apply_train_type_filter([lower], ["IC"]) == [lower]
    code_only = {"legs": [{"product": {"categoryCode": "SPR"}}]}
    assert apply_train_type_filter([code_only], ["spr"]) == [code_only]


def test_trip_with_nothing_to_board_is_dropped() -> None:
    trips = [{"legs": [{"product": {}}]}, {"legs": []}, {}, {"legs": ["junk"]}]
    assert apply_train_type_filter(trips, ["IC"]) == []


def test_leg_category_codes_and_train_types_in() -> None:
    assert leg_category_codes({"product": {"categoryCode": " ic "}}) == {"IC"}
    assert leg_category_codes({}) == set()
    assert train_types_in([_trip("IC", "SPR"), _trip("ICD")]) == ["IC", "ICD", "SPR"]
    assert train_types_in([]) == []


# ---- the picker -----------------------------------------------------


def test_picker_keeps_our_order_and_labels_both_languages() -> None:
    options = _train_type_options("nl")
    assert [o["value"] for o in options] == list(TRAIN_TYPE_CODES)
    labels = {o["value"]: o["label"] for o in options}
    assert labels["SPR"] == "Sprinter (SPR)"
    assert labels["ST"] == "Stoptrein (ST)"
    assert _train_type_options("en")[3]["label"] == "Local train (ST)"
    # An unknown UI language falls back to English rather than crashing.
    assert _train_type_options("de")[0]["label"] == "Intercity (IC)"


# ---- the coordinator ------------------------------------------------


def _resp(status: int, payload: dict | None = None):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=payload or {})
    r.__aenter__ = AsyncMock(return_value=r)
    r.__aexit__ = AsyncMock(return_value=None)
    return r


def _coord(hass: HomeAssistant, **kw) -> NSUpdateCoordinator:
    defaults = {
        "api_key": "k",
        "from_station": "Hilversum",
        "to_station": "Duivendrecht",
        "scan_interval_minutes": 5,
        "fav_hours": 6,
    }
    defaults.update(kw)
    coord = NSUpdateCoordinator(hass, **defaults)
    coord._store = MagicMock()
    coord._store.async_load = AsyncMock(return_value=None)
    coord._store.async_save = AsyncMock()
    return coord


async def test_selection_is_normalised(hass: HomeAssistant) -> None:
    coord = _coord(hass, filter_train_types=[" ic ", "icd", "IC", ""])
    assert coord.filter_train_types == ["IC", "ICD"]  # upper, de-duped, in order
    assert _coord(hass).filter_train_types == []
    assert _coord(hass, filter_train_types=None).filter_train_types == []


async def test_update_filters_the_published_trips(hass: HomeAssistant) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    payload = {"trips": [_trip("IC", ctx="A"), _trip("SPR", ctx="B")]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))

    out = await coord._async_update_data()

    assert [t["ctxRecon"] for t in out] == ["A"]
    # Reported before filtering, so the route shows what it really runs.
    assert coord.available_train_types == ["IC", "SPR"]


async def test_a_pinned_favourite_survives_its_type_being_excluded(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    coord.tracked_trips = {"B": time.time()}  # pinned just now
    payload = {"trips": [_trip("IC", ctx="A"), _trip("SPR", ctx="B")]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))

    out = await coord._async_update_data()

    assert sorted(t["ctxRecon"] for t in out) == ["A", "B"]


async def test_update_without_a_selection_keeps_every_trip(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    payload = {"trips": [_trip("IC", ctx="A"), _trip("SPR", ctx="B")]}
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, payload))

    out = await coord._async_update_data()

    assert sorted(t["ctxRecon"] for t in out) == ["A", "B"]
    assert coord.available_train_types == ["IC", "SPR"]


# ---- the follow-up search -------------------------------------------


def _many(prefix: str, code: str, count: int, hour: int) -> list[dict]:
    out = []
    for i in range(count):
        trip = _trip(code, ctx=f"{prefix}{i}")
        stamp = f"2099-05-04T{hour:02d}:{i:02d}:00+02:00"
        trip["legs"][0]["origin"]["plannedDateTime"] = stamp
        out.append(trip)
    return out


async def test_search_more_tops_up_a_thin_result(hass: HomeAssistant) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    first = [_trip("IC", ctx="A"), *_many("spr", "SPR", 5, 8)]
    second = _many("ic", "IC", 5, 9)
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[_resp(200, {"trips": second})])

    merged = await coord._async_search_more({}, {"dateTime": "x"}, first)

    assert len(merged) == 11
    # The follow-up asks for trips starting after the last one that was
    # already in hand when it went out (08:04 + a minute).
    assert coord._session.get.call_args.kwargs["params"]["dateTime"].startswith(
        "2099-05-04T08:05"
    )
    # Five allowed trips is enough, so it stops after one extra search.
    assert coord._session.get.call_count == 1


async def test_search_more_stops_at_two_extra_searches(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=[
        _resp(200, {"trips": _many("b", "SPR", 3, 9)}),
        _resp(200, {"trips": _many("c", "SPR", 3, 10)}),
        _resp(200, {"trips": _many("d", "SPR", 3, 11)}),
    ])

    merged = await coord._async_search_more(
        {}, {"dateTime": "x"}, _many("a", "SPR", 3, 8),
    )

    assert coord._session.get.call_count == 2  # never a third
    assert len(merged) == 9


async def test_search_more_is_a_no_op_without_a_selection(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    coord._session = MagicMock()
    trips = _many("a", "SPR", 1, 8)
    assert await coord._async_search_more({}, {}, trips) is trips
    coord._session.get.assert_not_called()


async def test_search_more_gives_up_quietly_on_a_bad_response(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(429, {}))
    trips = _many("a", "SPR", 2, 8)

    merged = await coord._async_search_more({}, {"dateTime": "x"}, trips)

    assert merged == trips  # a thin list beats a failed refresh
    assert coord._session.get.call_count == 1


async def test_search_more_gives_up_quietly_when_the_call_fails(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    coord._session = MagicMock()
    coord._session.get = MagicMock(side_effect=aiohttp.ClientError("boom"))
    trips = _many("a", "SPR", 2, 8)

    assert await coord._async_search_more({}, {"dateTime": "x"}, trips) == trips


async def test_search_more_stops_when_ns_repeats_itself(
    hass: HomeAssistant,
) -> None:
    """Same ctxRecons back means there is nothing further to fetch."""
    coord = _coord(hass, filter_train_types=["IC"])
    trips = _many("a", "SPR", 2, 8)
    coord._session = MagicMock()
    coord._session.get = MagicMock(return_value=_resp(200, {"trips": trips}))

    merged = await coord._async_search_more({}, {"dateTime": "x"}, trips)

    assert len(merged) == 2
    assert coord._session.get.call_count == 1


async def test_search_more_needs_a_usable_timestamp(hass: HomeAssistant) -> None:
    coord = _coord(hass, filter_train_types=["IC"])
    coord._session = MagicMock()
    undated = [{"ctxRecon": "X", "legs": [{"product": {"categoryCode": "SPR"}}]}]

    assert await coord._async_search_more({}, {}, undated) == undated
    coord._session.get.assert_not_called()


# ---- the route form -------------------------------------------------


class _Flow(NSRouteSubentryFlowHandler):
    """Subclass that bypasses the flow-runtime methods we don't have."""

    def _get_entry(self):
        return None


def _flow() -> _Flow:
    f = _Flow()
    f.hass = MagicMock()
    f.async_create_entry = MagicMock(
        return_value={"type": FlowResultType.CREATE_ENTRY},
    )
    f.async_show_form = MagicMock(
        return_value={"type": FlowResultType.FORM, "step_id": "x", "errors": {}},
    )
    return f


async def test_route_form_stores_the_selection() -> None:
    f = _flow()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        "filters": {CONF_FILTER_TRAIN_TYPES: ["ic", "ICD", "ic"]},
    })
    data = f.async_create_entry.call_args.kwargs["data"]
    assert data[CONF_FILTER_TRAIN_TYPES] == ["IC", "ICD"]


async def test_clearing_the_field_removes_the_key() -> None:
    f = _flow()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        "filters": {CONF_FILTER_TRAIN_TYPES: []},
    })
    data = f.async_create_entry.call_args.kwargs["data"]
    assert CONF_FILTER_TRAIN_TYPES not in data
