"""Shared helpers for the Virtual RF/IR Device integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .const import CONF_CODE, CONF_ID


async def async_send_code(
    hass: HomeAssistant, remote_entity_id: str, code: str
) -> None:
    """Transmit a raw IR/RF code through the given remote entity.

    A ``b64:`` prefix is added automatically when missing so pasted Base64
    codes work as-is.
    """
    command = code if code.startswith("b64:") else f"b64:{code}"
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: remote_entity_id,
            ATTR_COMMAND: command,
        },
        blocking=True,
    )


def commands_by_id(commands: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index a list of command definitions by their id."""
    return {command[CONF_ID]: command for command in commands}


def code_for_command(
    commands: list[dict[str, Any]], command_id: str | None
) -> str | None:
    """Return the code for a referenced command id, or ``None`` if missing."""
    if command_id is None:
        return None
    command = commands_by_id(commands).get(command_id)
    if command is None:
        return None
    return command.get(CONF_CODE)
