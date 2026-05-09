"""Tests for the v2.15.2 first_weekday hub option + day-picker rotation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.config_flow import (
    NSReisadviesOptionsFlowHandler,
    _read_first_weekday,
    _weekday_options,
)
from custom_components.ns_reisadvies.const import (
    CONF_API_KEY,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    CONF_FIRST_WEEKDAY,
    CONF_LIVE_MAP_REFRESH_SECONDS,
    CONF_LIVE_TRAIN_MAP,
    CONF_SCAN_INTERVAL,
    DEFAULT_FIRST_WEEKDAY,
)


# ---- _weekday_options pure helper ------------------------------------------


def test_weekday_options_default_starts_monday():
    """Default ('0') keeps the natural 0-6 order."""
    opts = _weekday_options(DEFAULT_FIRST_WEEKDAY)
    values = [opt["value"] for opt in opts]
    assert values == ["0", "1", "2", "3", "4", "5", "6"]


def test_weekday_options_sunday_rotates_to_top():
    """first_weekday=6 → Sunday first, then Mon..Sat."""
    opts = _weekday_options("6")
    values = [opt["value"] for opt in opts]
    assert values == ["6", "0", "1", "2", "3", "4", "5"]


def test_weekday_options_int_input_works():
    """Accepts int as well as string."""
    opts = _weekday_options(2)
    values = [opt["value"] for opt in opts]
    assert values == ["2", "3", "4", "5", "6", "0", "1"]


def test_weekday_options_garbage_string_falls_back_to_monday():
    opts = _weekday_options("not-a-number")
    values = [opt["value"] for opt in opts]
    assert values == ["0", "1", "2", "3", "4", "5", "6"]


def test_weekday_options_none_falls_back_to_monday():
    opts = _weekday_options(None)
    values = [opt["value"] for opt in opts]
    assert values == ["0", "1", "2", "3", "4", "5", "6"]


def test_weekday_options_out_of_range_clamps_to_monday():
    """Values < 0 or > 6 are silently clamped — Monday wins."""
    assert [o["value"] for o in _weekday_options("9")][0] == "0"
    assert [o["value"] for o in _weekday_options("-3")][0] == "0"


# ---- _read_first_weekday helper --------------------------------------------


def test_read_first_weekday_none_parent():
    assert _read_first_weekday(None) == DEFAULT_FIRST_WEEKDAY


def test_read_first_weekday_default_when_missing():
    parent = MagicMock()
    parent.options = {}
    assert _read_first_weekday(parent) == DEFAULT_FIRST_WEEKDAY


def test_read_first_weekday_returns_stored_value():
    parent = MagicMock()
    parent.options = {CONF_FIRST_WEEKDAY: "6"}
    assert _read_first_weekday(parent) == "6"


def test_read_first_weekday_handles_options_attribute_error():
    """parent.options blowing up at access time falls back to default."""
    parent = MagicMock()
    type(parent).options = property(
        lambda _self: (_ for _ in ()).throw(RuntimeError("nope"))
    )
    assert _read_first_weekday(parent) == DEFAULT_FIRST_WEEKDAY


# ---- OptionsFlow stores first_weekday --------------------------------------


def _make_options(hass, options=None, data=None) -> NSReisadviesOptionsFlowHandler:
    entry = MagicMock()
    entry.options = options if options is not None else {}
    entry.data = data if data is not None else {CONF_API_KEY: "k"}
    flow = NSReisadviesOptionsFlowHandler(entry)
    flow.hass = hass
    flow.entry = entry
    return flow


async def test_options_persists_first_weekday(hass):
    """OptionsFlow saves a non-default first_weekday into entry.options."""
    flow = _make_options(hass)
    fake_hass = MagicMock()
    fake_hass.config_entries.async_update_entry = MagicMock()
    flow.hass = fake_hass
    user_input = {
        CONF_API_KEY: "k",
        CONF_SCAN_INTERVAL: 5,
        CONF_FAV_HOURS: 6,
        CONF_FETCH_COMPOSITION: False,
        CONF_LIVE_TRAIN_MAP: False,
        CONF_LIVE_MAP_REFRESH_SECONDS: 10,
        CONF_FIRST_WEEKDAY: "6",
    }
    with patch(
        "custom_components.ns_reisadvies.coordinator.async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result = await flow.async_step_init(user_input=user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    _, kwargs = fake_hass.config_entries.async_update_entry.call_args
    assert kwargs["options"][CONF_FIRST_WEEKDAY] == "6"


async def test_options_default_first_weekday_when_not_supplied(hass):
    """When the user doesn't change the field, the default Monday survives."""
    flow = _make_options(hass)
    schema = flow._build_schema()
    for key, _ in schema.schema.items():
        if str(key) == CONF_FIRST_WEEKDAY:
            assert key.default() == DEFAULT_FIRST_WEEKDAY
            return
    pytest.fail("first_weekday field not found in OptionsFlow schema")
