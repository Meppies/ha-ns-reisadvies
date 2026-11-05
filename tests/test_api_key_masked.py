"""The NS API key is a secret: every form shows it masked (v2.19.2)."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import TextSelector

from custom_components.ns_reisadvies.config_flow import (
    NSReisadviesConfigFlow,
    NSReisadviesOptionsFlowHandler,
)
from custom_components.ns_reisadvies.const import CONF_API_KEY


def _key_field(result: dict) -> object:
    schema = result["data_schema"].schema
    return next(v for k, v in schema.items() if str(k) == CONF_API_KEY)


def _assert_masked(field: object) -> None:
    assert isinstance(field, TextSelector)
    assert field.config["type"] == "password"


async def test_user_step_masks_key(hass: HomeAssistant) -> None:
    flow = NSReisadviesConfigFlow()
    flow.hass = hass
    flow._async_current_entries = MagicMock(return_value=[])  # type: ignore[method-assign]
    _assert_masked(_key_field(await flow.async_step_user(user_input=None)))


async def test_reauth_step_masks_key(hass: HomeAssistant) -> None:
    flow = NSReisadviesConfigFlow()
    flow.hass = hass
    flow.context = {"source": "reauth"}  # type: ignore[typeddict-item]
    _assert_masked(_key_field(await flow.async_step_reauth_confirm(user_input=None)))


async def test_options_step_masks_stored_key(hass: HomeAssistant) -> None:
    entry = MagicMock()
    entry.options = {}
    entry.data = {CONF_API_KEY: "stored-secret"}
    flow = NSReisadviesOptionsFlowHandler(entry)
    flow.hass = hass
    flow.entry = entry
    result = await flow.async_step_init(user_input=None)
    _assert_masked(_key_field(result))
