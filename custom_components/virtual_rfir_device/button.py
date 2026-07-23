"""Button platform: one button entity per configured button."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BUTTONS,
    CONF_CODE_ID,
    CONF_DEVICE,
    CONF_ICON,
    CONF_ID,
    CONF_REMOTE,
    DOMAIN,
)
from .helpers import async_send_code


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a button entity for each configured button."""
    buttons = entry.options.get(CONF_BUTTONS, [])
    async_add_entities(VirtualRfirButton(entry, button) for button in buttons)


class VirtualRfirButton(ButtonEntity):
    """A stateless button that transmits one learned command via the remote."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, button: dict[str, Any]) -> None:
        """Initialize the button from a stored button definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._device: str | None = entry.data.get(CONF_DEVICE)
        self._command: str | None = button.get(CONF_CODE_ID)
        self._attr_name = button[CONF_NAME]
        self._attr_icon = button.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_button_{button[CONF_ID]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )

    async def async_press(self) -> None:
        """Transmit the referenced command through the configured remote."""
        await async_send_code(
            self.hass, self._remote_entity_id, self._command, self._device
        )
