"""The Virtual RF/IR Device integration.

Creates a virtual Home Assistant device that represents a physical appliance
(e.g. a fireplace) controlled through an existing IR/RF ``remote`` entity such
as a Broadlink transmitter. This step only registers the device; control
entities (buttons, switches, ...) are added in later steps.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BUTTONS,
    CONF_CLIMATES,
    CONF_ID,
    CONF_LIGHTS,
    CONF_MEDIA_PLAYERS,
    CONF_REMOTE,
    CONF_SWITCHES,
    DOMAIN,
    MANUFACTURER,
)

# Maps each options list to the unique_id prefix its entities use.
_ENTITY_LISTS: tuple[tuple[str, str], ...] = (
    (CONF_BUTTONS, "button"),
    (CONF_SWITCHES, "switch"),
    (CONF_LIGHTS, "light"),
    (CONF_CLIMATES, "climate"),
    (CONF_MEDIA_PLAYERS, "media_player"),
)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.CLIMATE,
    Platform.MEDIA_PLAYER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a virtual RF/IR device from a config entry."""
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data[CONF_NAME],
        manufacturer=MANUFACTURER,
        via_device=_resolve_via_device(hass, entry.data[CONF_REMOTE]),
    )

    _async_cleanup_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


@callback
def _async_cleanup_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove registry entries for items no longer in the config.

    Entities that are simply not re-added on reload linger in the entity
    registry as orphaned/unavailable entries (and reappear after a restart).
    Purging them by unique_id keeps the device in sync with the config.
    """
    valid_unique_ids = {
        f"{entry.entry_id}_{prefix}_{item[CONF_ID]}"
        for option_key, prefix in _ENTITY_LISTS
        for item in entry.options.get(option_key, [])
    }

    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id not in valid_unique_ids:
            registry.async_remove(reg_entry.entity_id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its commands change so buttons are rebuilt."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _resolve_via_device(
    hass: HomeAssistant, remote_entity_id: str
) -> tuple[str, str] | None:
    """Return the identifiers of the hub device behind the remote entity.

    Links the virtual appliance to the transmitter it is "connected through"
    on its device page. Returns ``None`` if the remote's device can't be
    resolved, in which case no link is drawn.
    """
    entity_registry = er.async_get(hass)
    remote_entry = entity_registry.async_get(remote_entity_id)
    if remote_entry is None or remote_entry.device_id is None:
        return None

    device_registry = dr.async_get(hass)
    hub_device = device_registry.async_get(remote_entry.device_id)
    if hub_device is None or not hub_device.identifiers:
        return None

    return next(iter(hub_device.identifiers))
