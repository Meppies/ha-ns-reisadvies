"""SubentryFlow body coverage by mocking flow-result methods."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.config_flow import NSRouteSubentryFlowHandler
from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION, CONF_TO_STATION, SUBENTRY_TYPE_ROUTE,
)


class _Flow(NSRouteSubentryFlowHandler):
    _test_parent = None
    _test_subentry = None

    def _get_entry(self):
        return self._test_parent

    def _get_reconfigure_entry(self):
        if self._test_parent is None:
            raise RuntimeError("x")
        return self._test_parent

    def _get_reconfigure_subentry(self):
        if self._test_subentry is None:
            raise RuntimeError("x")
        return self._test_subentry

    @property
    def _reconfigure_subentry_id(self):
        return "sid-test"


def _mk(parent=None, sub=None):
    f = _Flow()
    f.hass = MagicMock()
    f._test_parent = parent
    f._test_subentry = sub
    f.async_create_entry = MagicMock(return_value={"type": FlowResultType.CREATE_ENTRY})
    f.async_show_form = MagicMock(return_value={"type": FlowResultType.FORM, "step_id": "x", "errors": {}})
    f.async_update_and_abort = MagicMock(return_value={"type": FlowResultType.ABORT})
    return f


async def test_user_no_input_calls_show_form():
    f = _mk()
    await f.async_step_user(user_input=None)
    f.async_show_form.assert_called_once()


async def test_user_unknown_station_shows_form_with_error():
    f = _mk()
    await f.async_step_user(user_input={CONF_FROM_STATION: "Atlantis", CONF_TO_STATION: "Hilversum"})
    f.async_show_form.assert_called_once()
    args, kwargs = f.async_show_form.call_args
    assert kwargs["errors"][CONF_FROM_STATION] == "unknown_station"


async def test_user_creates_entry_on_valid():
    f = _mk()
    await f.async_step_user(user_input={CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"})
    f.async_create_entry.assert_called_once()
    _, kwargs = f.async_create_entry.call_args
    assert kwargs["data"][CONF_FROM_STATION] == "Hilversum"
    assert kwargs["unique_id"] == "hilversum_duivendrecht"


async def test_user_duplicate_route_via_existing_subentry():
    parent = MagicMock()
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    parent.subentries = {"sid": sub}
    f = _mk(parent=parent)
    await f.async_step_user(user_input={CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"})
    f.async_show_form.assert_called_once()
    _, kwargs = f.async_show_form.call_args
    assert kwargs["errors"]["base"] == "duplicate_route"


async def test_user_skips_non_route_subentries():
    parent = MagicMock()
    sub = MagicMock(); sub.subentry_type = "OTHER"
    parent.subentries = {"sid": sub}
    f = _mk(parent=parent)
    await f.async_step_user(user_input={CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"})
    # Not duplicate — created.
    f.async_create_entry.assert_called_once()


async def test_user_skips_subentry_without_stations():
    parent = MagicMock()
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE; sub.data = {}
    parent.subentries = {"sid": sub}
    f = _mk(parent=parent)
    await f.async_step_user(user_input={CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"})
    f.async_create_entry.assert_called_once()


async def test_reconfigure_no_input_shows_form():
    parent = MagicMock(); parent.subentries = {}
    sub = MagicMock(); sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    f = _mk(parent=parent, sub=sub)
    await f.async_step_reconfigure(user_input=None)
    f.async_show_form.assert_called_once()
    _, kwargs = f.async_show_form.call_args
    assert kwargs["step_id"] == "reconfigure"


async def test_reconfigure_updates_and_aborts():
    parent = MagicMock(); parent.subentries = {}
    sub = MagicMock(); sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    f = _mk(parent=parent, sub=sub)
    await f.async_step_reconfigure(user_input={CONF_FROM_STATION: "Amsterdam Centraal", CONF_TO_STATION: "Utrecht Centraal"})
    f.async_update_and_abort.assert_called_once()


async def test_reconfigure_skips_self_in_duplicate_check():
    parent = MagicMock()
    self_sub = MagicMock(); self_sub.subentry_type = SUBENTRY_TYPE_ROUTE
    self_sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    parent.subentries = {"sid-test": self_sub}
    f = _mk(parent=parent, sub=self_sub)
    # Reconfiguring to same route should NOT trigger duplicate (self is skipped).
    await f.async_step_reconfigure(user_input={CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"})
    f.async_update_and_abort.assert_called_once()


async def test_reconfigure_subentry_data_unreadable():
    parent = MagicMock(); parent.subentries = {}
    f = _mk(parent=parent, sub=None)  # _get_reconfigure_subentry will raise
    await f.async_step_reconfigure(user_input=None)
    f.async_show_form.assert_called_once()
