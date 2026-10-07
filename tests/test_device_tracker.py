"""device_tracker platform for pinned favourites (v2.18.0)."""
from __future__ import annotations

import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.device_tracker import SourceType
from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
    SUBENTRY_TYPE_ROUTE,
)
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator, parse_iso
from custom_components.ns_reisadvies.device_tracker import (
    NSFavouriteTracker,
    NSFavouriteTrackerManager,
    async_setup_entry,
)

CTX = "CTX-ONE"
DEP = "2026-10-07T07:52:00+02:00"
ARR = "2026-10-07T08:06:00+02:00"


def _trip(ctx=CTX):
    return {
        "ctxRecon": ctx,
        "legs": [{
            "product": {
                "number": "1825",
                "shortCategoryName": "ICD",
                "operatorName": "NS",
            },
            "origin": {"name": "Duivendrecht", "plannedDateTime": DEP},
            "destination": {"name": "Hilversum", "plannedDateTime": ARR},
            "direction": "Amersfoort Schothorst",
        }],
    }


def _coord(hass: HomeAssistant, **kw) -> NSUpdateCoordinator:
    coord = NSUpdateCoordinator(
        hass,
        api_key="k",
        from_station="Duivendrecht",
        to_station="Hilversum",
        track_favourites=kw.pop("track_favourites", True),
        **kw,
    )
    coord._store = MagicMock()
    coord._store.async_save = AsyncMock(return_value=None)
    coord.data = [_trip()]
    coord.tracked_trips = {CTX: time.time()}
    coord.last_update_success = True
    return coord


def _tracker(coord) -> NSFavouriteTracker:
    return NSFavouriteTracker(
        coord, ctx_recon=CTX, route_uid="duivendrecht_hilversum", route_slug="werk",
    )


async def test_identity_and_naming(hass: HomeAssistant) -> None:
    tracker = _tracker(_coord(hass))
    assert tracker.unique_id.startswith("duivendrecht_hilversum_fav_")
    assert tracker.name == "NS favourite 07:52 → Hilversum"
    assert tracker._attr_suggested_object_id == "ns_fav_werk_07_52_hilversum"
    assert tracker.source_type is SourceType.GPS
    assert tracker.translation_key == "favourite"  # icon via icons.json
    assert tracker.entity_category is None  # not a diagnostic entity
    assert tracker.device_info is None  # HA pins this for trackers


