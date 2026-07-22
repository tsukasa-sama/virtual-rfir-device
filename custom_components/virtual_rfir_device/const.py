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
CONF_CLIMATES = "climates"

# Shared item keys
CONF_ID = "id"
CONF_ICON = "icon"

# Code-library entry keys.
# A code is either a raw Base64 payload (CONF_CODE) or a reference to a
# learned Broadlink command (CONF_DEVICE + CONF_COMMAND).
CONF_CODE = "code"
CONF_DEVICE = "device"
CONF_COMMAND = "command"

# Button entry keys
CONF_CODE_ID = "code_id"

# Switch and light power keys
CONF_ON_CODE = "on_code"
CONF_OFF_CODE = "off_code"

# Light brightness-level keys
CONF_LEVELS = "levels"
CONF_PERCENT = "percent"

# Climate keys. off_code (above) turns the unit off / is the mode-off toggle.
CONF_HEAT = "heat"
CONF_COOL = "cool"
CONF_HEAT_CODE = "heat_code"
CONF_COOL_CODE = "cool_code"
CONF_UP_CODE = "up_code"
CONF_DOWN_CODE = "down_code"
# Explicit list of selectable target temperatures (need not be evenly spaced).
CONF_TEMPERATURES = "temperatures"
CONF_TARGET_TEMP = "target_temp"
CONF_TEMP_SENSOR = "temp_sensor"

# Device metadata
MANUFACTURER = "Virtual RF/IR"
