"""Shared helpers for the Virtual RF/IR Device integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DEVICE,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .const import CONF_CODE, CONF_COMMAND, CONF_DEVICE, CONF_ID


async def async_send_code(
    hass: HomeAssistant,
    remote_entity_id: str,
    code_entry: dict[str, Any] | None,
) -> None:
    """Transmit a code through the given remote entity.

    A code entry is either a raw Base64 payload (``CONF_CODE``) or a reference
    to a learned command (``CONF_DEVICE`` + ``CONF_COMMAND``). Raw codes get a
    ``b64:`` prefix when missing; references are sent by name so the remote
    (e.g. Broadlink) resolves the stored code itself.
    """
    if not code_entry:
        return

    data: dict[str, Any] = {ATTR_ENTITY_ID: remote_entity_id}
    if CONF_CODE in code_entry:
        value = code_entry[CONF_CODE]
        data[ATTR_COMMAND] = value if value.startswith("b64:") else f"b64:{value}"
    elif CONF_COMMAND in code_entry:
        data[ATTR_COMMAND] = code_entry[CONF_COMMAND]
        if device := code_entry.get(CONF_DEVICE):
            data[ATTR_DEVICE] = device
    else:
        return

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_SEND_COMMAND, data, blocking=True
    )


def codes_by_id(codes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index a list of code-library entries by their id."""
    return {code[CONF_ID]: code for code in codes}


def resolve_code_entry(
    codes: list[dict[str, Any]], code_id: str | None
) -> dict[str, Any] | None:
    """Return the code-library entry for a referenced id, or ``None``."""
    if code_id is None:
        return None
    return codes_by_id(codes).get(code_id)
