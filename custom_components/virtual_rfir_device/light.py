"""Light platform: optimistic dimmable lights built from learned commands.

A light has one dimming mode:

* **preset** - the remote exposes a code per *absolute* brightness level (e.g.
  10%, 50%, 100%). The slider snaps to the nearest level and sends that code.
* **relative** - the remote exposes ``brightness_up`` / ``brightness_down``
  codes. The slider snaps to the nearest of an explicit list of percentages and
  steps up/down between them, exactly like the climate temperature dial.
* **none** - on/off only, no brightness.

Power is an on/off (or toggle) code, always sent before any brightness code
since the appliance needs power first. Brightness is inert while the light is
off: adjusting it snaps back and the light stays off (turn it on first). Like
the other entities here, lights are assumed-state and can drift if the physical
remote is used.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CODE_ID,
    CONF_DEVICE,
    CONF_DIM_MODE,
    CONF_DOWN_CODE,
    CONF_ICON,
    CONF_ID,
    CONF_LEVELS,
    CONF_LIGHTS,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_PERCENT,
    CONF_REMOTE,
    CONF_STEPS,
    CONF_UP_CODE,
    DIM_NONE,
    DIM_PRESET,
    DIM_RELATIVE,
    DOMAIN,
)
from .helpers import async_send_code


def _pct_to_brightness(percent: int) -> int:
    """Convert a 0-100 percentage to a 0-255 brightness value."""
    return round(percent / 100 * 255)


def _brightness_to_pct(brightness: int) -> int:
    """Convert a 0-255 brightness value to a 0-100 percentage."""
    return round(brightness / 255 * 100)


def _dim_mode(light: dict[str, Any]) -> str:
    """Return a light's dimming mode, inferring it for legacy lights."""
    mode = light.get(CONF_DIM_MODE)
    if mode:
        return mode
    return DIM_PRESET if light.get(CONF_LEVELS) else DIM_NONE


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a light entity for each configured light."""
    lights = entry.options.get(CONF_LIGHTS, [])
    async_add_entities(VirtualRfirLight(entry, light) for light in lights)


class VirtualRfirLight(LightEntity, RestoreEntity):
    """An optimistic light with preset or relative IR/RF brightness control."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, entry: ConfigEntry, light: dict[str, Any]) -> None:
        """Initialize the light from a stored light definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._device: str | None = entry.data.get(CONF_DEVICE)
        self._on_command: str | None = light.get(CONF_ON_CODE)
        self._off_command: str | None = light.get(CONF_OFF_CODE)
        self._dim_mode = _dim_mode(light)

        # Preset dimming: sorted (percent, command) absolute levels.
        levels: list[tuple[int, str]] = []
        for level in light.get(CONF_LEVELS, []):
            command = level.get(CONF_CODE_ID)
            percent = level.get(CONF_PERCENT)
            if command is not None and percent is not None:
                levels.append((int(percent), command))
        levels.sort(key=lambda item: item[0])
        self._levels = levels

        # Relative dimming: sorted percentage stops plus up/down commands.
        self._up_command: str | None = light.get(CONF_UP_CODE)
        self._down_command: str | None = light.get(CONF_DOWN_CODE)
        self._steps = sorted({int(s) for s in light.get(CONF_STEPS, [])})

        self._has_brightness = (
            self._dim_mode == DIM_PRESET and bool(self._levels)
        ) or (self._dim_mode == DIM_RELATIVE and bool(self._steps))

        self._attr_name = light[CONF_NAME]
        self._attr_icon = light.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_light_{light[CONF_ID]}"
        self._attr_is_on = False
        self._attr_brightness: int | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )

        if self._has_brightness:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state after a restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON
            brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
            if brightness is not None:
                self._attr_brightness = int(brightness)

    def _nearest_level(self, brightness: int) -> tuple[int, str]:
        """Return the preset (percent, command) level closest to a brightness."""
        target = _brightness_to_pct(brightness)
        return min(self._levels, key=lambda item: abs(item[0] - target))

    def _nearest_step(self, percent: int) -> int:
        """Return the relative step percentage closest to ``percent``."""
        return min(self._steps, key=lambda step: abs(step - percent))

    async def _async_apply_brightness(self, brightness: int) -> None:
        """Send the code(s) to reach a brightness and update assumed state."""
        if self._dim_mode == DIM_PRESET:
            percent, command = self._nearest_level(brightness)
            await async_send_code(
                self.hass, self._remote_entity_id, command, self._device
            )
            self._attr_brightness = _pct_to_brightness(percent)
        elif self._dim_mode == DIM_RELATIVE:
            new_value = self._nearest_step(_brightness_to_pct(brightness))
            current_value = (
                self._nearest_step(_brightness_to_pct(self._attr_brightness))
                if self._attr_brightness is not None
                else self._steps[0]
            )
            delta = self._steps.index(new_value) - self._steps.index(current_value)
            command = self._up_command if delta > 0 else self._down_command
            for _ in range(abs(delta)):
                await async_send_code(
                    self.hass, self._remote_entity_id, command, self._device
                )
            self._attr_brightness = _pct_to_brightness(new_value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Power on (if needed) and optionally set the brightness.

        Brightness is inert while off: a brightness request on an off light snaps
        back and the light stays off. A plain turn-on (no brightness) powers it
        on. Once on, brightness requests take effect.
        """
        if not self._attr_is_on and ATTR_BRIGHTNESS in kwargs:
            self.async_write_ha_state()
            return

        if not self._attr_is_on:
            await async_send_code(
                self.hass, self._remote_entity_id, self._on_command, self._device
            )
        self._attr_is_on = True

        if self._has_brightness:
            if ATTR_BRIGHTNESS in kwargs:
                await self._async_apply_brightness(kwargs[ATTR_BRIGHTNESS])
            elif self._attr_brightness is None:
                # Just powered on with no known level; show a sensible default:
                # highest preset level, or the lowest relative step as a baseline.
                default_pct = (
                    self._levels[-1][0]
                    if self._dim_mode == DIM_PRESET
                    else self._steps[0]
                )
                self._attr_brightness = _pct_to_brightness(default_pct)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the off command and optimistically mark the light off."""
        if self._attr_is_on:
            await async_send_code(
                self.hass, self._remote_entity_id, self._off_command, self._device
            )
        self._attr_is_on = False
        self.async_write_ha_state()
