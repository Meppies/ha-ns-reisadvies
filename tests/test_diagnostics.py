"""Tests for the diagnostics dump."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.ns_reisadvies.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)
from custom_components.ns_reisadvies.types import NSRuntimeData


def _make_entry(*, options: dict, data: dict, runtime: NSRuntimeData | None):
    entry = MagicMock()
    entry.version = 3
    entry.title = "NS Reisadvies"
    entry.data = data
    entry.options = options
    entry.subentries = {}
    entry.runtime_data = runtime
    return entry


async def test_diagnostics_redacts_api_key(hass: HomeAssistant) -> None:
    entry = _make_entry(
        data={"api_key": "secret-key-1234"},
        options={"scan_interval_minuten": 5},
        runtime=NSRuntimeData(),
    )
    dump = await async_get_config_entry_diagnostics(hass, entry)
    assert dump["entry"]["data"]["api_key"] != "secret-key-1234"


async def test_diagnostics_redacts_ctx_recon_inside_first_trip(
    hass: HomeAssistant,
) -> None:
    coord = MagicMock()
    coord.from_station = "Hilversum"
    coord.to_station = "Duivendrecht"
    coord.fav_hours = 6
    coord.fetch_composition = False
    coord.tracked_trips = {}
    coord.last_update_success = True
    coord.last_exception = None
    coord.data = [{"ctxRecon": "VWY...secret", "legs": []}]
    runtime = NSRuntimeData(coordinators={"sub1": coord})
    entry = _make_entry(
        data={"api_key": "k"},
        options={},
        runtime=runtime,
    )
    dump = await async_get_config_entry_diagnostics(hass, entry)
    first = dump["coordinators"]["sub1"]["first_trip"]
    assert first["ctxRecon"] != "VWY...secret"


async def test_diagnostics_handles_missing_runtime_data(
    hass: HomeAssistant,
) -> None:
    """An entry that hasn't finished loading yet still produces a usable dump."""
    entry = _make_entry(data={"api_key": "k"}, options={}, runtime=None)
    dump = await async_get_config_entry_diagnostics(hass, entry)
    # Should not crash; runtime block is filled with None.
    assert dump["runtime"]["live_train_map_enabled"] is None
    assert dump["coordinators"] == {}


async def test_diagnostics_lists_route_subentries(hass: HomeAssistant) -> None:
    sub = MagicMock()
    sub.subentry_type = "route"
    sub.title = "Hilversum -> Duivendrecht"
    sub.unique_id = "hilversum_duivendrecht"
    sub.data = {"act_station": "Hilversum", "arr_station": "Duivendrecht"}

    entry = _make_entry(data={"api_key": "k"}, options={}, runtime=NSRuntimeData())
    entry.subentries = {"sub_id_xyz": sub}

    dump = await async_get_config_entry_diagnostics(hass, entry)
    assert "sub_id_xyz" in dump["entry"]["subentries"]
    assert dump["entry"]["subentries"]["sub_id_xyz"]["title"] == \
        "Hilversum -> Duivendrecht"


def test_to_redact_covers_known_secret_fields() -> None:
    assert "api_key" in TO_REDACT
    assert "ctxRecon" in TO_REDACT
