"""The Virtual RF/IR Device integration.

Creates a virtual Home Assistant device that represents a physical appliance
(e.g. a fireplace) controlled through an existing IR/RF ``remote`` entity such
as a Broadlink transmitter. This step only registers the device; control
entities (buttons, switches, ...) are added in later steps.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import CONF_REMOTE, DOMAIN, MANUFACTURER

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SWITCH]


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


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
