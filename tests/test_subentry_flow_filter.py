"""Tests for the v2.14.0 filter fields in the route subentry flow."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.config_flow import NSRouteSubentryFlowHandler
from custom_components.ns_reisadvies.const import (
    CONF_FILTER_DATE,
    CONF_FILTER_DAYS,
    CONF_FILTER_TIME,
    CONF_FILTER_WINDOW_MINUTES,
    CONF_FROM_STATION,
    CONF_TO_STATION,
)


class _Flow(NSRouteSubentryFlowHandler):
    """Subclass that bypasses the flow-runtime methods we don't have."""

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
    f.async_create_entry = MagicMock(
        return_value={"type": FlowResultType.CREATE_ENTRY},
    )
    f.async_show_form = MagicMock(
        return_value={"type": FlowResultType.FORM, "step_id": "x", "errors": {}},
    )
    f.async_update_and_abort = MagicMock(
        return_value={"type": FlowResultType.ABORT},
    )
    return f


async def test_user_step_with_filter_fields_persists_them():
    """v2.14.2: filter fields arrive nested under "filters" section."""
    f = _mk()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        "filters": {
            CONF_FILTER_DAYS: ["0", "2", "4"],
            CONF_FILTER_TIME: "08:00",
            CONF_FILTER_WINDOW_MINUTES: 60,
            CONF_FILTER_DATE: "2026-12-24",
        },
    })
    f.async_create_entry.assert_called_once()
    _, kwargs = f.async_create_entry.call_args
    data = kwargs["data"]
    # Subentry data stays FLAT (backwards compat with v2.13.x routes).
    assert data[CONF_FILTER_DAYS] == [0, 2, 4]
    assert data[CONF_FILTER_TIME] == "08:00"
    assert data[CONF_FILTER_WINDOW_MINUTES] == 60
    assert data[CONF_FILTER_DATE] == "2026-12-24"


async def test_user_step_filter_fields_omitted_when_empty():
    """Empty section values are not stored — keeps subentry tidy."""
    f = _mk()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        "filters": {
            CONF_FILTER_DAYS: [],
            CONF_FILTER_TIME: "",
            CONF_FILTER_WINDOW_MINUTES: 0,
            CONF_FILTER_DATE: "",
        },
    })
    f.async_create_entry.assert_called_once()
    _, kwargs = f.async_create_entry.call_args
    data = kwargs["data"]
    # Only stations stored — filter keys absent.
    assert CONF_FILTER_DAYS not in data
    assert CONF_FILTER_TIME not in data
    assert CONF_FILTER_WINDOW_MINUTES not in data
    assert CONF_FILTER_DATE not in data


async def test_reconfigure_prefills_existing_filter_values():
    parent = MagicMock()
    parent.subentries = {}
    sub = MagicMock()
    sub.data = {
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_FILTER_DAYS: [0, 4],
        CONF_FILTER_TIME: "08:00",
        CONF_FILTER_WINDOW_MINUTES: 30,
        CONF_FILTER_DATE: "2026-12-24",
    }
    f = _mk(parent=parent, sub=sub)
    await f.async_step_reconfigure(user_input=None)
    f.async_show_form.assert_called_once()
    # The schema is built; the test verifies no crash and correct step.
    _, kwargs = f.async_show_form.call_args
    assert kwargs["step_id"] == "reconfigure"


async def test_user_step_filter_window_int_coerced():
    """A string-like number from the slider is coerced to int (nested)."""
    f = _mk()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        "filters": {
            CONF_FILTER_WINDOW_MINUTES: "45",  # NumberSelector may yield str
        },
    })
    f.async_create_entry.assert_called_once()
    _, kwargs = f.async_create_entry.call_args
    assert kwargs["data"][CONF_FILTER_WINDOW_MINUTES] == 45


async def test_user_step_flat_filter_input_still_works():
    """Hybrid path: flat user_input (no "filters" section key) still parses
    — covers the backwards-compat fallback in _show_form."""
    f = _mk()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_FILTER_TIME: "09:30",
        CONF_FILTER_WINDOW_MINUTES: 15,
    })
    f.async_create_entry.assert_called_once()
    _, kwargs = f.async_create_entry.call_args
    data = kwargs["data"]
    assert data[CONF_FILTER_TIME] == "09:30"
    assert data[CONF_FILTER_WINDOW_MINUTES] == 15
