"""Tests for the NS Reisadvies config flow."""
from __future__ import annotations

from typing import Any

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.const import (
    CONF_API_KEY,
    CONF_FROM_STATION,
    CONF_TO_STATION,
    CONF_SCAN_INTERVAL,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    CONF_LIVE_TRAIN_MAP,
    CONF_LIVE_MAP_REFRESH_SECONDS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
    DEFAULT_LIVE_MAP_REFRESH_SECONDS,
    DOMAIN,
)


async def _start_flow(
    hass: HomeAssistant, user_input: dict[str, Any] | None = None
) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=user_input,
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_creates_hub(hass: HomeAssistant) -> None:
    """Submitting valid input creates a hub entry with one route subentry."""
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] in (None, {})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "test-api-key",
            CONF_FROM_STATION: "Hilversum",
            CONF_TO_STATION: "Duivendrecht",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NS Reisadvies"
    data = result["data"]
    assert data[CONF_API_KEY] == "test-api-key"
    assert data[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL
    assert data[CONF_FAV_HOURS] == DEFAULT_FAV_HOURS
    assert data[CONF_FETCH_COMPOSITION] is False
    assert data[CONF_LIVE_TRAIN_MAP] is False
    assert data[CONF_LIVE_MAP_REFRESH_SECONDS] == DEFAULT_LIVE_MAP_REFRESH_SECONDS

    subentries = result.get("subentries") or []
    assert len(subentries) == 1
    sub = subentries[0]
    assert sub["data"][CONF_FROM_STATION] == "Hilversum"
    assert sub["data"][CONF_TO_STATION] == "Duivendrecht"
    assert sub["unique_id"] == "hilversum_duivendrecht"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_rejects_unknown_station(hass: HomeAssistant) -> None:
    """A station name that isn't in the catalogue surfaces a per-field error."""
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "test-api-key",
            CONF_FROM_STATION: "Atlantis Centraal",
            CONF_TO_STATION: "Duivendrecht",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_FROM_STATION] == "unknown_station"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_rejects_same_station(hass: HomeAssistant) -> None:
    """Departure equal to arrival is rejected."""
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "test-api-key",
            CONF_FROM_STATION: "Hilversum",
            CONF_TO_STATION: "Hilversum",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "same_station"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_single_instance_only(hass: HomeAssistant) -> None:
    """Adding a second hub aborts: one hub, many routes is the rule."""
    entry = config_entries.ConfigEntry(
        version=2,
        minor_version=1,
        domain=DOMAIN,
        title="NS Reisadvies",
        data={CONF_API_KEY: "x"},
        source=config_entries.SOURCE_USER,
        unique_id=None,
        options={},
        discovery_keys={},
        subentries_data=[],
    )
    entry.add_to_hass(hass)

    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
