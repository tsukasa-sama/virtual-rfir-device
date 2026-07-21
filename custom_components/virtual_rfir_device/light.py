"""Light platform: optimistic dimmable lights built from IR/RF codes.

An IR light exposes a set of *absolute* brightness codes (e.g. 10%, 20%, ...,
100%). The brightness slider snaps to the nearest configured level and sends
that code. Power is handled by an on/off (or toggle) code, and brightness codes
are only sent once the light is on, since the appliance requires power first.

Like the other entities here, lights are assumed-state: Home Assistant only
remembers the last command it sent and can drift if the physical remote is used.
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
    CONF_CODES,
    CONF_ICON,
    CONF_ID,
    CONF_LEVELS,
    CONF_LIGHTS,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_PERCENT,
    CONF_REMOTE,
    DOMAIN,
)
from .helpers import async_send_code, resolve_code


def _pct_to_brightness(percent: int) -> int:
    """Convert a 0-100 percentage to a 0-255 brightness value."""
    return round(percent / 100 * 255)


def _brightness_to_pct(brightness: int) -> int:
    """Convert a 0-255 brightness value to a 0-100 percentage."""
    return round(brightness / 255 * 100)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a light entity for each configured light."""
    codes = entry.options.get(CONF_CODES, [])
    lights = entry.options.get(CONF_LIGHTS, [])
    async_add_entities(
        VirtualRfirLight(entry, light, codes) for light in lights
    )


class VirtualRfirLight(LightEntity, RestoreEntity):
    """An optimistic light with discrete IR/RF brightness levels."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        entry: ConfigEntry,
        light: dict[str, Any],
        codes: list[dict[str, Any]],
    ) -> None:
        """Initialize the light from a stored light definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._on_code = resolve_code(codes, light.get(CONF_ON_CODE))
        self._off_code = resolve_code(codes, light.get(CONF_OFF_CODE))

        # Resolve and sort the brightness levels: list of (percent, code).
        levels: list[tuple[int, str]] = []
        for level in light.get(CONF_LEVELS, []):
            code = resolve_code(codes, level.get(CONF_CODE_ID))
            percent = level.get(CONF_PERCENT)
            if code is not None and percent is not None:
                levels.append((int(percent), code))
        levels.sort(key=lambda item: item[0])
        self._levels = levels

        self._attr_name = light[CONF_NAME]
        self._attr_icon = light.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_light_{light[CONF_ID]}"
        self._attr_is_on = False
        self._attr_brightness: int | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )

        if self._levels:
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
        """Return the (percent, code) level closest to a 0-255 brightness."""
        target = _brightness_to_pct(brightness)
        return min(self._levels, key=lambda item: abs(item[0] - target))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Power on (if needed) and optionally set the nearest brightness.

        The appliance needs power before brightness codes take effect, so the
        on code is always sent first when the light was off.
        """
        if not self._attr_is_on and self._on_code is not None:
            await async_send_code(self.hass, self._remote_entity_id, self._on_code)
        self._attr_is_on = True

        if ATTR_BRIGHTNESS in kwargs and self._levels:
            percent, code = self._nearest_level(kwargs[ATTR_BRIGHTNESS])
            await async_send_code(self.hass, self._remote_entity_id, code)
            self._attr_brightness = _pct_to_brightness(percent)
        elif self._attr_brightness is None and self._levels:
            # No brightness known yet; display the highest configured level.
            self._attr_brightness = _pct_to_brightness(self._levels[-1][0])

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the off code and optimistically mark the light off."""
        if self._attr_is_on and self._off_code is not None:
            await async_send_code(self.hass, self._remote_entity_id, self._off_code)
        self._attr_is_on = False
        self.async_write_ha_state()
