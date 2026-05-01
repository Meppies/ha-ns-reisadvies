"""Config and options flow for the NS Reisadvies integration.

v2 architecture: ONE hub config entry holds the integration-wide
options (api_key, scan interval, favourite retention, fetch
composition). Each route lives as a subentry under the hub
(from_station / to_station). This mirrors the standard Home
Assistant pattern that integrations like ZHA and Bluetooth use.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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
    CONF_LIVE_TRAIN_MAP,
    CONF_LIVE_MAP_REFRESH_SECONDS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
    DEFAULT_FETCH_COMPOSITION,
    DEFAULT_LIVE_TRAIN_MAP,
    DEFAULT_LIVE_MAP_REFRESH_SECONDS,
)
from .stations import STATIONS

_LOGGER = logging.getLogger(__name__)


def _station_selector() -> SelectSelector:
    """Type-to-filter combo box rendered by ha-picker-combo-box."""
    return SelectSelector(
        SelectSelectorConfig(
            options=STATIONS,
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )


def _validate_route(
    user_input: dict,
    existing_routes: list[tuple[str, str]],
) -> dict[str, str]:
    """Return per-field validation errors for a route subentry."""
    errors: dict[str, str] = {}
    raw_from = (user_input.get(CONF_FROM_STATION) or "").strip()
    raw_to = (user_input.get(CONF_TO_STATION) or "").strip()
    lookup = {s.lower(): s for s in STATIONS}

    if raw_from and raw_from.lower() not in lookup:
        errors[CONF_FROM_STATION] = "unknown_station"
    if raw_to and raw_to.lower() not in lookup:
        errors[CONF_TO_STATION] = "unknown_station"

    if not errors and raw_from and raw_to and raw_from.lower() == raw_to.lower():
        errors["base"] = "same_station"

    if not errors:
        # Normalise to the canonical casing
        user_input[CONF_FROM_STATION] = lookup[raw_from.lower()]
        user_input[CONF_TO_STATION] = lookup[raw_to.lower()]
        for fr, to in existing_routes:
            if fr.lower() == raw_from.lower() and to.lower() == raw_to.lower():
                errors["base"] = "duplicate_route"
                break

    return errors


# ---------------------------------------------------------------------------
# Hub-level config flow: creates the singleton "NS Reisadvies" entry.
# ---------------------------------------------------------------------------


class NSReisadviesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of NS Reisadvies."""

    VERSION = CONFIG_ENTRY_VERSION

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NSReisadviesOptionsFlowHandler:
        return NSReisadviesOptionsFlowHandler(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_ROUTE: NSRouteSubentryFlowHandler}

    async def async_step_user(self, user_input=None):
        """First-time setup: ask for API key + first route."""
        # Only one hub entry is allowed; further routes go via subentries.
        existing = self._async_current_entries()
        if existing:
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            errs = _validate_route(user_input, existing_routes=[])
            errors.update(errs)
            if not errors:
                api_key = (user_input.get(CONF_API_KEY) or "").strip()
                from_st = user_input[CONF_FROM_STATION]
                to_st = user_input[CONF_TO_STATION]
                # Hub data: globalen
                hub_data = {
                    CONF_API_KEY: api_key,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_FAV_HOURS: DEFAULT_FAV_HOURS,
                    CONF_FETCH_COMPOSITION: DEFAULT_FETCH_COMPOSITION,
                    CONF_LIVE_TRAIN_MAP: DEFAULT_LIVE_TRAIN_MAP,
                    CONF_LIVE_MAP_REFRESH_SECONDS: DEFAULT_LIVE_MAP_REFRESH_SECONDS,
                }
                # First route comes along as a subentry
                return self.async_create_entry(
                    title="NS Reisadvies",
                    data=hub_data,
                    subentries=[
                        {
                            "subentry_type": SUBENTRY_TYPE_ROUTE,
                            "title": f"{from_st} -> {to_st}",
                            "unique_id": f"{from_st}_{to_st}".lower(),
                            "data": {
                                CONF_FROM_STATION: from_st,
                                CONF_TO_STATION: to_st,
                            },
                        }
                    ],
                )

        schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_FROM_STATION): _station_selector(),
            vol.Required(CONF_TO_STATION): _station_selector(),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


# ---------------------------------------------------------------------------
# Subentry flow: add or reconfigure a single route under the hub.
# ---------------------------------------------------------------------------


