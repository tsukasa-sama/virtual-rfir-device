"""Constants for the Virtual RF/IR Device integration."""

from __future__ import annotations

DOMAIN = "virtual_rfir_device"

# Config entry data keys
CONF_REMOTE = "remote"
# The learned-command group (a Broadlink "device", i.e. a top-level key in the
# remote's codes store) this virtual device represents. Chosen at setup; only
# this group's commands are offered when building controls, and it's passed as
# the ``device`` argument when transmitting.
CONF_DEVICE = "device"

# Options keys (top-level lists)
CONF_BUTTONS = "buttons"
CONF_SWITCHES = "switches"
CONF_LIGHTS = "lights"
CONF_CLIMATES = "climates"

# Shared item keys
CONF_ID = "id"
CONF_ICON = "icon"

# Control command keys. Each holds the *name* of a command learned on the remote
# within the entry's selected device group; it's transmitted by that name.
CONF_CODE_ID = "code_id"
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
