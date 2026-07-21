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


def codes_by_id(codes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index a list of code-library entries by their id."""
    return {code[CONF_ID]: code for code in codes}


def resolve_code(
    codes: list[dict[str, Any]], code_id: str | None
) -> str | None:
    """Return the Base64 string for a referenced code id, or ``None``."""
    if code_id is None:
        return None
    entry = codes_by_id(codes).get(code_id)
    if entry is None:
        return None
    return entry.get(CONF_CODE)
