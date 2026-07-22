"""Climate platform: optimistic thermostats built from IR/RF codes.

An IR heater typically exposes a heat on/off (or toggle) code plus *relative*
temperature up/down codes. This entity keeps a virtual target temperature: when
you change the target, it fires the up/down code once per step to cover the
difference. Heat mode is driven by the on/off code.

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
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CLIMATES,
    CONF_CODES,
    CONF_DOWN_CODE,
    CONF_ICON,
    CONF_ID,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_REMOTE,
    CONF_TARGET_TEMP,
    CONF_TEMP_SENSOR,
    CONF_TEMP_STEP,
    CONF_UP_CODE,
    DOMAIN,
)
from .helpers import async_send_code, resolve_code


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a climate entity for each configured climate."""
    codes = entry.options.get(CONF_CODES, [])
    climates = entry.options.get(CONF_CLIMATES, [])
    async_add_entities(
        VirtualRfirClimate(entry, climate, codes) for climate in climates
    )


class VirtualRfirClimate(ClimateEntity, RestoreEntity):
    """An optimistic heater with relative IR/RF temperature control."""

    _attr_has_entity_name = True
    _attr_assumed_state = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    # Opt in to the modern turn_on/turn_off behavior (no legacy shim).
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        entry: ConfigEntry,
        climate: dict[str, Any],
        codes: list[dict[str, Any]],
    ) -> None:
        """Initialize the climate entity from a stored definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._on_code = resolve_code(codes, climate.get(CONF_ON_CODE))
        self._off_code = resolve_code(codes, climate.get(CONF_OFF_CODE))
        self._up_code = resolve_code(codes, climate.get(CONF_UP_CODE))
        self._down_code = resolve_code(codes, climate.get(CONF_DOWN_CODE))
        self._temp_sensor: str | None = climate.get(CONF_TEMP_SENSOR)

        self._attr_name = climate[CONF_NAME]
        self._attr_icon = climate.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_climate_{climate[CONF_ID]}"
        self._attr_min_temp = float(climate[CONF_MIN_TEMP])
        self._attr_max_temp = float(climate[CONF_MAX_TEMP])
        self._attr_target_temperature_step = float(climate[CONF_TEMP_STEP])
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(
            climate.get(CONF_TARGET_TEMP, climate[CONF_MIN_TEMP])
        )
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
            if last_state.state in (HVACMode.OFF, HVACMode.HEAT):
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
        """Turn heat on or off, guarding the toggle against double-firing."""
        if hvac_mode == self._attr_hvac_mode:
            return
        if hvac_mode == HVACMode.HEAT:
            if self._on_code is not None:
                await async_send_code(self.hass, self._remote_entity_id, self._on_code)
        elif self._off_code is not None:
            await async_send_code(self.hass, self._remote_entity_id, self._off_code)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn heat on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn heat off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Step the target toward the requested temperature via up/down codes."""
        target = kwargs.get(ATTR_TEMPERATURE)
        if target is None:
            return
        target = min(max(float(target), self._attr_min_temp), self._attr_max_temp)

        step = self._attr_target_temperature_step or 1.0
        current = self._attr_target_temperature or self._attr_min_temp
        delta_steps = round((target - current) / step)

        code = self._up_code if delta_steps > 0 else self._down_code
        if code is not None:
            for _ in range(abs(delta_steps)):
                await async_send_code(self.hass, self._remote_entity_id, code)

        # Land on the exact stepped value we actually commanded.
        self._attr_target_temperature = current + delta_steps * step
        self.async_write_ha_state()
