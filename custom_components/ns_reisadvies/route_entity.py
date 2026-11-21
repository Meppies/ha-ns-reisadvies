"""What every per-route entity shares (v2.28.0).

The route's identity — the unique-id stem and the short entity-id stem
— was worked out inline in the sensor platform. With binary sensors and
an event entity joining it, it lives here once, together with the base
class for everything that describes a route's *focus trip*.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_FROM_STATION, CONF_ROUTE_NAME, CONF_TO_STATION, DOMAIN
from .coordinator import NSUpdateCoordinator


def route_ids(data: Mapping[str, Any]) -> tuple[str, str, str, str, str | None]:
    """(unique-id stem, entity-id stem, from, to, name) for a route subentry.

    The unique id mirrors the subentry's, so registry entries from
    every earlier version keep matching; a named route gets its slug
    appended. The entity-id stem is short and readable —
    ``ns_werk`` rather than ``ns_hilversum_duivendrecht_werk``.
    """
    from_st = data.get(CONF_FROM_STATION) or "?"
    to_st = data.get(CONF_TO_STATION) or "?"
    route_name = (data.get(CONF_ROUTE_NAME) or "").strip() or None
    if route_name:
        return (
            f"{from_st}_{to_st}_{slugify(route_name)}".lower(),
            f"ns_{slugify(route_name)}",
            from_st, to_st, route_name,
        )
    return (
        f"{from_st}_{to_st}".lower(),
        f"ns_{slugify(from_st)}_{slugify(to_st)}",
        from_st, to_st, None,
    )


class NSFocusEntity(CoordinatorEntity[NSUpdateCoordinator]):
    """An entity about the route's focus trip, on the route's device.

    The focus is a pinned favourite when there is one, else the next
    departure; see ``_focus``. Every such entity registers with the
    coordinator while it is in Home Assistant, which is what keeps the
    minute tick running — and the ones that show where the train is
    register as *live*, which is what allows NS to be asked. One that
    is disabled in the entity settings is never added, never registers,
    and so never costs a request.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _platform_domain = "sensor"
    _live = False
    _last_train = False

    def __init__(
        self,
        coordinator: NSUpdateCoordinator,
        key: str,
        *,
        route_unique_id: str,
        route_object_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{route_unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, route_unique_id)})
        # As everywhere else here: set the id outright, because Home
        # Assistant otherwise derives it from the translated name and
        # it would differ per language.
        self.entity_id = f"{self._platform_domain}.{route_object_id}_{key}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_focus_consumer(
                live=self._live, last_train=self._last_train,
            )
        )

    @property
    def focus(self) -> dict[str, Any]:
        return self.coordinator.focus or {}

    @property
    def live(self) -> dict[str, Any]:
        return self.coordinator.focus_live or {}

    @property
    def available(self) -> bool:
        """Available whenever the route is; no train is not a fault."""
        return bool(self.coordinator.last_update_success)
