"""Config and options flow for the NS Reisadvies integration.

v2 architecture: ONE hub config entry holds the integration-wide
options (api_key, scan interval, favourite retention, fetch
composition). Each route lives as a subentry under the hub
(from_station / to_station). This mirrors the standard Home
Assistant pattern that integrations like ZHA and Bluetooth use.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.util import slugify
from homeassistant.helpers.selector import (
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
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
    CONF_FILTER_DAYS,
    CONF_FILTER_TIME,
    CONF_FILTER_WINDOW_MINUTES,
    CONF_FILTER_DATE,
    CONF_FIRST_WEEKDAY,
    CONF_ROUTE_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FAV_HOURS,
    DEFAULT_FETCH_COMPOSITION,
    DEFAULT_LIVE_TRAIN_MAP,
    DEFAULT_LIVE_MAP_REFRESH_SECONDS,
    DEFAULT_FILTER_WINDOW_MINUTES,
    DEFAULT_FIRST_WEEKDAY,
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


# v2.16.3: localized weekday labels embedded in the SelectOptionDicts
# directly. Previously we relied on `translation_key="filter_days"` to
# let HA's frontend look up the localized full names from strings.json,
# but the frontend RE-SORTS such options alphabetically by translated
# label — so the dropdown ended up "Friday, Monday, Saturday, Sunday,
# Thursday, Tuesday, Wednesday" regardless of our intended rotation.
# Embedding the label directly bypasses that sort.
_WEEKDAY_NAMES: dict[str, list[str]] = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday",
           "Friday", "Saturday", "Sunday"],
    "nl": ["Maandag", "Dinsdag", "Woensdag", "Donderdag",
           "Vrijdag", "Zaterdag", "Zondag"],
}


def _weekday_options(
    first_weekday: Any, language: str = "en",
) -> list[SelectOptionDict]:
    """Return the seven weekday SelectOptionDicts rotated so the chosen
    first day appears at the top of the list.

    ``first_weekday`` may be a string or int (Python weekday convention:
    0 = Monday … 6 = Sunday). Anything that cannot be parsed back into
    that range falls back to Monday. ``language`` is the user's HA UI
    language ("en" or "nl"); unsupported languages fall back to English.

    v2.16.7: returned to plain labels. We tried a U+0001..U+0007 prefix
    in v2.16.6 to game HA's mandatory alphabetical sort while staying
    compact in DROPDOWN mode, but ``ha-combo-box``'s filter pipeline
    swallows the items entirely (empty dropdown). The combination of
    "compact chip-style dropdown" AND "rotated first-weekday order" is
    not achievable without a visible label prefix, so we keep the
    correct LIST-mode ordering and accept a vertical checkbox stack.
    """
    try:
        start = int(first_weekday)
    except (TypeError, ValueError):
        start = 0
    if not 0 <= start <= 6:
        start = 0
    names = _WEEKDAY_NAMES.get(
        (language or "en").lower()[:2], _WEEKDAY_NAMES["en"],
    )
    order = [(i + start) % 7 for i in range(7)]
    return [SelectOptionDict(value=str(d), label=names[d]) for d in order]


def _read_first_weekday(parent: Any) -> str:
    """Pull CONF_FIRST_WEEKDAY off the hub entry's options safely.

    Defensive reads — both the entry and its options attribute may be
    missing during a fresh subentry add (no parent attached yet) or in
    test fixtures. Always returns a string.
    """
    if parent is None:
        return DEFAULT_FIRST_WEEKDAY
    try:
        return str(parent.options.get(CONF_FIRST_WEEKDAY, DEFAULT_FIRST_WEEKDAY))
    except Exception:  # noqa: BLE001
        return DEFAULT_FIRST_WEEKDAY


def _validate_route(
    user_input: dict[str, Any],
    existing_routes: list[tuple[str, str, str]],
) -> dict[str, str]:
    """Return per-field validation errors for a route subentry.

    ``existing_routes`` is a list of ``(from, to, name)`` tuples — name
    may be an empty string for routes that have no custom name. The
    duplicate check requires the full triple to match before flagging.
    """
    errors: dict[str, str] = {}
    raw_from = (user_input.get(CONF_FROM_STATION) or "").strip()
    raw_to = (user_input.get(CONF_TO_STATION) or "").strip()
    raw_name = (user_input.get(CONF_ROUTE_NAME) or "").strip()
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
        for fr, to, nm in existing_routes:
            if (
                fr.lower() == raw_from.lower()
                and to.lower() == raw_to.lower()
                and nm.strip().lower() == raw_name.lower()
            ):
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

    # ----- Reauthentication flow (Silver quality-scale rule) ---------
    # Triggered when the coordinator raises ConfigEntryAuthFailed (e.g.
    # the NS API key was rotated or revoked). HA opens this flow in
    # the UI and asks the user to enter a fresh key, which we validate
    # with a real probe before storing.

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Entry point: HA invoked us because the credentials are stale."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a new API key and verify it works."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = (user_input.get(CONF_API_KEY) or "").strip()
            from .coordinator import async_validate_api_key
            probe_error = await async_validate_api_key(self.hass, api_key)
            if probe_error:
                errors["base"] = probe_error
            else:
                existing = self._get_reauth_entry()
                self.hass.config_entries.async_update_entry(
                    existing,
                    data={**existing.data, CONF_API_KEY: api_key},
                )
                # Force a reload so the coordinator picks up the new key.
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(existing.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                # Test-before-configure (Bronze quality-scale rule):
                # validate the NS API key with a real probe call before
                # creating the entry. Surfaces invalid_auth /
                # cannot_connect errors in the form so the user can
                # correct them on the spot.
                from .coordinator import async_validate_api_key
                probe_error = await async_validate_api_key(self.hass, api_key)
                if probe_error:
                    errors["base"] = probe_error
                else:
                    # v3 layout: only credentials live in entry.data;
                    # configurable settings (refresh interval etc.)
                    # live in entry.options. Defaults applied here so
                    # the options form has sensible starting values.
                    hub_data = {CONF_API_KEY: api_key}
                    hub_options = {
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
                        options=hub_options,
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Initial step shown when the user clicks 'Add route'."""
        return await self._show_form(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing route."""
        return await self._show_form(user_input, reconfigure=True)

    async def _show_form(
        self,
        user_input: dict[str, Any] | None,
        reconfigure: bool = False,
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}

        # Bestaande routes verzamelen om duplicaten te vangen. Each entry
        # is a (from, to, name) triple — name "" when the route has no
        # custom name, so two unnamed routes between the same stations
        # still collide.
        # ``_get_entry`` is provided by ``ConfigSubentryFlow`` on real HA
        # runs and stubbed by the unit tests. The hasattr guard keeps
        # this defensive against future HA refactors where the method
        # name might change again.
        parent: config_entries.ConfigEntry | None = (
            self._get_entry() if hasattr(self, "_get_entry") else None
        )
        existing: list[tuple[str, str, str]] = []
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
                nm = sub.data.get(CONF_ROUTE_NAME) or ""
                if fr and to:
                    existing.append((fr, to, nm))

        if user_input is not None:
            # Filter fields are now grouped under a section() — they arrive
            # nested as user_input["filters"][...]. Older callers (and tests
            # that pre-date v2.14.2) still pass them flat, so accept either.
            _section = user_input.get("filters")
            src: dict[str, Any] = (
                _section if isinstance(_section, dict) else user_input
            )
            errs = _validate_route(user_input, existing_routes=existing)
            errors.update(errs)
            if not errors:
                from_st = user_input[CONF_FROM_STATION]
                to_st = user_input[CONF_TO_STATION]
                # Custom route name (v2.15.0). Optional. When supplied,
                # used as the subentry title and as the basis for the
                # sensor's friendly name and entity_id slug.
                _route_name = (user_input.get(CONF_ROUTE_NAME) or "").strip()
                title = _route_name if _route_name else f"{from_st} -> {to_st}"
                # Build the route data dict, preserving filter fields when set.
                # Empty/None filter fields are dropped so subentries created in
                # earlier versions stay byte-identical when the user re-saves.
                route_data: dict[str, Any] = {
                    CONF_FROM_STATION: from_st,
                    CONF_TO_STATION: to_st,
                }
                if _route_name:
                    route_data[CONF_ROUTE_NAME] = _route_name
                _filter_days = src.get(CONF_FILTER_DAYS) or []
                if _filter_days:
                    route_data[CONF_FILTER_DAYS] = [int(d) for d in _filter_days]
                _filter_time = (src.get(CONF_FILTER_TIME) or "").strip()
                if _filter_time:
                    route_data[CONF_FILTER_TIME] = _filter_time
                _filter_window = int(
                    src.get(
                        CONF_FILTER_WINDOW_MINUTES, DEFAULT_FILTER_WINDOW_MINUTES,
                    )
                )
                if _filter_window:
                    route_data[CONF_FILTER_WINDOW_MINUTES] = _filter_window
                _filter_date = (src.get(CONF_FILTER_DATE) or "").strip()
                if _filter_date:
                    route_data[CONF_FILTER_DATE] = _filter_date

                if reconfigure:
                    return self.async_update_and_abort(
                        self._get_entry(),  # type: ignore[attr-defined]
                        self._get_reconfigure_subentry(),  # type: ignore[attr-defined]
                        data=route_data,
                        title=title,
                    )
                # unique_id includes the route name slug when set so two
                # routes between the same stations but with different
                # names (e.g. "Werk" and "Weekend") get distinct IDs and
                # therefore distinct sensor entities. Routes without a
                # name keep the legacy "from_to" unique_id so existing
                # entity registry entries from v2.13.x / v2.14.x continue
                # to match.
                if _route_name:
                    name_slug = slugify(_route_name)
                    unique_id = f"{from_st}_{to_st}_{name_slug}".lower()
                else:
                    unique_id = f"{from_st}_{to_st}".lower()
                return self.async_create_entry(
                    title=title,
                    data=route_data,
                    unique_id=unique_id,
                )

        # Pre-fill bij reconfigure
        defaults: dict[str, Any] = {}
        if reconfigure:
            try:
                sub = self._get_reconfigure_subentry()  # type: ignore[attr-defined]
                defaults = dict(sub.data)
            except Exception:  # noqa: BLE001
                defaults = {}

        # First-day-of-week preference (v2.15.2). Display-only — the
        # day-picker rotation reflects the user's locale (NL/EU = Mon,
        # US = Sun). Helpers are pure so the rotation can be unit-tested
        # without spinning up the form.
        # v2.16.3: also pass the active HA language so the labels are
        # localised directly in the SelectOptionDict (the frontend
        # re-sorts options alphabetically when translation_key is used).
        _hass = getattr(self, "hass", None)
        _lang = getattr(getattr(_hass, "config", None), "language", "en")
        weekday_options = _weekday_options(_read_first_weekday(parent), _lang)

        schema = vol.Schema({
            vol.Optional(
                CONF_ROUTE_NAME,
                default=defaults.get(CONF_ROUTE_NAME, vol.UNDEFINED),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_FROM_STATION,
                default=defaults.get(CONF_FROM_STATION, vol.UNDEFINED),
            ): _station_selector(),
            vol.Required(
                CONF_TO_STATION,
                default=defaults.get(CONF_TO_STATION, vol.UNDEFINED),
            ): _station_selector(),
            vol.Required("filters"): section(
                vol.Schema({
                    vol.Optional(
                        CONF_FILTER_DAYS,
                        default=[str(d) for d in defaults.get(CONF_FILTER_DAYS, [])],
                    ): SelectSelector(
                        SelectSelectorConfig(
                            # v2.16.3: Options are rotated so the user's
                            # preferred first day of the week (set on the
                            # hub OptionsFlow, defaults to Monday) appears
                            # at the top of the dropdown, AND the labels
                            # are pre-localised here so HA's frontend
                            # doesn't re-sort them alphabetically (which
                            # is what happened when we used
                            # ``translation_key`` — the dropdown ended up
                            # "Friday, Monday, Saturday, …").
                            options=weekday_options,
                            # v2.16.8: back to DROPDOWN. HA's multi-select
                            # ha-combo-box force-alphabetises labels and
                            # there's no way to override that without a
                            # visible label prefix or rejected control
                            # characters (see v2.16.4–v2.16.7). User
                            # explicitly chose compact chip-style display
                            # over rotated weekday order — alphabetical
                            # is acceptable for a 7-item picker.
                            mode=SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        ),
                    ),
                    vol.Optional(
                        CONF_FILTER_TIME,
                        default=defaults.get(CONF_FILTER_TIME, vol.UNDEFINED),
                    ): TimeSelector(),
                    vol.Optional(
                        CONF_FILTER_WINDOW_MINUTES,
                        default=int(
                            defaults.get(
                                CONF_FILTER_WINDOW_MINUTES,
                                DEFAULT_FILTER_WINDOW_MINUTES,
                            )
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=360,
                            step=15,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.SLIDER,
                        ),
                    ),
                    vol.Optional(
                        CONF_FILTER_DATE,
                        default=defaults.get(CONF_FILTER_DATE, vol.UNDEFINED),
                    ): DateSelector(),
                }),
                # Section is shown expanded by default.
                {"collapsed": False},
            ),
        })
        step_id = "reconfigure" if reconfigure else "user"
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)


# ---------------------------------------------------------------------------
# Hub options flow: edit the integration-wide settings.
# ---------------------------------------------------------------------------


class NSReisadviesOptionsFlowHandler(config_entries.OptionsFlow):
    """Edit hub-level (integration-wide) settings.

    Per the Bronze quality-scale rule on
    ``ConfigEntry.data`` vs ``ConfigEntry.options`` separation,
    configurable settings live on ``entry.options``; only credentials
    live on ``entry.data``. The form submits both: the API key is
    written back to ``data`` (so a key-rotation re-runs setup with
    fresh credentials), everything else lands on ``options``.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.entry = config_entry

    def _read(self, key: str, default: Any) -> Any:
        """Read a value, preferring options over data (post-v3 layout)."""
        if self.entry.options and key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Validate the (possibly rotated) API key before saving.
            api_key_input = (user_input.get(CONF_API_KEY) or "").strip()
            from .coordinator import async_validate_api_key
            probe_error = await async_validate_api_key(self.hass, api_key_input)
            if probe_error:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_schema(api_key_input),
                    errors={"base": probe_error},
                )

            # Split: API key → entry.data, everything else → entry.options.
            new_data = {**self.entry.data, CONF_API_KEY: api_key_input}
            new_options = {
                k: v for k, v in user_input.items() if k != CONF_API_KEY
            }
            self.hass.config_entries.async_update_entry(
                self.entry, data=new_data, options=new_options,
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init", data_schema=self._build_schema(),
        )

    def _build_schema(self, api_key_default: str | None = None) -> vol.Schema:
        api_val = api_key_default if api_key_default is not None else self._read(
            CONF_API_KEY, "",
        )
        return vol.Schema({
            vol.Required(CONF_API_KEY, default=str(api_val)): str,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=int(self._read(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            ): vol.All(int, vol.Range(min=1, max=60)),
            vol.Required(
                CONF_FAV_HOURS,
                default=int(self._read(CONF_FAV_HOURS, DEFAULT_FAV_HOURS)),
            ): vol.All(int, vol.Range(min=0, max=72)),
            vol.Required(
                CONF_FETCH_COMPOSITION,
                default=bool(self._read(CONF_FETCH_COMPOSITION, DEFAULT_FETCH_COMPOSITION)),
            ): bool,
            vol.Required(
                CONF_LIVE_TRAIN_MAP,
                default=bool(self._read(CONF_LIVE_TRAIN_MAP, DEFAULT_LIVE_TRAIN_MAP)),
            ): bool,
            vol.Required(
                CONF_LIVE_MAP_REFRESH_SECONDS,
                default=int(
                    self._read(CONF_LIVE_MAP_REFRESH_SECONDS, DEFAULT_LIVE_MAP_REFRESH_SECONDS)
                ),
            ): vol.All(int, vol.Range(min=5, max=60)),
            # First day of week (v2.15.2). Display-only — controls the
            # rotation of the day picker on the per-route filter form.
            vol.Required(
                CONF_FIRST_WEEKDAY,
                default=str(self._read(CONF_FIRST_WEEKDAY, DEFAULT_FIRST_WEEKDAY)),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value="0", label="Monday"),
                        SelectOptionDict(value="6", label="Sunday"),
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    multiple=False,
                    translation_key="first_weekday",
                ),
            ),
        })
