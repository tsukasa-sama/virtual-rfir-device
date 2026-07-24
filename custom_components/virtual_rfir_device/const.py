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

# Device-wide setting: milliseconds to wait between consecutive relative ticks
# (climate temperature up/down, relative light dimming) so the appliance
# registers each press. Sends are already serialized per entity; this adds a
# gap on top of the transmission time.
CONF_STEP_DELAY = "step_delay"
DEFAULT_STEP_DELAY_MS = 100

# Shared item keys
CONF_ID = "id"
CONF_ICON = "icon"

# Control command keys. Each holds the *name* of a command learned on the remote
# within the entry's selected device group; it's transmitted by that name.
CONF_CODE_ID = "code_id"
CONF_ON_CODE = "on_code"
CONF_OFF_CODE = "off_code"

# Light dimming. A light is one mode:
#   DIM_NONE     - on/off only, no brightness
#   DIM_PRESET   - absolute per-level codes (CONF_LEVELS)
#   DIM_RELATIVE - brightness up/down codes (CONF_UP_CODE/CONF_DOWN_CODE) stepped
#                  across an explicit list of percentages (CONF_STEPS)
CONF_DIM_MODE = "dim_mode"
DIM_NONE = "none"
DIM_PRESET = "preset"
DIM_RELATIVE = "relative"

# Power-on brightness behavior (dimmable lights only):
#   ON_RESUME - send only the on code; the device resumes its own last level
#   ON_FULL   - drive to full brightness on power-on
CONF_ON_BEHAVIOR = "on_behavior"
ON_RESUME = "resume"
ON_FULL = "full"

# Light brightness-level keys (preset mode)
CONF_LEVELS = "levels"
CONF_PERCENT = "percent"
# Relative-mode selectable brightness percentages (need not be evenly spaced).
CONF_STEPS = "steps"
# Light effects: named commands (colors, scenes, ...) exposed as the light's
# effect list. Each entry is {CONF_NAME, CONF_CODE_ID}.
CONF_EFFECTS = "effects"

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
