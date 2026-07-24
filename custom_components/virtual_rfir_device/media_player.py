"""Media-player platform: optimistic TVs / receivers from IR/RF commands.

An IR TV or AV receiver is driven by discrete and relative commands (power,
volume up/down, mute, input select, sound mode, transport). This entity maps
those to a Home Assistant media player. Volume is step-only (up/down) since IR
carries no absolute level or feedback.

Like the other entities here it's assumed-state: it only remembers the last
command it sent and can drift if the physical remote is used.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CODE_ID,
    CONF_DEVICE,
    CONF_ICON,
    CONF_ID,
    CONF_MEDIA_PLAYERS,
    CONF_MUTE_CODE,
    CONF_NEXT_CODE,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_PAUSE_CODE,
    CONF_PLAY_CODE,
    CONF_PREVIOUS_CODE,
    CONF_REMOTE,
    CONF_SOUND_MODES,
    CONF_SOURCES,
    CONF_STOP_CODE,
    CONF_VOLUME_DOWN_CODE,
    CONF_VOLUME_UP_CODE,
    DOMAIN,
)
from .helpers import async_send_code


def _named_commands(items: list[dict[str, Any]]) -> dict[str, str]:
    """Return an ordered {name: command} map from a list of named entries."""
    mapping: dict[str, str] = {}
    for item in items:
        name = item.get(CONF_NAME)
        command = item.get(CONF_CODE_ID)
        if name and command:
            mapping[name] = command
    return mapping


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a media-player entity for each configured media player."""
    players = entry.options.get(CONF_MEDIA_PLAYERS, [])
    async_add_entities(VirtualRfirMediaPlayer(entry, player) for player in players)


class VirtualRfirMediaPlayer(MediaPlayerEntity, RestoreEntity):
    """An optimistic media player built from learned IR/RF commands."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, entry: ConfigEntry, player: dict[str, Any]) -> None:
        """Initialize the media player from a stored definition."""
        self._remote_entity_id: str = entry.data[CONF_REMOTE]
        self._device: str | None = entry.data.get(CONF_DEVICE)

        self._on_command: str | None = player.get(CONF_ON_CODE)
        self._off_command: str | None = player.get(CONF_OFF_CODE)
        self._volume_up: str | None = player.get(CONF_VOLUME_UP_CODE)
        self._volume_down: str | None = player.get(CONF_VOLUME_DOWN_CODE)
        self._mute: str | None = player.get(CONF_MUTE_CODE)
        self._play: str | None = player.get(CONF_PLAY_CODE)
        self._pause: str | None = player.get(CONF_PAUSE_CODE)
        self._stop: str | None = player.get(CONF_STOP_CODE)
        self._next: str | None = player.get(CONF_NEXT_CODE)
        self._previous: str | None = player.get(CONF_PREVIOUS_CODE)

        self._sources = _named_commands(player.get(CONF_SOURCES, []))
        self._sound_modes = _named_commands(player.get(CONF_SOUND_MODES, []))

        self._attr_name = player[CONF_NAME]
        self._attr_icon = player.get(CONF_ICON)
        self._attr_unique_id = f"{entry.entry_id}_media_player_{player[CONF_ID]}"
        self._attr_state = MediaPlayerState.OFF
        self._attr_is_volume_muted = False
        self._attr_source_list = list(self._sources) or None
        self._attr_source: str | None = None
        self._attr_sound_mode_list = list(self._sound_modes) or None
        self._attr_sound_mode: str | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
        )

        features = (
            MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
        )
        if self._volume_up and self._volume_down:
            features |= MediaPlayerEntityFeature.VOLUME_STEP
        if self._mute:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self._sources:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self._sound_modes:
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
        if self._play:
            features |= MediaPlayerEntityFeature.PLAY
        if self._pause:
            features |= MediaPlayerEntityFeature.PAUSE
        if self._stop:
            features |= MediaPlayerEntityFeature.STOP
        if self._next:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if self._previous:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        self._attr_supported_features = features

    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state after a restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is None:
            return
        try:
            self._attr_state = MediaPlayerState(last_state.state)
        except ValueError:
            self._attr_state = MediaPlayerState.OFF
        self._attr_is_volume_muted = bool(
            last_state.attributes.get(ATTR_MEDIA_VOLUME_MUTED)
        )
        if (source := last_state.attributes.get(ATTR_INPUT_SOURCE)) in self._sources:
            self._attr_source = source
        if (mode := last_state.attributes.get(ATTR_SOUND_MODE)) in self._sound_modes:
            self._attr_sound_mode = mode

    async def _async_send(self, command: str | None) -> None:
        """Transmit a command through the configured remote."""
        await async_send_code(
            self.hass, self._remote_entity_id, command, self._device
        )

    async def async_turn_on(self) -> None:
        """Power on and optimistically mark the player on."""
        await self._async_send(self._on_command)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Power off and optimistically mark the player off."""
        await self._async_send(self._off_command)
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Send the volume-up command."""
        await self._async_send(self._volume_up)

    async def async_volume_down(self) -> None:
        """Send the volume-down command."""
        await self._async_send(self._volume_down)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute toggle and flip the assumed mute state."""
        await self._async_send(self._mute)
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Send the command for the chosen input source."""
        if (command := self._sources.get(source)) is None:
            return
        await self._async_send(command)
        self._attr_source = source
        self.async_write_ha_state()

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Send the command for the chosen sound mode."""
        if (command := self._sound_modes.get(sound_mode)) is None:
            return
        await self._async_send(command)
        self._attr_sound_mode = sound_mode
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Send the play command."""
        await self._async_send(self._play)
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Send the pause command."""
        await self._async_send(self._pause)
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Send the stop command."""
        await self._async_send(self._stop)
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Send the next-track command."""
        await self._async_send(self._next)

    async def async_media_previous_track(self) -> None:
        """Send the previous-track command."""
        await self._async_send(self._previous)
