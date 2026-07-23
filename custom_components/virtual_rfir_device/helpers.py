"""Shared helpers for the Virtual RF/IR Device integration."""

from __future__ import annotations

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DEVICE,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def async_send_code(
    hass: HomeAssistant,
    remote_entity_id: str,
    command: str | None,
    device: str | None = None,
) -> None:
    """Transmit a learned command by name through the given remote entity.

    Commands are sent by name (within the entry's device group) so the remote
    (e.g. Broadlink) resolves the code it currently has stored — re-learning a
    command stays in sync with no reconfiguration here. Does nothing if no
    command is given.
    """
    if not command:
        return

    data: dict[str, object] = {
        ATTR_ENTITY_ID: remote_entity_id,
        ATTR_COMMAND: command,
    }
    if device:
        data[ATTR_DEVICE] = device

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_SEND_COMMAND, data, blocking=True
    )
