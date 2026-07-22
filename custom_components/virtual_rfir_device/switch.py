"""Switch platform: optimistic on/off switches built from IR/RF codes.

Because IR/RF devices don't report their real state, these switches are
assumed-state: Home Assistant shows separate on/off buttons and only remembers
the last command it sent. If the appliance is controlled by its physical
remote, the displayed state can drift.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CODES,
    CONF_ICON,
    CONF_ID,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_REMOTE,
    CONF_SWITCHES,
    DOMAIN,
)
from .helpers import async_send_code, resolve_code_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a switch entity for each configured switch."""
    codes = entry.options.get(CONF_CODES, [])
    switches = entry.options.get(CONF_SWITCHES, [])
    async_add_entities(
        VirtualRfirSwitch(entry, switch, codes) for switch in switches
    )


class VirtualRfirSwitch(SwitchEntity, RestoreEntity):
    """An optimistic switch that sends an IR/RF code to turn on and off."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        entry: ConfigEntry,
        switch: dict[str, Any],
        codes: list[dict[str, Any]],
    ) -> None:
        """Initialize the switch from a stored switch definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._on_code = resolve_code_entry(codes, switch.get(CONF_ON_CODE))
        self._off_code = resolve_code_entry(codes, switch.get(CONF_OFF_CODE))
        self._attr_name = switch[CONF_NAME]
        self._attr_icon = switch.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_switch_{switch[CONF_ID]}"
        self._attr_is_on = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state after a restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the on code and optimistically mark the switch on."""
        await async_send_code(self.hass, self._remote_entity_id, self._on_code)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the off code and optimistically mark the switch off."""
        await async_send_code(self.hass, self._remote_entity_id, self._off_code)
        self._attr_is_on = False
        self.async_write_ha_state()
