"""NS Reisadvies integration."""
import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components import lovelace
from homeassistant.loader import async_get_integration

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_FROM_STATION,
    CONF_TO_STATION,
    CONF_SCAN_INTERVAL,
    CONF_FAV_HOURS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
)
from .coordinator import NSUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CARD_URL = "/ns_reisadvies/ns-reisadvies-card.js"


def _opt(entry: ConfigEntry, key: str, default):
    """Read option, fall back to data, then to the supplied default."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an NS Reisadvies entry and register the Lovelace card path."""
    hass.data.setdefault(DOMAIN, {})

    api_key = _opt(entry, CONF_API_KEY, None)
    act_station = entry.data.get(CONF_FROM_STATION)
    arr_station = entry.data.get(CONF_TO_STATION)
    scan_interval = int(_opt(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    fav_hours = int(_opt(entry, CONF_FAV_HOURS, DEFAULT_FAV_HOURS))

    coordinator = NSUpdateCoordinator(
        hass,
        api_key=api_key,
        from_station=act_station,
        to_station=arr_station,
        scan_interval_minutes=scan_interval,
        fav_hours=fav_hours,
    )
    await coordinator.async_load_tracked()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register the static path for the Lovelace card once per HA instance,
    # AND auto-register the JS file so users do not need to add it
    # manually under Settings → Dashboards → Resources. The integration
    # version is appended as a cache-buster.
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
            _LOGGER.info("Registered Lovelace card path /ns_reisadvies")

            try:
                integration = await async_get_integration(hass, DOMAIN)
                version = str(integration.version or "0")
            except Exception:  # noqa: BLE001
                version = "0"
            await _async_register_card_resource(hass, version)
            hass.data[DOMAIN]["card_url_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry whenever the user changes options so that
    # scan_interval/fav_hours take effect immediately.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_register_card_resource(hass: HomeAssistant, version: str) -> None:
    """Auto-register the Lovelace card.

    Tries two routes so the card shows up across all dashboard modes:

    1. ``frontend.add_extra_js_url`` — works for the default Lovelace
       dashboard and most storage-mode dashboards.
    2. ``lovelace_resources`` storage collection — needed for custom
       storage-mode dashboards (``/dashboard-<id>``) which do not pick
       up extra_module_url. This mirrors what HACS does for plugins.

    Idempotent on both routes: existing entries pointing at our card
    are updated to the current version rather than duplicated. YAML-mode
    Lovelace setups are silently skipped — there is no resources
    collection to write to in that case.
    """
    url = f"{CARD_URL}?v={version}"

    try:
        add_extra_js_url(hass, url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("add_extra_js_url failed: %s", err)

    try:
        # LovelaceData is a dataclass in modern HA (2024.x+); older
        # versions stored a plain dict. Try attribute access first, fall
        # back to dict-style for forward and backward compatibility.
        lov_data = hass.data.get(lovelace.DOMAIN)
        if lov_data is None:
            _LOGGER.debug("Lovelace data not available; skipping resource registration")
            return
        resources = getattr(lov_data, "resources", None)
        if resources is None and isinstance(lov_data, dict):
            resources = lov_data.get("resources")
        if resources is None:
            _LOGGER.debug("Lovelace resources collection not available")
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
                _LOGGER.info("Updated Lovelace resource for NS Reisadvies card to %s", version)
            else:
                _LOGGER.debug("Lovelace resource already at %s", version)
        else:
            await resources.async_create_item({"url": url, "res_type": "module"})
            _LOGGER.info("Registered Lovelace resource for NS Reisadvies card v%s", version)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not auto-register Lovelace resource (you may need to add %s manually): %s",
            url, err,
        )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an NS Reisadvies entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
