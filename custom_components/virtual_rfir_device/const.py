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

# Climate keys (on_code/off_code above are reused for heat on/off/toggle)
CONF_UP_CODE = "up_code"
CONF_DOWN_CODE = "down_code"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TEMP_STEP = "temp_step"
CONF_TARGET_TEMP = "target_temp"
CONF_TEMP_SENSOR = "temp_sensor"

# Device metadata
MANUFACTURER = "Virtual RF/IR"
