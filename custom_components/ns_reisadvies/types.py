"""Runtime data types for the NS Reisadvies integration.

Holds the shape of ``ConfigEntry.runtime_data`` (Platinum quality-scale
rule ``runtime-data``: integration runtime state lives on the entry,
not in ``hass.data[DOMAIN][entry_id]``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import NSUpdateCoordinator


@dataclass
class NSRuntimeData:
    """Per-entry runtime state for the NS Reisadvies hub.

    The integration declares ``single_config_entry: true`` so this is
    effectively a per-Home-Assistant singleton, but it remains tied to
    the config entry's lifecycle (so a reload / unload tears it all
    down cleanly).
    """

    # One DataUpdateCoordinator per route subentry.
    coordinators: dict[str, NSUpdateCoordinator] = field(default_factory=dict)

    # Hub-wide flags — these come from ``ConfigEntry.options`` and
    # influence sensor extra_state_attributes / WS handlers.
    live_train_map_enabled: bool = False
    live_map_refresh_seconds: int = 10

    # /v2/stations response, cached per-HA-boot. {code: {name, lat, lng}}
    stations_geo: dict[str, dict[str, Any]] | None = None

    # Active live-train-map WebSocket sessions. Keyed by session_id.
    live_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)

    # One-shot guards: True after the corresponding registration ran in
    # this HA process. Survives reloads of this entry because
    # async_unload doesn't reset these (they're per-HA registrations).
    ws_registered: bool = False
    rail_refresh_scheduled: bool = False
    static_paths_registered: bool = False
    card_url_registered: bool = False


# Aliased ConfigEntry that exposes ``runtime_data`` typed as
# ``NSRuntimeData``. HA's ConfigEntry is generic; integrations type their
# runtime_data via an alias for full mypy support. Annotated as
# ``TypeAlias`` so mypy --strict treats it as a type, not a runtime value.
from typing import TypeAlias  # noqa: E402

NSConfigEntry: TypeAlias = ConfigEntry[NSRuntimeData]
