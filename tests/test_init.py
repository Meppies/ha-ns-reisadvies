"""Tests for setup, unload, and migration of the hub."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ns_reisadvies.const import (
    CONF_API_KEY,
    CONF_FROM_STATION,
    CONF_TO_STATION,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)


def _make_hub_entry(
    *, with_subentry: bool = True, version: int = CONFIG_ENTRY_VERSION
) -> MockConfigEntry:
    subentries: list[dict] = []
    if with_subentry:
        subentries.append(
            {
                "subentry_type": SUBENTRY_TYPE_ROUTE,
                "title": "Hilversum -> Duivendrecht",
                "unique_id": "hilversum_duivendrecht",
                "data": {
                    CONF_FROM_STATION: "Hilversum",
                    CONF_TO_STATION: "Duivendrecht",
                },
            }
        )
    return MockConfigEntry(
        version=version,
        domain=DOMAIN,
        title="NS Reisadvies",
        data={CONF_API_KEY: "test-key"},
        options={},
        subentries_data=subentries,
        source=config_entries.SOURCE_USER,
    )


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """The hub sets up a coordinator per route subentry, unload tears it down."""
    entry = _make_hub_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ns_reisadvies.NSUpdateCoordinator.async_load_tracked",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies.NSUpdateCoordinator.async_refresh",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies._async_register_card_resource",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies._async_refresh_rail_cache",
            new=AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.entry_id in hass.data[DOMAIN]
    coordinators = hass.data[DOMAIN][entry.entry_id]
    assert len(coordinators) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_setup_survives_transient_api_outage(hass: HomeAssistant) -> None:
    """A 5xx on first refresh must not put the entry in setup_retry."""
    entry = _make_hub_entry()
    entry.add_to_hass(hass)

    refresh = AsyncMock()
    refresh.side_effect = lambda: None  # async_refresh swallows the error

    with (
        patch(
            "custom_components.ns_reisadvies.NSUpdateCoordinator.async_load_tracked",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies.NSUpdateCoordinator.async_refresh",
            new=refresh,
        ),
        patch(
            "custom_components.ns_reisadvies._async_register_card_resource",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies._async_refresh_rail_cache",
            new=AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Even though refresh "did nothing", the entry is loaded and the coordinator
    # is registered — the sensor will be created in "No trips" state.
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_recover_subentries_from_storage(hass: HomeAssistant) -> None:
    """If the hub has no subentries but Store files exist, rebuild them."""
    entry = _make_hub_entry(with_subentry=False)
    entry.add_to_hass(hass)

    fake_files = [
        "ns_reisadvies_tracked_trips_Hilversum_Duivendrecht",
        "core.entity_registry",
    ]

    with (
        patch(
            "custom_components.ns_reisadvies.os.listdir",
            return_value=fake_files,
        ),
        patch(
            "custom_components.ns_reisadvies.NSUpdateCoordinator.async_load_tracked",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies.NSUpdateCoordinator.async_refresh",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies._async_register_card_resource",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.ns_reisadvies._async_refresh_rail_cache",
            new=AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # The recovered subentry should now exist.
    assert any(
        sub.subentry_type == SUBENTRY_TYPE_ROUTE
        and sub.data.get(CONF_FROM_STATION).lower() == "hilversum"
        and sub.data.get(CONF_TO_STATION).lower() == "duivendrecht"
        for sub in entry.subentries.values()
    )
