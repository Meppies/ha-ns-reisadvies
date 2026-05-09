"""Final coverage push: _backfill, rail_cache edge cases, register edge cases, async_unload, update_listener."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ns_reisadvies import (
    _async_register_card_resource, _async_refresh_rail_cache,
    _async_update_listener, _backfill_entity_subentries,
    async_unload_entry,
)
from custom_components.ns_reisadvies.const import (
    CONF_FROM_STATION, CONF_TO_STATION, SUBENTRY_TYPE_ROUTE,
)


# ---- _backfill_entity_subentries -------------------------------------------


def test_backfill_links_entity_by_unique_id():
    fake_hass = MagicMock()
    sub = MagicMock()
    sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock()
    entry.subentries = {"sid1": sub}
    entry.entry_id = "e1"
    ent_reg = MagicMock()
    ent_reg.async_update_entity = MagicMock()
    ent = MagicMock()
    ent.config_subentry_id = None
    ent.unique_id = "hilversum_duivendrecht"
    ent.entity_id = "sensor.x"
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[ent]):
        _backfill_entity_subentries(fake_hass, entry)
    ent_reg.async_update_entity.assert_called_once_with("sensor.x", config_subentry_id="sid1")


def test_backfill_skips_already_linked_entity():
    fake_hass = MagicMock()
    sub = MagicMock()
    sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock(); entry.subentries = {"sid1": sub}; entry.entry_id = "e1"
    ent_reg = MagicMock()
    ent = MagicMock()
    ent.config_subentry_id = "already-linked"
    ent.unique_id = "hilversum_duivendrecht"
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[ent]):
        _backfill_entity_subentries(fake_hass, entry)
    ent_reg.async_update_entity.assert_not_called()


def test_backfill_skips_entity_with_no_matching_subentry():
    fake_hass = MagicMock()
    entry = MagicMock(); entry.subentries = {}; entry.entry_id = "e1"
    ent_reg = MagicMock()
    ent = MagicMock(); ent.config_subentry_id = None; ent.unique_id = "unknown"
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[ent]):
        _backfill_entity_subentries(fake_hass, entry)
    ent_reg.async_update_entity.assert_not_called()


def test_backfill_swallows_update_error():
    fake_hass = MagicMock()
    sub = MagicMock()
    sub.subentry_type = SUBENTRY_TYPE_ROUTE
    sub.data = {CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    entry = MagicMock(); entry.subentries = {"sid1": sub}; entry.entry_id = "e1"
    ent_reg = MagicMock()
    ent_reg.async_update_entity = MagicMock(side_effect=ValueError("boom"))
    ent = MagicMock(); ent.config_subentry_id = None; ent.unique_id = "hilversum_duivendrecht"; ent.entity_id = "sensor.x"
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[ent]):
        _backfill_entity_subentries(fake_hass, entry)  # should not raise


def test_backfill_skips_non_route_subentry():
    fake_hass = MagicMock()
    sub = MagicMock(); sub.subentry_type = "OTHER"
    entry = MagicMock(); entry.subentries = {"sid1": sub}; entry.entry_id = "e1"
    ent_reg = MagicMock()
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[]):
        _backfill_entity_subentries(fake_hass, entry)


def test_backfill_skips_subentry_without_stations():
    fake_hass = MagicMock()
    sub = MagicMock(); sub.subentry_type = SUBENTRY_TYPE_ROUTE; sub.data = {}
    entry = MagicMock(); entry.subentries = {"sid1": sub}; entry.entry_id = "e1"
    ent_reg = MagicMock()
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[]):
        _backfill_entity_subentries(fake_hass, entry)


# ---- _async_refresh_rail_cache edge cases ----------------------------------




async def test_rail_cache_logs_on_write_error(tmp_path):
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = str(tmp_path / "www")
    fake_hass.async_add_executor_job = AsyncMock(side_effect=OSError("disk full"))
    coord = MagicMock()
    coord.async_fetch_full_rail_network = AsyncMock(return_value={"type": "FeatureCollection", "features": [{}]})
    await _async_refresh_rail_cache(fake_hass, coord, force=True)  # should not raise


# ---- _async_register_card_resource edge cases ------------------------------


async def test_register_card_swallows_add_extra_js_error():
    fake_hass = MagicMock()
    fake_hass.data = MagicMock()
    fake_hass.data.get = MagicMock(return_value=None)
    with patch("custom_components.ns_reisadvies.add_extra_js_url", side_effect=RuntimeError("x")):
        await _async_register_card_resource(fake_hass, "1.0")  # should not raise


async def test_register_card_lov_data_dict_style():
    resources = MagicMock()
    resources.loaded = True
    resources.async_items = MagicMock(return_value=[])
    resources.async_create_item = AsyncMock()
    lov_data = {"resources": resources}
    fake_hass = MagicMock(); fake_hass.data = MagicMock()
    fake_hass.data.get = MagicMock(return_value=lov_data)
    with patch("custom_components.ns_reisadvies.add_extra_js_url"):
        await _async_register_card_resource(fake_hass, "1.0")
    resources.async_create_item.assert_called_once()


async def test_register_card_resources_none_returns_early():
    lov_data = MagicMock(); lov_data.resources = None
    fake_hass = MagicMock(); fake_hass.data = MagicMock()
    fake_hass.data.get = MagicMock(return_value=lov_data)
    with patch("custom_components.ns_reisadvies.add_extra_js_url"):
        await _async_register_card_resource(fake_hass, "1.0")  # no-op


async def test_register_card_swallows_lovelace_exception():
    fake_hass = MagicMock(); fake_hass.data = MagicMock()
    fake_hass.data.get = MagicMock(side_effect=RuntimeError("boom"))
    with patch("custom_components.ns_reisadvies.add_extra_js_url"):
        await _async_register_card_resource(fake_hass, "1.0")  # should not raise


# ---- async_unload_entry + _async_update_listener ---------------------------


async def test_async_unload_entry_forwards_to_platform():
    fake_hass = MagicMock()
    fake_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock()
    result = await async_unload_entry(fake_hass, entry)
    assert result is True
    fake_hass.config_entries.async_unload_platforms.assert_called_once()


async def test_async_update_listener_reloads_entry():
    fake_hass = MagicMock()
    fake_hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock(); entry.entry_id = "e1"
    await _async_update_listener(fake_hass, entry)
    fake_hass.config_entries.async_reload.assert_called_once_with("e1")
