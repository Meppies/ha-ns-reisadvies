"""Test config_flow steps by instantiating the flow class directly.

This bypasses ``hass.config_entries.flow.async_init`` which triggers
frontend/lovelace dependency setup that the default test fixture
cannot satisfy.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.config_flow import NSReisadviesConfigFlow
from custom_components.ns_reisadvies.const import (
    CONF_API_KEY, CONF_FROM_STATION, CONF_TO_STATION, DOMAIN,
)


def _make_flow(hass):
    flow = NSReisadviesConfigFlow()
    flow.hass = hass
    flow._async_current_entries = MagicMock(return_value=[])  # type: ignore
    return flow


async def test_user_step_shows_form_when_no_input(hass):
    flow = _make_flow(hass)
    result = await flow.async_step_user(user_input=None)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_aborts_when_entry_exists(hass):
    flow = _make_flow(hass)
    flow._async_current_entries = MagicMock(return_value=[MagicMock()])  # type: ignore
    result = await flow.async_step_user(user_input=None)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_step_invalid_auth_shows_error(hass):
    flow = _make_flow(hass)
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value="invalid_auth"),
    ):
        result = await flow.async_step_user(user_input={
            CONF_API_KEY: "k", CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht",
        })
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_step_cannot_connect_shows_error(hass):
    flow = _make_flow(hass)
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value="cannot_connect"),
    ):
        result = await flow.async_step_user(user_input={
            CONF_API_KEY: "k", CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht",
        })
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_step_unknown_station_shows_error(hass):
    flow = _make_flow(hass)
    result = await flow.async_step_user(user_input={
        CONF_API_KEY: "k", CONF_FROM_STATION: "Atlantis", CONF_TO_STATION: "Hilversum",
    })
    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_FROM_STATION] == "unknown_station"


async def test_user_step_success_creates_entry(hass):
    flow = _make_flow(hass)
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result = await flow.async_step_user(user_input={
            CONF_API_KEY: "k", CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht",
        })
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NS Reisadvies"
    assert result["data"][CONF_API_KEY] == "k"
    assert len(result["subentries"]) == 1


async def test_reauth_step_shows_form(hass):
    flow = _make_flow(hass)
    flow.context = {"source": "reauth"}
    result = await flow.async_step_reauth_confirm(user_input=None)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_step_invalid_key_shows_error(hass):
    flow = _make_flow(hass)
    flow.context = {"source": "reauth"}
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value="invalid_auth"),
    ):
        result = await flow.async_step_reauth_confirm(user_input={CONF_API_KEY: "bad"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_success_updates_entry_and_aborts(hass):
    flow = _make_flow(hass)
    flow.context = {"source": "reauth"}
    existing = MagicMock()
    existing.data = {CONF_API_KEY: "old"}
    existing.entry_id = "e1"
    flow._get_reauth_entry = MagicMock(return_value=existing)  # type: ignore
    fake_hass = MagicMock()
    fake_hass.config_entries.async_update_entry = MagicMock()
    fake_hass.config_entries.async_reload = AsyncMock()
    fake_hass.async_create_task = MagicMock()
    flow.hass = fake_hass
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result = await flow.async_step_reauth_confirm(user_input={CONF_API_KEY: "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    fake_hass.config_entries.async_update_entry.assert_called_once()


async def test_reauth_entry_point_routes_to_confirm(hass):
    flow = _make_flow(hass)
    flow.context = {"source": "reauth"}
    result = await flow.async_step_reauth(entry_data={CONF_API_KEY: "x"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


def test_options_flow_factory_returns_handler(hass):
    cfg = MagicMock()
    handler = NSReisadviesConfigFlow.async_get_options_flow(cfg)
    assert handler is not None


def test_subentry_factory_returns_route_handler(hass):
    from custom_components.ns_reisadvies.config_flow import NSRouteSubentryFlowHandler
    from custom_components.ns_reisadvies.const import SUBENTRY_TYPE_ROUTE
    cfg = MagicMock()
    types = NSReisadviesConfigFlow.async_get_supported_subentry_types(cfg)
    assert types[SUBENTRY_TYPE_ROUTE] is NSRouteSubentryFlowHandler
