"""Climate platform: optimistic thermostats built from IR/RF codes.

An IR HVAC unit typically exposes a code to enter each mode (heat and/or cool),
an off code, and *relative* temperature up/down codes. This entity keeps a
virtual target temperature chosen from an explicit list of selectable values
(which need not be evenly spaced): changing the target fires the up/down code
once per list position to cover the difference.

Because the codes are relative and the appliance reports nothing, the entity is
assumed-state and can drift if the physical remote is used. A separate
temperature sensor can be linked to show a real current temperature; without
one, the current temperature mirrors the target so the dial still reads sensibly.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CLIMATES,
    CONF_COOL,
    CONF_COOL_CODE,
    CONF_DEVICE,
    CONF_DOWN_CODE,
    CONF_HEAT,
    CONF_HEAT_CODE,
    CONF_ICON,
    CONF_ID,
    CONF_OFF_CODE,
    CONF_REMOTE,
    CONF_TARGET_TEMP,
    CONF_TEMP_SENSOR,
    CONF_TEMPERATURES,
    CONF_UP_CODE,
    DOMAIN,
)
from .helpers import async_send_code


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a climate entity for each configured climate."""
    climates = entry.options.get(CONF_CLIMATES, [])
    async_add_entities(VirtualRfirClimate(entry, climate) for climate in climates)


class VirtualRfirClimate(ClimateEntity, RestoreEntity):
    """An optimistic thermostat with relative IR/RF temperature control."""

    _attr_has_entity_name = True
    _attr_assumed_state = True
    # Opt in to the modern turn_on/turn_off behavior (no legacy shim).
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, entry: ConfigEntry, climate: dict[str, Any]) -> None:
        """Initialize the climate entity from a stored definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._device: str | None = entry.data.get(CONF_DEVICE)
        # Each mode/step is the name of a command learned in the device group.
        self._off_command: str | None = climate.get(CONF_OFF_CODE)
        self._heat_command: str | None = climate.get(CONF_HEAT_CODE)
        self._cool_command: str | None = climate.get(CONF_COOL_CODE)
        self._up_command: str | None = climate.get(CONF_UP_CODE)
        self._down_command: str | None = climate.get(CONF_DOWN_CODE)
        self._temp_sensor: str | None = climate.get(CONF_TEMP_SENSOR)

        # Sorted, de-duplicated list of selectable target temperatures.
        self._temps = sorted({float(t) for t in climate.get(CONF_TEMPERATURES, [])})

        modes = [HVACMode.OFF]
        if climate.get(CONF_HEAT):
            modes.append(HVACMode.HEAT)
        if climate.get(CONF_COOL):
            modes.append(HVACMode.COOL)
        self._attr_hvac_modes = modes

        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if self._temps:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_min_temp = self._temps[0]
            self._attr_max_temp = self._temps[-1]
            gaps = [b - a for a, b in zip(self._temps, self._temps[1:])]
            self._attr_target_temperature_step = min(gaps) if gaps else 1.0
        self._attr_supported_features = features

        self._attr_name = climate[CONF_NAME]
        self._attr_icon = climate.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_climate_{climate[CONF_ID]}"
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = None
        default_target = climate.get(CONF_TARGET_TEMP)
        if default_target is not None:
            self._attr_target_temperature = float(default_target)
        elif self._temps:
            self._attr_target_temperature = self._temps[0]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )

    @property
    def temperature_unit(self) -> str:
        """Follow the Home Assistant system temperature unit."""
        return self.hass.config.units.temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Return the linked sensor's reading, or the target if none is set."""
        if self._temp_sensor is None:
            return self._attr_target_temperature
        state = self.hass.states.get(self._temp_sensor)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    async def async_added_to_hass(self) -> None:
        """Restore assumed state and start watching any linked sensor."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(last_state.state)
            target = last_state.attributes.get(ATTR_TEMPERATURE)
            if target is not None:
                self._attr_target_temperature = float(target)

        if self._temp_sensor is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._temp_sensor], self._async_sensor_changed
                )
            )

    @callback
    def _async_sensor_changed(self, event: Event) -> None:
        """Refresh state when the linked temperature sensor changes."""
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch mode, sending the code for the requested mode."""
        if hvac_mode == self._attr_hvac_mode or hvac_mode not in self._attr_hvac_modes:
            return
        command = {
            HVACMode.HEAT: self._heat_command,
            HVACMode.COOL: self._cool_command,
            HVACMode.OFF: self._off_command,
        }.get(hvac_mode)
        await async_send_code(self.hass, self._remote_entity_id, command, self._device)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on to the first available active mode (heat preferred)."""
        for mode in (HVACMode.HEAT, HVACMode.COOL):
            if mode in self._attr_hvac_modes:
                await self.async_set_hvac_mode(mode)
                return

    async def async_turn_off(self) -> None:
        """Turn the unit off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Step the target to the nearest listed temperature via up/down codes.

        The up/down codes are relative and only take effect while the unit is
        running, so temperature changes are ignored when it's off (turn it on to
        a mode first). This also keeps the assumed target from drifting away
        from the appliance while off.
        """
        requested = kwargs.get(ATTR_TEMPERATURE)
        if requested is None or not self._temps:
            return

        if self._attr_hvac_mode == HVACMode.OFF:
            # Snap the dial back to the unchanged target.
            self.async_write_ha_state()
            return

        new_value = min(self._temps, key=lambda t: abs(t - float(requested)))
        current = self._attr_target_temperature
        current_value = (
            min(self._temps, key=lambda t: abs(t - current))
            if current is not None
            else self._temps[0]
        )
        delta = self._temps.index(new_value) - self._temps.index(current_value)

        command = self._up_command if delta > 0 else self._down_command
        for _ in range(abs(delta)):
            await async_send_code(
                self.hass, self._remote_entity_id, command, self._device
            )

        self._attr_target_temperature = new_value
        self.async_write_ha_state()
