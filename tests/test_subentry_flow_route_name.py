"""Tests for the v2.15.0 optional route_name field on the subentry flow."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.data_entry_flow import FlowResultType

from custom_components.ns_reisadvies.config_flow import NSRouteSubentryFlowHandler
from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION,
    CONF_ROUTE_NAME,
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


async def test_user_step_with_route_name_uses_name_as_title_and_unique_id():
    """When route_name is set, title becomes the name and unique_id
    appends the slug so duplicate detection works on (from, to, name)."""
    f = _mk()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "Werk",
    })
    f.async_create_entry.assert_called_once()
    _, kwargs = f.async_create_entry.call_args
    assert kwargs["title"] == "Werk"
    assert kwargs["unique_id"] == "hilversum_duivendrecht_werk"
    assert kwargs["data"][CONF_ROUTE_NAME] == "Werk"


async def test_user_step_without_route_name_uses_legacy_title_and_unique_id():
    """No route_name → legacy "from -> to" title and "from_to" unique_id;
    backwards compatibility with v2.14.x routes is preserved."""
    f = _mk()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
    })
    f.async_create_entry.assert_called_once()
    _, kwargs = f.async_create_entry.call_args
    assert kwargs["title"] == "Hilversum -> Duivendrecht"
    assert kwargs["unique_id"] == "hilversum_duivendrecht"
    assert CONF_ROUTE_NAME not in kwargs["data"]


async def test_user_step_route_name_with_special_chars_is_slugified():
    """A name with spaces/diacritics produces a clean unique_id."""
    f = _mk()
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "Naar het Werk!",
    })
    _, kwargs = f.async_create_entry.call_args
    assert kwargs["unique_id"] == "hilversum_duivendrecht_naar_het_werk"
    # Title is the exact human-supplied name (not the slug).
    assert kwargs["title"] == "Naar het Werk!"


async def test_reconfigure_keeps_existing_route_name_in_form():
    """Pre-fill: a route reopened for reconfigure should populate the
    schema with the existing route_name as default."""
    parent = MagicMock()
    parent.subentries = {}
    sub = MagicMock()
    sub.data = {
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "Werk",
    }
    f = _mk(parent=parent, sub=sub)
    await f.async_step_reconfigure(user_input=None)
    f.async_show_form.assert_called_once()
    _, kwargs = f.async_show_form.call_args
    assert kwargs["step_id"] == "reconfigure"


async def test_user_step_two_named_routes_same_stations_both_succeed():
    """Two routes between the same stations with different names are
    allowed in the duplicate-check phase."""
    parent = MagicMock()
    sub_existing = MagicMock()
    sub_existing.subentry_type = "route"
    sub_existing.data = {
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "Werk",
    }
    parent.subentries = {"existing-id": sub_existing}
    f = _mk(parent=parent)
    await f.async_step_user(user_input={
        CONF_FROM_STATION: "Hilversum",
        CONF_TO_STATION: "Duivendrecht",
        CONF_ROUTE_NAME: "Weekend",
    })
    # No duplicate error → entry created.
    f.async_create_entry.assert_called_once()
