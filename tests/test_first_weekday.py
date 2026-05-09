"""Tests for the v2.15.2 first_weekday hub option + day-picker rotation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.config_flow import (
    NSReisadviesOptionsFlowHandler,
    NSRouteSubentryFlowHandler,
)
from custom_components.ns_reisadvies.const import (
    CONF_API_KEY,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    CONF_FIRST_WEEKDAY,
    CONF_FROM_STATION,
    CONF_LIVE_MAP_REFRESH_SECONDS,
    CONF_LIVE_TRAIN_MAP,
    CONF_SCAN_INTERVAL,
    CONF_TO_STATION,
    DEFAULT_FIRST_WEEKDAY,
)


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
        CONF_FIRST_WEEKDAY: "6",  # Sunday
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
    # Schema dict's default for first_weekday → "0" (Monday).
    for key, _ in schema.schema.items():
        if str(key) == CONF_FIRST_WEEKDAY:
            assert key.default() == DEFAULT_FIRST_WEEKDAY
            return
    pytest.fail("first_weekday field not found in OptionsFlow schema")


# ---- Subentry day-picker is rotated by first_weekday ------------------------


class _Flow(NSRouteSubentryFlowHandler):
    _test_parent = None

    def _get_entry(self):
        return self._test_parent

    def _get_reconfigure_entry(self):
        if self._test_parent is None:
            raise RuntimeError("x")
        return self._test_parent

    def _get_reconfigure_subentry(self):
        raise RuntimeError("x")

    @property
    def _reconfigure_subentry_id(self):
        return "sid-test"


def _mk_subflow(parent_options=None):
    parent = MagicMock()
    parent.subentries = {}
    parent.options = parent_options or {}
    f = _Flow()
    f.hass = MagicMock()
    f._test_parent = parent
    f.async_create_entry = MagicMock(
        return_value={"type": FlowResultType.CREATE_ENTRY},
    )
    f.async_show_form = MagicMock(
        return_value={"type": FlowResultType.FORM, "step_id": "user", "errors": {}},
    )
    f.async_update_and_abort = MagicMock(
        return_value={"type": FlowResultType.ABORT},
    )
    return f


async def test_day_picker_default_starts_with_monday():
    """Without an explicit first_weekday option, the rotation starts at Mon."""
    f = _mk_subflow()
    await f.async_step_user(user_input=None)
    f.async_show_form.assert_called_once()
    # Schema is built; the values "0".."6" should appear in the order
    # Mon, Tue, …, Sun. We verify by inspecting the rendered schema.
    _, kwargs = f.async_show_form.call_args
    schema = kwargs["data_schema"]
    # Find the section's inner schema and the filter_days option order.
    found = False
    for key, val in schema.schema.items():
        # The "filters" section is wrapped — its options live underneath.
        if str(key) == "filters":
            inner = val.schema
            for inner_key, inner_val in inner.schema.items():
                if str(inner_key) == "filter_days":
                    config = inner_val.config
                    values = [opt["value"] for opt in config.options]
                    assert values == ["0", "1", "2", "3", "4", "5", "6"]
                    found = True
    assert found


async def test_day_picker_starts_with_sunday_when_configured():
    """First_weekday=6 → rotation Sun, Mon, Tue, …, Sat."""
    f = _mk_subflow(parent_options={CONF_FIRST_WEEKDAY: "6"})
    await f.async_step_user(user_input=None)
    _, kwargs = f.async_show_form.call_args
    schema = kwargs["data_schema"]
    for key, val in schema.schema.items():
        if str(key) == "filters":
            for inner_key, inner_val in val.schema.schema.items():
                if str(inner_key) == "filter_days":
                    values = [opt["value"] for opt in inner_val.config.options]
                    # Rotation starting at 6 (Sunday): 6, 0, 1, 2, 3, 4, 5
                    assert values == ["6", "0", "1", "2", "3", "4", "5"]


async def test_day_picker_invalid_first_weekday_falls_back_to_monday():
    """A non-numeric / unparseable first_weekday is treated as Monday."""
    f = _mk_subflow(parent_options={CONF_FIRST_WEEKDAY: "garbage"})
    await f.async_step_user(user_input=None)
    _, kwargs = f.async_show_form.call_args
    schema = kwargs["data_schema"]
    for key, val in schema.schema.items():
        if str(key) == "filters":
            for inner_key, inner_val in val.schema.schema.items():
                if str(inner_key) == "filter_days":
                    values = [opt["value"] for opt in inner_val.config.options]
                    assert values == ["0", "1", "2", "3", "4", "5", "6"]


async def test_day_picker_handles_options_attribute_error():
    """parent.options raising attribute error → falls back to default."""
    parent = MagicMock()
    parent.subentries = {}
    # Make options access raise.
    type(parent).options = property(lambda _self: (_ for _ in ()).throw(RuntimeError("nope")))
    f = _Flow()
    f.hass = MagicMock()
    f._test_parent = parent
    f.async_show_form = MagicMock(
        return_value={"type": FlowResultType.FORM, "step_id": "user", "errors": {}},
    )
    await f.async_step_user(user_input=None)
    _, kwargs = f.async_show_form.call_args
    schema = kwargs["data_schema"]
    for key, val in schema.schema.items():
        if str(key) == "filters":
            for inner_key, inner_val in val.schema.schema.items():
                if str(inner_key) == "filter_days":
                    values = [opt["value"] for opt in inner_val.config.options]
                    assert values[0] == "0"  # Monday — default fallback
