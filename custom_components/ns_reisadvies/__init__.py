"""NS Reisadvies integration."""
import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig

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


def _opt(entry: ConfigEntry, key: str, default):
    """Lees option met fallback naar data en daarna default."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Start de integratie en registreer het pad voor de kaart."""
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

    # Registreer het statische pad voor de Lovelace-kaart eenmalig
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
            _LOGGER.info("Pad /ns_reisadvies geregistreerd voor de kaart.")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options change zodat scan_interval/fav_hours direct werken
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry wanneer de gebruiker opties wijzigt."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verwijder de integratie."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
