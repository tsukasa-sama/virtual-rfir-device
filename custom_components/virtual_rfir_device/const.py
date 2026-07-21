"""Constants for the Virtual RF/IR Device integration."""

from __future__ import annotations

DOMAIN = "virtual_rfir_device"

# Config entry data keys
CONF_REMOTE = "remote"

# Options keys (top-level lists)
CONF_CODES = "codes"
CONF_BUTTONS = "buttons"
CONF_SWITCHES = "switches"
CONF_LIGHTS = "lights"

# Shared item keys
CONF_ID = "id"
CONF_ICON = "icon"

# Code-library entry keys
CONF_CODE = "code"

# Button entry keys
CONF_CODE_ID = "code_id"

# Switch and light power keys
CONF_ON_CODE = "on_code"
CONF_OFF_CODE = "off_code"

# Light brightness-level keys
CONF_LEVELS = "levels"
CONF_PERCENT = "percent"

# Device metadata
MANUFACTURER = "Virtual RF/IR"