async def test_naming_falls_back_without_trip_data(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.data = []
    tracker = _tracker(coord)
    assert tracker.name.startswith("NS favourite ")
    assert tracker.unique_id.startswith("duivendrecht_hilversum_fav_")


async def test_position_and_attributes(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    coord.async_fetch_arcgis_position = AsyncMock(return_value={
        "lat": 52.3, "lng": 4.94, "speed": 112, "heading": 90,
        "station_name": "Duivendrecht", "source": "arcgis",
    })
    await coord.async_refresh_favourite_positions(parse_iso(DEP) + timedelta(minutes=3))

    tracker = _tracker(coord)
    assert tracker.latitude == 52.3
    assert tracker.longitude == 4.94
    assert tracker.location_accuracy == 50
    attrs = tracker.extra_state_attributes
    assert attrs["en_route"] is True
    assert attrs["phase"] == "en_route"
    assert attrs["train_number"] == "1825"
    assert attrs["train_type"] == "ICD"
    assert attrs["leg_destination"] == "Hilversum"
    assert attrs["speed"] == 112
    assert attrs["position_source"] == "arcgis"
    assert attrs["position_fresh"] is True


async def test_no_position_before_departure(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    await coord.async_refresh_favourite_positions(parse_iso(DEP) - timedelta(hours=2))
    tracker = _tracker(coord)
    assert tracker.latitude is None
    assert tracker.longitude is None
    assert tracker.location_accuracy == 0
    attrs = tracker.extra_state_attributes
    assert attrs["phase"] == "upcoming"
    assert attrs["en_route"] is False
    assert "speed" not in attrs


async def test_availability_tracks_the_pin(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    tracker = _tracker(coord)
    assert tracker.available is True
    coord.tracked_trips = {}
    assert tracker.available is False
    coord.tracked_trips = {CTX: time.time()}
    coord.last_update_success = False
    assert tracker.available is False


async def test_manager_adds_and_removes_entities(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    added: list = []

    def _add(entities, config_subentry_id=None):
        added.extend(entities)

    manager = NSFavouriteTrackerManager(
        hass, coord,
        subentry_id="sub1",
        route_uid="duivendrecht_hilversum",
        route_slug="werk",
        async_add_entities=_add,
    )
    unsub = manager.async_start()
    assert len(added) == 1
    tracker = added[0]
    tracker.async_remove = AsyncMock()

    # A second sync with the same favourite adds nothing.
    manager._async_sync()
    assert len(added) == 1

    coord.tracked_trips = {}
    manager._async_sync()
    await hass.async_block_till_done()
    tracker.async_remove.assert_awaited_once()
    unsub()


async def test_manager_handles_old_add_entities_signature(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    added: list = []

    def _add(entities):  # no config_subentry_id — HA < 2024.11
        added.extend(entities)

    manager = NSFavouriteTrackerManager(
        hass, coord,
        subentry_id="sub1",
        route_uid="duivendrecht_hilversum",
        route_slug="werk",
        async_add_entities=_add,
    )
    manager._async_sync()
    assert len(added) == 1


async def test_setup_entry_requires_runtime_and_option(hass: HomeAssistant) -> None:
    entry = SimpleNamespace(runtime_data=None, subentries={}, async_on_unload=lambda _f: None)
    assert await async_setup_entry(hass, entry, lambda *_a, **_k: None) is False

    coord = _coord(hass, track_favourites=False)
    runtime = SimpleNamespace(coordinators={"sub1": coord})
    subentry = SimpleNamespace(
        subentry_type=SUBENTRY_TYPE_ROUTE,
        data={CONF_FROM_STATION: "Duivendrecht", CONF_TO_STATION: "Hilversum"},
    )
    added: list = []
    entry = SimpleNamespace(
        runtime_data=runtime,
        subentries={"sub1": subentry},
        async_on_unload=lambda _f: None,
    )
    assert await async_setup_entry(hass, entry, lambda e, **_k: added.extend(e)) is True
    assert added == []  # option off: no trackers


async def test_setup_entry_creates_trackers(hass: HomeAssistant) -> None:
    coord = _coord(hass)
    runtime = SimpleNamespace(coordinators={"sub1": coord})
    route = SimpleNamespace(
        subentry_type=SUBENTRY_TYPE_ROUTE,
        data={
            CONF_FROM_STATION: "Duivendrecht",
            CONF_TO_STATION: "Hilversum",
            CONF_ROUTE_NAME: "Werk",
        },
    )
    other = SimpleNamespace(subentry_type="something_else", data={})
    unsubs: list = []
    entry = SimpleNamespace(
        runtime_data=runtime,
        subentries={"sub1": route, "sub2": other},
        async_on_unload=unsubs.append,
    )
    added: list = []
    assert await async_setup_entry(
        hass, entry, lambda e, **_k: added.extend(e),
    ) is True
    assert len(added) == 1
    assert added[0].unique_id.startswith("duivendrecht_hilversum_werk_fav_")
    assert unsubs  # teardown registered
    unsubs[0]()


async def test_setup_entry_unnamed_route_slug(hass: HomeAssistant) -> None:
    """A route without a custom name falls back to the station pair."""
    coord = _coord(hass)
    runtime = SimpleNamespace(coordinators={"sub1": coord})
    route = SimpleNamespace(
        subentry_type=SUBENTRY_TYPE_ROUTE,
        data={CONF_FROM_STATION: "Duivendrecht", CONF_TO_STATION: "Hilversum"},
    )
    added: list = []
    entry = SimpleNamespace(
        runtime_data=runtime,
        subentries={"sub1": route},
        async_on_unload=lambda _f: None,
    )
    assert await async_setup_entry(hass, entry, lambda e, **_k: added.extend(e)) is True
    assert len(added) == 1
    assert added[0].unique_id.startswith("duivendrecht_hilversum_fav_")
    assert added[0]._attr_suggested_object_id.startswith(
        "ns_fav_duivendrecht_hilversum_"
    )