class NSRouteSubentryFlowHandler(ConfigSubentryFlow):
    """Add a route subentry."""

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        """Initial step shown when the user clicks 'Add route'."""
        return await self._show_form(user_input)

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        """Edit an existing route."""
        return await self._show_form(user_input, reconfigure=True)

    async def _show_form(self, user_input, reconfigure: bool = False) -> SubentryFlowResult:
        errors: dict[str, str] = {}

        # Bestaande routes verzamelen om duplicaten te vangen.
        parent: config_entries.ConfigEntry | None = self._get_entry() if hasattr(self, "_get_entry") else None
        existing: list[tuple[str, str]] = []
        try:
            parent = parent or self._get_reconfigure_entry()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            parent = None
        if parent is not None:
            current_id = (
                self._reconfigure_subentry_id  # type: ignore[attr-defined]
                if reconfigure and hasattr(self, "_reconfigure_subentry_id")
                else None
            )
            for sid, sub in (parent.subentries or {}).items():
                if sid == current_id:
                    continue
                if sub.subentry_type != SUBENTRY_TYPE_ROUTE:
                    continue
                fr = sub.data.get(CONF_FROM_STATION)
                to = sub.data.get(CONF_TO_STATION)
                if fr and to:
                    existing.append((fr, to))

        if user_input is not None:
            errs = _validate_route(user_input, existing_routes=existing)
            errors.update(errs)
            if not errors:
                from_st = user_input[CONF_FROM_STATION]
                to_st = user_input[CONF_TO_STATION]
                title = f"{from_st} -> {to_st}"
                if reconfigure:
                    return self.async_update_and_abort(
                        self._get_reconfigure_entry(),  # type: ignore[attr-defined]
                        self._get_reconfigure_subentry(),  # type: ignore[attr-defined]
                        data={
                            CONF_FROM_STATION: from_st,
                            CONF_TO_STATION: to_st,
                        },
                        title=title,
                    )
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_FROM_STATION: from_st,
                        CONF_TO_STATION: to_st,
                    },
                    unique_id=f"{from_st}_{to_st}".lower(),
                )

        # Pre-fill bij reconfigure
        defaults: dict = {}
        if reconfigure:
            try:
                sub = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
                defaults = dict(sub.data)
            except Exception:  # noqa: BLE001
                defaults = {}

        schema = vol.Schema({
            vol.Required(
                CONF_FROM_STATION,
                default=defaults.get(CONF_FROM_STATION, vol.UNDEFINED),
            ): _station_selector(),
            vol.Required(
                CONF_TO_STATION,
                default=defaults.get(CONF_TO_STATION, vol.UNDEFINED),
            ): _station_selector(),
        })
        step_id = "reconfigure" if reconfigure else "user"
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)


# ---------------------------------------------------------------------------
# Hub options flow: edit the integration-wide settings.
# ---------------------------------------------------------------------------


class NSReisadviesOptionsFlowHandler(config_entries.OptionsFlow):
    """Edit hub-level (integration-wide) settings."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Schrijf naar entry.data zodat de hub de nieuwe waarden
            # bewaart en de update_listener een reload triggert.
            new_data = {**self.entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            return self.async_create_entry(title="", data={})

        data = self.entry.data
        api_val = data.get(CONF_API_KEY, "")
        int_val = int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        fav_val = int(data.get(CONF_FAV_HOURS, DEFAULT_FAV_HOURS))
        comp_val = bool(data.get(CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION))
        map_val = bool(data.get(CONF_LIVE_TRAIN_MAP, DEFAULT_LIVE_TRAIN_MAP))
        map_int = int(data.get(
            CONF_LIVE_MAP_REFRESH_SECONDS, DEFAULT_LIVE_MAP_REFRESH_SECONDS,
        ))

        schema = vol.Schema({
            vol.Required(CONF_API_KEY, default=str(api_val)): str,
            vol.Required(
                CONF_SCAN_INTERVAL, default=int_val
            ): vol.All(int, vol.Range(min=1, max=60)),
            vol.Required(
                CONF_FAV_HOURS, default=fav_val
            ): vol.All(int, vol.Range(min=0, max=72)),
            vol.Required(CONF_FETCH_COMPOSITION, default=comp_val): bool,
            vol.Required(CONF_LIVE_TRAIN_MAP, default=map_val): bool,
            vol.Required(
                CONF_LIVE_MAP_REFRESH_SECONDS, default=map_int,
            ): vol.All(int, vol.Range(min=5, max=60)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
