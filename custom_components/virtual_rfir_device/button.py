"""Button platform: one button entity per stored IR/RF command."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CODE, CONF_COMMANDS, CONF_ICON, CONF_ID, CONF_REMOTE, DOMAIN
from .helpers import async_send_code


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a button entity for each command in the entry options."""
    commands = entry.options.get(CONF_COMMANDS, [])
    async_add_entities(
        VirtualRfirButton(entry, command) for command in commands
    )


class VirtualRfirButton(ButtonEntity):
    """A stateless button that transmits one IR/RF code via the remote."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, command: dict[str, Any]) -> None:
        """Initialize the button from a stored command definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._code: str = command[CONF_CODE]
        self._attr_name = command[CONF_NAME]
        self._attr_icon = command.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_{command[CONF_ID]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )

    async def async_press(self) -> None:
        """Transmit the stored code through the configured remote."""
        await async_send_code(self.hass, self._remote_entity_id, self._code)
