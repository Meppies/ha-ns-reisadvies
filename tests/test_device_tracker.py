"""device_tracker platform for pinned favourites (v2.18.1).

One tracker per route, following whichever favourite is being
travelled; v2.18.0's per-favourite entities are removed on upgrade.
"""
from __future__ import annotations

import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.device_tracker import SourceType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
    CONF_TO_STATION,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)
from custom_components.ns_reisadvies.coordinator import NSUpdateCoordinator, parse_iso
from custom_components.ns_reisadvies.device_tracker import (
    NSFavouriteTracker,
    _async_drop_legacy_entities,
    async_setup_entry,
    route_identity,
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
        coord,
        route_uid="duivendrecht_hilversum",
        route_slug="werk",
        route_label="Werk",
    )


async def test_identity_is_stable_per_route(hass: HomeAssistant) -> None:
    tracker = _tracker(_coord(hass))
    # Keyed on the route, not on a dated trip, so automations survive.
    assert tracker.unique_id == "duivendrecht_hilversum_favourite"
    assert tracker.name == "NS favourite Werk"
    assert tracker._attr_suggested_object_id == "ns_favourite_werk"
    assert tracker.source_type is SourceType.GPS
    assert tracker.translation_key == "favourite"  # icon via icons.json
    assert tracker.entity_category is None  # not a diagnostic entity
    assert tracker.device_info is None  # HA pins this for trackers


def test_route_identity_falls_back_to_the_station_pair() -> None:
    uid, slug, label = route_identity(
        {CONF_FROM_STATION: "Duivendrecht", CONF_TO_STATION: "Hilversum"},
    )
    assert uid == "duivendrecht_hilversum"
    assert slug == "duivendrecht_hilversum"
    assert label == "Duivendrecht → Hilversum"

    named = route_identity({
        CONF_FROM_STATION: "Duivendrecht",
        CONF_TO_STATION: "Hilversum",
        CONF_ROUTE_NAME: "  Naar werk  ",
    })
    assert named == ("duivendrecht_hilversum_naar_werk", "naar_werk", "Naar werk")


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
    assert attrs["favourite_ctx"] == CTX
    assert attrs["pinned_favourites"] == 1
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


async def test_entity_stays_available_without_a_pin(hass: HomeAssistant) -> None:
    """An automation should not break between trips."""
    coord = _coord(hass)
    tracker = _tracker(coord)
    assert tracker.available is True
    coord.tracked_trips = {}
    coord.favourite_positions = {}
    assert tracker.available is True
    assert tracker.latitude is None
    assert tracker.extra_state_attributes["pinned_favourites"] == 0
    assert tracker.extra_state_attributes["phase"] is None
    coord.last_update_success = False
    assert tracker.available is False


async def test_added_to_hass_subscribes_to_position_updates(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    tracker = _tracker(coord)
    tracker.hass = hass
    tracker.entity_id = "device_tracker.ns_favourite_werk"
    await tracker.async_added_to_hass()
    assert coord._fav_listeners  # the platform follows refreshes
    # HA runs these when the entity is removed; the subscription must
    # detach so a reload does not leave a dead listener behind.
    for unsub in list(tracker._on_remove or []):
        unsub()
    assert not coord._fav_listeners


async def test_setup_entry_requires_runtime_and_option(hass: HomeAssistant) -> None:
    entry = SimpleNamespace(runtime_data=None, subentries={}, entry_id="e1")
    assert await async_setup_entry(hass, entry, lambda *_a, **_k: None) is False

    coord = _coord(hass, track_favourites=False)
    runtime = SimpleNamespace(coordinators={"sub1": coord})
    subentry = SimpleNamespace(
        subentry_type=SUBENTRY_TYPE_ROUTE,
        data={CONF_FROM_STATION: "Duivendrecht", CONF_TO_STATION: "Hilversum"},
    )
    added: list = []
    entry = SimpleNamespace(
        runtime_data=runtime, subentries={"sub1": subentry}, entry_id="e1",
    )
    assert await async_setup_entry(hass, entry, lambda e, **_k: added.extend(e)) is True
    assert added == []  # option off: no trackers


async def test_setup_entry_creates_one_tracker_per_route(
    hass: HomeAssistant,
) -> None:
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
    entry = SimpleNamespace(
        runtime_data=runtime,
        subentries={"sub1": route, "sub2": other},
        entry_id="e1",
    )
    added: list = []
    assert await async_setup_entry(
        hass, entry, lambda e, **_k: added.extend(e),
    ) is True
    assert len(added) == 1
    assert added[0].unique_id == "duivendrecht_hilversum_werk_favourite"


async def test_setup_entry_handles_old_add_entities_signature(
    hass: HomeAssistant,
) -> None:
    coord = _coord(hass)
    added: list = []

    def _add(entities):  # no config_subentry_id — HA < 2024.11
        added.extend(entities)

    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(coordinators={"sub1": coord}),
        subentries={"sub1": SimpleNamespace(
            subentry_type=SUBENTRY_TYPE_ROUTE,
            data={CONF_FROM_STATION: "Duivendrecht", CONF_TO_STATION: "Hilversum"},
        )},
        entry_id="e1",
    )
    assert await async_setup_entry(hass, entry, _add) is True
    assert len(added) == 1


async def test_legacy_per_favourite_entities_are_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """v2.18.0's dated entities cannot come back, so they are dropped."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    legacy = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, "duivendrecht_hilversum_fav_0123456789",
        config_entry=entry,
    )
    keeper = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, "duivendrecht_hilversum_favourite",
        config_entry=entry,
    )
    sensor = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "duivendrecht_hilversum_fav_9876543210",
        config_entry=entry,
    )

    _async_drop_legacy_entities(hass, entry)

    assert entity_registry.async_get(legacy.entity_id) is None
    assert entity_registry.async_get(keeper.entity_id) is not None
    assert entity_registry.async_get(sensor.entity_id) is not None  # other domain


async def test_legacy_cleanup_without_an_entry_id(hass: HomeAssistant) -> None:
    _async_drop_legacy_entities(hass, SimpleNamespace(entry_id=None))  # no crash
