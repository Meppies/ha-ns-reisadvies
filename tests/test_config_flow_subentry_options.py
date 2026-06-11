"""Cover SubentryFlow + OptionsFlow via direct class instantiation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.config_flow import (
    NSReisadviesOptionsFlowHandler, NSRouteSubentryFlowHandler,
)
from custom_components.ns_reisadvies.const import (
    CONF_API_KEY, CONF_FAV_HOURS, CONF_FETCH_COMPOSITION, CONF_FROM_STATION,
    CONF_LIVE_MAP_REFRESH_SECONDS, CONF_LIVE_TRAIN_MAP, CONF_SCAN_INTERVAL,
    CONF_TO_STATION, SUBENTRY_TYPE_ROUTE,
)


# ---- OptionsFlow ----


def _make_options(hass, options=None, data=None):
    cfg = MagicMock()
    cfg.options = options or {}
    cfg.data = data or {CONF_API_KEY: "k"}
    flow = NSReisadviesOptionsFlowHandler(cfg)
    flow.hass = hass
    return flow


async def test_options_init_shows_form_no_input(hass):
    flow = _make_options(hass)
    result = await flow.async_step_init(user_input=None)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_init_invalid_key_shows_error(hass):
    flow = _make_options(hass)
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value="invalid_auth"),
    ):
        result = await flow.async_step_init(user_input={CONF_API_KEY: "bad"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_options_init_success_updates_entry(hass):
    flow = _make_options(hass)
    fake_hass = MagicMock()
    fake_hass.config_entries.async_update_entry = MagicMock()
    flow.hass = fake_hass
    user_input = {
        CONF_API_KEY: "new", CONF_SCAN_INTERVAL: 5, CONF_FAV_HOURS: 6,
        CONF_FETCH_COMPOSITION: True, CONF_LIVE_TRAIN_MAP: True,
        CONF_LIVE_MAP_REFRESH_SECONDS: 15,
    }
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result = await flow.async_step_init(user_input=user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # v2.16.24: options now flow through ``async_create_entry(data=…)``;
    # ``async_update_entry`` only persists the API key into entry.data.
    fake_hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = fake_hass.config_entries.async_update_entry.call_args
    assert kwargs["data"][CONF_API_KEY] == "new"
    assert "options" not in kwargs
    assert result["data"][CONF_SCAN_INTERVAL] == 5
    assert CONF_API_KEY not in result["data"]


def test_options_read_prefers_options_over_data(hass):
    flow = _make_options(
        hass,
        options={CONF_SCAN_INTERVAL: 7},
        data={CONF_API_KEY: "k", CONF_SCAN_INTERVAL: 99},
    )
    assert flow._read(CONF_SCAN_INTERVAL, 0) == 7


def test_options_read_falls_back_to_data(hass):
    flow = _make_options(
        hass,
        options={},
        data={CONF_API_KEY: "k", CONF_SCAN_INTERVAL: 99},
    )
    assert flow._read(CONF_SCAN_INTERVAL, 0) == 99


def test_options_read_returns_default(hass):
    flow = _make_options(hass, options={}, data={})
    assert flow._read(CONF_SCAN_INTERVAL, 42) == 42


def test_options_build_schema_with_api_key_default(hass):
    flow = _make_options(hass)
    schema = flow._build_schema(api_key_default="explicit")
    assert schema is not None


