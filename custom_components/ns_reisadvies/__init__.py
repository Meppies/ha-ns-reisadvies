"""NS Reisadvies integration.

v2 architecture: ONE hub config entry holds the integration-wide
options (api_key, scan interval, favourite retention, fetch
composition). Each route lives as a subentry under the hub
(from_station / to_station). Per-route coordinators are managed
in async_setup_entry below.

Legacy v1 installs (one ConfigEntry per route) are migrated to
this hub+subentries layout in async_migrate_entry. The migration
preserves sensor entity_ids by rewriting unique_id mappings in
the entity registry.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components import lovelace
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import (
    DOMAIN,
    CONFIG_ENTRY_VERSION,
    SUBENTRY_TYPE_ROUTE,
    CONF_API_KEY,
    CONF_FROM_STATION,
    CONF_TO_STATION,
    CONF_SCAN_INTERVAL,
    CONF_FAV_HOURS,
    CONF_FETCH_COMPOSITION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
    DEFAULT_FETCH_COMPOSITION,
)
from .coordinator import NSUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CARD_URL = "/ns_reisadvies/ns-reisadvies-card.js"


# ---------------------------------------------------------------------------
# Migration: v1 multi-entry → v2 single hub + subentries.
# ---------------------------------------------------------------------------


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Lift legacy flat entries into the hub+subentries layout."""
    if entry.version >= CONFIG_ENTRY_VERSION:
        return True

    _LOGGER.info("Migrating NS Reisadvies entry %s from v%s to v%s",
                 entry.entry_id, entry.version, CONFIG_ENTRY_VERSION)

    # Sort all v1 entries: oldest becomes the hub.
    legacy = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.version == 1
    ]
    legacy.sort(key=lambda e: e.entry_id)

    if not legacy:
        # No legacy entries — nothing to migrate. Returning True signals
        # success and HA stamps the new version automatically.
        return True

    primary = legacy[0]

    # Only the primary actually does the migration. For non-primary
    # legacy entries we just return True and let HA update the
    # version-marker; the primary will then remove them in its own
    # migrate_entry call.
    if entry.entry_id != primary.entry_id:
        return True

    # Build hub data from primary's options + data
    def _opt(e: ConfigEntry, key: str, default: Any) -> Any:
        if e.options and key in e.options:
            return e.options[key]
        if key in e.data:
            return e.data[key]
        return default

    hub_data = {
        CONF_API_KEY: _opt(primary, CONF_API_KEY, ""),
        CONF_SCAN_INTERVAL: int(_opt(primary, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        CONF_FAV_HOURS: int(_opt(primary, CONF_FAV_HOURS, DEFAULT_FAV_HOURS)),
        CONF_FETCH_COMPOSITION: bool(_opt(primary, CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION)),
    }

    # Build subentries from EVERY legacy entry, including primary
    subentries = []
    legacy_id_to_route: dict[str, tuple[str, str]] = {}
    for legacy_entry in legacy:
        from_st = legacy_entry.data.get(CONF_FROM_STATION)
        to_st = legacy_entry.data.get(CONF_TO_STATION)
        if not from_st or not to_st:
            continue
        unique_id = f"{from_st}_{to_st}".lower()
        subentries.append(
            ConfigSubentry(
                data={
                    CONF_FROM_STATION: from_st,
                    CONF_TO_STATION: to_st,
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=f"{from_st} -> {to_st}",
                unique_id=unique_id,
            )
        )
        legacy_id_to_route[legacy_entry.entry_id] = (from_st, to_st)

    # Update the entity registry: old sensor unique_id was the legacy
    # entry's entry_id. Map each to the new deterministic id so that
    # sensor.ns_<from>_<to> entity_ids stay the same.
    ent_reg = er.async_get(hass)
    for legacy_entry in legacy:
        route = legacy_id_to_route.get(legacy_entry.entry_id)
        if not route:
            continue
        new_uid = f"{route[0]}_{route[1]}".lower()
        for entity in er.async_entries_for_config_entry(ent_reg, legacy_entry.entry_id):
            try:
                ent_reg.async_update_entity(
                    entity.entity_id,
                    new_unique_id=new_uid,
                    config_entry_id=primary.entry_id,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Could not move entity %s to hub: %s", entity.entity_id, err)

    # Update primary into the hub: new title, data, subentries.
    # The version is stamped automatically when this function returns
    # True — no need to pass version= here.
    hass.config_entries.async_update_entry(
        primary,
        title="NS Reisadvies",
        data=hub_data,
        options={},
    )

    # Add subentries one by one — async_update_entry doesn't take
    # subentries directly, but async_add_subentry does.
    for sub in subentries:
        try:
            hass.config_entries.async_add_subentry(primary, sub)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not add subentry %s: %s", sub.title, err)

    # Schedule removal of the OTHER legacy entries; primary stays as hub.
    for legacy_entry in legacy[1:]:
        hass.async_create_task(
            hass.config_entries.async_remove(legacy_entry.entry_id)
        )

    return True


# ---------------------------------------------------------------------------
# Setup / unload.
# ---------------------------------------------------------------------------


async def _recover_subentries_from_storage(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """If the hub has no route subentries (e.g. because a v1->v2
    migration partially failed) but the per-route Store files are
    still on disk, reconstruct subentries from those file names.
    """
    if entry.subentries:
        return

    from .stations import STATIONS  # noqa: WPS433 — local import to avoid cycle
    station_lookup = {s.lower(): s for s in STATIONS}
    storage_dir = hass.config.path(".storage")

    try:
        files = await hass.async_add_executor_job(os.listdir, storage_dir)
    except Exception:  # noqa: BLE001
        return

    routes: list[tuple[str, str]] = []
    for fname in files:
        if not fname.startswith("ns_reisadvies_tracked_trips_"):
            continue
        rest = fname[len("ns_reisadvies_tracked_trips_"):]
        # Try splits matching known station names. Stations may
        # contain underscores after sanitisation; iterate possible
        # split points and verify both halves against the lookup.
        parts = rest.split("_")
        found = False
        for i in range(1, len(parts)):
            fr = "_".join(parts[:i]).replace("_", " ")
            to = "_".join(parts[i:]).replace("_", " ")
            if fr.lower() in station_lookup and to.lower() in station_lookup:
                routes.append((station_lookup[fr.lower()], station_lookup[to.lower()]))
                found = True
                break
        if not found and len(parts) == 2:
            # Last-resort: assume the simple two-part case
            routes.append((parts[0], parts[1]))

    if not routes:
        return

    _LOGGER.warning(
        "Hub has no subentries; reconstructing %d route(s) from storage", len(routes)
    )
    for fr, to in routes:
        try:
            sub = ConfigSubentry(
                data={CONF_FROM_STATION: fr, CONF_TO_STATION: to},
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=f"{fr} -> {to}",
                unique_id=f"{fr}_{to}".lower(),
            )
            hass.config_entries.async_add_subentry(entry, sub)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not recover subentry %s -> %s: %s", fr, to, err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the hub: build a coordinator per route subentry."""
    hass.data.setdefault(DOMAIN, {})

    # Self-heal: if a previous (failed) migration left the hub without
    # subentries, try to rebuild them from the per-route Store files.
    await _recover_subentries_from_storage(hass, entry)

    # Hub-wide config
    api_key = entry.data.get(CONF_API_KEY)
    scan_interval = int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    fav_hours = int(entry.data.get(CONF_FAV_HOURS, DEFAULT_FAV_HOURS))
    fetch_composition = bool(entry.data.get(CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION))

    # Coordinator per subentry. We store them in hass.data keyed by
    # subentry_id so the sensor platform can pick them up.
    coordinators: dict[str, NSUpdateCoordinator] = {}
    for subentry_id, subentry in (entry.subentries or {}).items():
        if subentry.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        from_st = subentry.data.get(CONF_FROM_STATION)
        to_st = subentry.data.get(CONF_TO_STATION)
        if not from_st or not to_st:
            continue
        coordinator = NSUpdateCoordinator(
            hass,
            api_key=api_key,
            from_station=from_st,
            to_station=to_st,
            scan_interval_minutes=scan_interval,
            fav_hours=fav_hours,
            fetch_composition=fetch_composition,
        )
        await coordinator.async_load_tracked()
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry_id] = coordinator

    hass.data[DOMAIN][entry.entry_id] = coordinators

    # Backfill: link existing entities to their subentry by unique_id.
    # Entities created before HA's subentry-aware async_add_entities have
    # config_subentry_id=None; this rewrites them so HA tracks the link
    # and the entity is shown under the right subentry in the UI.
    _backfill_entity_subentries(hass, entry)

    # Static path + Lovelace card auto-registration (one-shot per HA).
    if "static_paths_registered" not in hass.data[DOMAIN]:
        path = hass.config.path("custom_components/ns_reisadvies/www")
        if os.path.isdir(path):
            await hass.http.async_register_static_paths([
                StaticPathConfig(
                    url_path="/ns_reisadvies",
                    path=path,
                    cache_headers=False,
                )
            ])
            hass.data[DOMAIN]["static_paths_registered"] = True

            try:
                integration = await async_get_integration(hass, DOMAIN)
                version = str(integration.version or "0")
            except Exception:  # noqa: BLE001
                version = "0"
            await _async_register_card_resource(hass, version)
            hass.data[DOMAIN]["card_url_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _backfill_entity_subentries(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set config_subentry_id on existing entities by matching unique_id.

    Older sensors created before HA's subentry-aware async_add_entities
    (or added via legacy migration) end up with config_subentry_id=None
    even though they conceptually belong to a subentry. This function
    finds them by unique_id and links them to the matching subentry.
    """
    ent_reg = er.async_get(hass)
    # Build a unique_id -> subentry_id map for this hub's route subentries.
    uid_to_subentry: dict[str, str] = {}
    for sub_id, sub in (entry.subentries or {}).items():
        if sub.subentry_type != SUBENTRY_TYPE_ROUTE:
            continue
        from_st = sub.data.get(CONF_FROM_STATION)
        to_st = sub.data.get(CONF_TO_STATION)
        if not from_st or not to_st:
            continue
        uid_to_subentry[f"{from_st}_{to_st}".lower()] = sub_id

    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent.config_subentry_id:
            continue
        target = uid_to_subentry.get(ent.unique_id)
        if not target:
            continue
        try:
            ent_reg.async_update_entity(
                ent.entity_id, config_subentry_id=target
            )
            _LOGGER.debug(
                "Linked %s (uid=%s) to subentry %s",
                ent.entity_id, ent.unique_id, target,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Could not link %s to subentry %s: %s",
                ent.entity_id, target, err,
            )


async def _async_register_card_resource(hass: HomeAssistant, version: str) -> None:
    """Register the Lovelace card via add_extra_js_url and Lovelace resources."""
    url = f"{CARD_URL}?v={version}"
    try:
        add_extra_js_url(hass, url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("add_extra_js_url failed: %s", err)

    try:
        lov_data = hass.data.get(lovelace.DOMAIN)
        if lov_data is None:
            return
        resources = getattr(lov_data, "resources", None)
        if resources is None and isinstance(lov_data, dict):
            resources = lov_data.get("resources")
        if resources is None:
            return
        if not resources.loaded:
            await resources.async_load()

        existing = next(
            (r for r in resources.async_items() if (r.get("url") or "").split("?")[0] == CARD_URL),
            None,
        )
        if existing:
            if existing.get("url") != url:
                await resources.async_update_item(
                    existing["id"], {"url": url, "res_type": existing.get("type", "module")}
                )
        else:
            await resources.async_create_item({"url": url, "res_type": "module"})
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not auto-register Lovelace resource (you may need to add %s manually): %s",
            url, err,
        )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the hub when global options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the hub."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
