"""Cover async_migrate_entry v1->v2 and _recover_subentries_from_storage."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ns_reisadvies import (
    _recover_subentries_from_storage, async_migrate_entry,
)
from custom_components.ns_reisadvies.const import (
    CONF_API_KEY, CONF_FROM_STATION, CONF_TO_STATION, DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)


async def test_migrate_entry_already_current_version_returns_true():
    hass = MagicMock()
    entry = MagicMock(); entry.version = 3
    assert await async_migrate_entry(hass, entry) is True


async def test_migrate_v2_to_v3_moves_options(hass):
    fake_hass = MagicMock()
    fake_hass.config_entries.async_update_entry = MagicMock()
    entry = MagicMock()
    entry.version = 2
    entry.entry_id = "e1"
    entry.data = {CONF_API_KEY: "k", "scan_interval_minuten": 7, "fav_hours": 4}
    entry.options = {}
    assert await async_migrate_entry(fake_hass, entry) is True
    fake_hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = fake_hass.config_entries.async_update_entry.call_args
    assert kwargs["version"] == 3
    # API key stays in data, but settings keys moved to options.
    assert kwargs["data"][CONF_API_KEY] == "k"
    assert "scan_interval_minuten" in kwargs["options"]


async def test_migrate_v1_no_legacy_returns_true():
    fake_hass = MagicMock()
    fake_hass.config_entries.async_entries.return_value = []
    entry = MagicMock(); entry.version = 1
    assert await async_migrate_entry(fake_hass, entry) is True


async def test_migrate_v1_non_primary_returns_true():
    fake_hass = MagicMock()
    primary = MagicMock(); primary.version = 1; primary.entry_id = "a"
    other = MagicMock(); other.version = 1; other.entry_id = "b"
    fake_hass.config_entries.async_entries.return_value = [primary, other]
    # Sort by entry_id puts primary=a first; called for entry=b → not primary.
    other.version = 1
    other.entry_id = "b"
    assert await async_migrate_entry(fake_hass, other) is True


async def test_migrate_v1_primary_builds_hub_with_subentries():
    fake_hass = MagicMock()
    primary = MagicMock()
    primary.version = 1; primary.entry_id = "a"
    primary.data = {CONF_API_KEY: "k", CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    primary.options = {}
    other = MagicMock()
    other.version = 1; other.entry_id = "b"
    other.data = {CONF_FROM_STATION: "Amsterdam Centraal", CONF_TO_STATION: "Utrecht Centraal"}
    other.options = {}
    fake_hass.config_entries.async_entries.return_value = [primary, other]
    fake_hass.config_entries.async_update_entry = MagicMock()
    fake_hass.config_entries.async_add_subentry = MagicMock()
    fake_hass.config_entries.async_remove = AsyncMock()
    fake_hass.async_create_task = MagicMock()
    with patch("custom_components.ns_reisadvies.er.async_get") as mock_er:
        ent_reg = MagicMock()
        mock_er.return_value = ent_reg
        with patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[]):
            assert await async_migrate_entry(fake_hass, primary) is True
    fake_hass.config_entries.async_update_entry.assert_called_once()
    assert fake_hass.config_entries.async_add_subentry.call_count == 2
    fake_hass.async_create_task.assert_called_once()


async def test_migrate_v1_skips_legacy_without_stations():
    fake_hass = MagicMock()
    primary = MagicMock()
    primary.version = 1; primary.entry_id = "a"
    primary.data = {CONF_API_KEY: "k"}  # No stations -> skipped
    primary.options = {}
    fake_hass.config_entries.async_entries.return_value = [primary]
    fake_hass.config_entries.async_update_entry = MagicMock()
    fake_hass.config_entries.async_add_subentry = MagicMock()
    with patch("custom_components.ns_reisadvies.er.async_get") as mock_er:
        mock_er.return_value = MagicMock()
        with patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[]):
            assert await async_migrate_entry(fake_hass, primary) is True
    # No subentries should have been added.
    fake_hass.config_entries.async_add_subentry.assert_not_called()


# ---- _recover_subentries_from_storage --------------------------------------


async def test_recover_skips_when_subentries_exist():
    fake_hass = MagicMock()
    entry = MagicMock(); entry.subentries = {"sub1": MagicMock()}
    await _recover_subentries_from_storage(fake_hass, entry)
    fake_hass.config.path.assert_not_called()


async def test_recover_silent_on_listdir_error():
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = "/storage"
    fake_hass.async_add_executor_job = AsyncMock(side_effect=OSError("boom"))
    entry = MagicMock(); entry.subentries = {}
    await _recover_subentries_from_storage(fake_hass, entry)  # should not raise


async def test_recover_no_matching_files_no_op():
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = "/storage"
    fake_hass.async_add_executor_job = AsyncMock(return_value=["core.entity_registry", "unrelated"])
    entry = MagicMock(); entry.subentries = {}
    await _recover_subentries_from_storage(fake_hass, entry)
    fake_hass.config_entries.async_add_subentry.assert_not_called()


async def test_recover_rebuilds_subentry_for_known_route():
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = "/storage"
    fake_hass.async_add_executor_job = AsyncMock(return_value=[
        "ns_reisadvies_tracked_trips_Hilversum_Duivendrecht",
    ])
    fake_hass.config_entries.async_add_subentry = MagicMock()
    entry = MagicMock(); entry.subentries = {}
    await _recover_subentries_from_storage(fake_hass, entry)
    fake_hass.config_entries.async_add_subentry.assert_called_once()


async def test_recover_swallows_add_subentry_errors():
    fake_hass = MagicMock()
    fake_hass.config.path.return_value = "/storage"
    fake_hass.async_add_executor_job = AsyncMock(return_value=[
        "ns_reisadvies_tracked_trips_Hilversum_Duivendrecht",
    ])
    fake_hass.config_entries.async_add_subentry = MagicMock(side_effect=ValueError("boom"))
    entry = MagicMock(); entry.subentries = {}
    await _recover_subentries_from_storage(fake_hass, entry)  # should not raise


async def test_migrate_v1_updates_entity_registry_for_legacy_entries():
    """Cover entity_registry update branch (lines 204-211)."""
    fake_hass = MagicMock()
    primary = MagicMock()
    primary.version = 1; primary.entry_id = "a"
    primary.data = {CONF_API_KEY: "k", CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    primary.options = {}
    fake_hass.config_entries.async_entries.return_value = [primary]
    fake_hass.config_entries.async_update_entry = MagicMock()
    fake_hass.config_entries.async_add_subentry = MagicMock()
    fake_hass.async_create_task = MagicMock()
    ent = MagicMock(); ent.entity_id = "sensor.x"
    ent_reg = MagicMock()
    ent_reg.async_update_entity = MagicMock()
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[ent]):
        assert await async_migrate_entry(fake_hass, primary) is True
    ent_reg.async_update_entity.assert_called_once()


async def test_migrate_v1_swallows_entity_update_error():
    """Entity update raising -> warning logged, migration continues (lines 210-211)."""
    fake_hass = MagicMock()
    primary = MagicMock()
    primary.version = 1; primary.entry_id = "a"
    primary.data = {CONF_API_KEY: "k", CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    primary.options = {}
    fake_hass.config_entries.async_entries.return_value = [primary]
    fake_hass.config_entries.async_update_entry = MagicMock()
    fake_hass.config_entries.async_add_subentry = MagicMock()
    fake_hass.async_create_task = MagicMock()
    ent = MagicMock(); ent.entity_id = "sensor.x"
    ent_reg = MagicMock()
    ent_reg.async_update_entity = MagicMock(side_effect=ValueError("boom"))
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=ent_reg), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[ent]):
        assert await async_migrate_entry(fake_hass, primary) is True


async def test_migrate_v1_swallows_add_subentry_error():
    """async_add_subentry raises -> warning logged (lines 228-229)."""
    fake_hass = MagicMock()
    primary = MagicMock()
    primary.version = 1; primary.entry_id = "a"
    primary.data = {CONF_API_KEY: "k", CONF_FROM_STATION: "Hilversum", CONF_TO_STATION: "Duivendrecht"}
    primary.options = {}
    fake_hass.config_entries.async_entries.return_value = [primary]
    fake_hass.config_entries.async_update_entry = MagicMock()
    fake_hass.config_entries.async_add_subentry = MagicMock(side_effect=ValueError("boom"))
    fake_hass.async_create_task = MagicMock()
    with patch("custom_components.ns_reisadvies.er.async_get", return_value=MagicMock()), \
         patch("custom_components.ns_reisadvies.er.async_entries_for_config_entry", return_value=[]):
        assert await async_migrate_entry(fake_hass, primary) is True
