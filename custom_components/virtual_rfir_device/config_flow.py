"""Config and options flows for the Virtual RF/IR Device integration."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BUTTONS,
    CONF_CLIMATES,
    CONF_CODE,
    CONF_CODE_ID,
    CONF_CODES,
    CONF_COMMAND,
    CONF_COOL,
    CONF_COOL_CODE,
    CONF_DEVICE,
    CONF_DOWN_CODE,
    CONF_HEAT,
    CONF_HEAT_CODE,
    CONF_ICON,
    CONF_ID,
    CONF_LEVELS,
    CONF_LIGHTS,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_PERCENT,
    CONF_REMOTE,
    CONF_SWITCHES,
    CONF_TARGET_TEMP,
    CONF_TEMP_SENSOR,
    CONF_TEMPERATURES,
    CONF_UP_CODE,
    DOMAIN,
)


# Field key for the import multi-select, and the delimiter used to pack a
# (device, command) pair into a single select value (0x1f = ASCII unit
# separator, which won't appear in a learned command name).
CONF_SELECTION = "selection"
_IMPORT_DELIM = "\x1f"


def _as_options(items: list[dict[str, Any]]) -> list[selector.SelectOptionDict]:
    """Return items as id/name select options."""
    return [
        selector.SelectOptionDict(value=item[CONF_ID], label=item[CONF_NAME])
        for item in items
    ]


def _find_by_id(
    items: list[dict[str, Any]], item_id: str | None
) -> dict[str, Any] | None:
    """Return the item with the given id, or ``None``."""
    return next((item for item in items if item[CONF_ID] == item_id), None)


def _set_optional(item: dict[str, Any], key: str, value: Any) -> None:
    """Set ``key`` on ``item`` if ``value`` is truthy, otherwise remove it."""
    if value:
        item[key] = value
    else:
        item.pop(key, None)


class VirtualRfirDeviceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for creating a virtual RF/IR device."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: name the appliance and pick its remote."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_REMOTE: user_input[CONF_REMOTE],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_REMOTE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="remote")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow used to manage this device's contents."""
        return VirtualRfirDeviceOptionsFlow()


class VirtualRfirDeviceOptionsFlow(OptionsFlow):
    """Manage the codes, buttons, and switches of a virtual RF/IR device.

    Codes are a data-only library of IR/RF codes; they create no entities on
    their own. Buttons and switches are the entities, composed by referencing
    codes.
    """

    def __init__(self) -> None:
        """Initialize the options flow with lazily-loaded working copies."""
        self._codes: list[dict[str, Any]] | None = None
        self._buttons: list[dict[str, Any]] | None = None
        self._switches: list[dict[str, Any]] | None = None
        self._lights: list[dict[str, Any]] | None = None
        self._climates: list[dict[str, Any]] | None = None
        # Learned commands available on the remote, as {device: {command: code}}.
        # None until first loaded; {} if the remote has none / can't be read.
        self._learned: dict[str, Any] | None = None
        # Id of the item currently being edited (set by an edit-select step),
        # also used as the "current light" while editing its brightness levels.
        self._edit_id: str | None = None

    def _load(self) -> None:
        """Load the current options into editable working copies once."""
        options = self.config_entry.options
        if self._codes is None:
            self._codes = [dict(item) for item in options.get(CONF_CODES, [])]
        if self._buttons is None:
            self._buttons = [dict(item) for item in options.get(CONF_BUTTONS, [])]
        if self._switches is None:
            self._switches = [dict(item) for item in options.get(CONF_SWITCHES, [])]
        if self._lights is None:
            # Deep-copy lights so their nested level lists are editable copies.
            self._lights = [
                {**item, CONF_LEVELS: [dict(lvl) for lvl in item.get(CONF_LEVELS, [])]}
                for item in options.get(CONF_LIGHTS, [])
            ]
        if self._climates is None:
            self._climates = [dict(item) for item in options.get(CONF_CLIMATES, [])]

    def _code_options(self) -> list[selector.SelectOptionDict]:
        """Return the code library as select options."""
        assert self._codes is not None
        return _as_options(self._codes)

    def _code_name(self, code_id: str) -> str:
        """Return the display name of a code id, or a placeholder."""
        code = _find_by_id(self._codes or [], code_id)
        return code[CONF_NAME] if code else "?"

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the top-level menu for managing the device's contents."""
        self._load()
        assert self._codes is not None
        assert self._buttons is not None
        assert self._switches is not None
        assert self._lights is not None

        if self._learned is None:
            self._learned = await self._async_load_learned()

        menu_options = ["add_code", "add_reference"]
        if self._learned:
            menu_options.append("import_codes")
        if self._codes:
            menu_options += ["edit_code", "remove_code"]
            # Entities reference codes, so require codes first.
            menu_options.append("add_button")
        if self._buttons:
            menu_options += ["edit_button", "remove_button"]
        if self._codes:
            menu_options.append("add_switch")
        if self._switches:
            menu_options += ["edit_switch", "remove_switch"]
        if self._codes:
            menu_options.append("add_light")
        if self._lights:
            menu_options += ["edit_light", "remove_light"]
        if self._codes:
            menu_options.append("add_climate")
        if self._climates:
            menu_options += ["edit_climate", "remove_climate"]
        menu_options.append("finish")
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    # --- Codes -------------------------------------------------------------

    async def async_step_add_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add an IR/RF code to the library (creates no entity)."""
        self._load()
        assert self._codes is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            code = user_input[CONF_CODE].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not code:
                errors[CONF_CODE] = "code_required"
            else:
                self._codes.append(
                    {CONF_ID: uuid.uuid4().hex, CONF_NAME: name, CONF_CODE: code}
                )
                return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_CODE): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="add_code",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_add_reference(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a code that references a command already learned on the remote.

        Works with any remote whose ``send_command`` accepts a command name
        (Broadlink, Xiaomi, SwitchBot, ...). Leave the device blank for remotes
        that don't group commands under a device.
        """
        self._load()
        assert self._codes is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            command = user_input[CONF_COMMAND].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not command:
                errors[CONF_COMMAND] = "code_required"
            else:
                reference = {
                    CONF_ID: uuid.uuid4().hex,
                    CONF_NAME: name,
                    CONF_COMMAND: command,
                }
                if device := (user_input.get(CONF_DEVICE) or "").strip():
                    reference[CONF_DEVICE] = device
                self._codes.append(reference)
                return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_DEVICE): selector.TextSelector(),
                vol.Required(CONF_COMMAND): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="add_reference",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def _async_load_learned(self) -> dict[str, Any]:
        """Load learned commands for the configured remote (Broadlink store).

        Returns ``{device: {command: code}}`` or an empty dict if the remote
        isn't a Broadlink (or has no learned commands / can't be read).
        """
        remote_entity_id = self.config_entry.data[CONF_REMOTE]
        entity_registry = er.async_get(self.hass)
        remote_entry = entity_registry.async_get(remote_entity_id)
        if remote_entry is None or remote_entry.device_id is None:
            return {}

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get(remote_entry.device_id)
        if device is None:
            return {}

        mac = next(
            (
                value.replace(":", "").lower()
                for conn_type, value in device.connections
                if conn_type == CONNECTION_NETWORK_MAC
            ),
            None,
        )
        if mac is None:
            return {}

        store: Store = Store(self.hass, 1, f"broadlink_remote_{mac}_codes")
        data = await store.async_load()
        return data if isinstance(data, dict) else {}

    async def async_step_import_codes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import learned commands from the remote as reference codes."""
        self._load()
        assert self._codes is not None
        learned = self._learned or {}

        if user_input is not None:
            existing = {
                (code.get(CONF_DEVICE), code.get(CONF_COMMAND))
                for code in self._codes
                if CONF_COMMAND in code
            }
            for token in user_input.get(CONF_SELECTION, []):
                device, command = token.split(_IMPORT_DELIM, 1)
                if (device, command) in existing:
                    continue
                self._codes.append(
                    {
                        CONF_ID: uuid.uuid4().hex,
                        CONF_NAME: command,
                        CONF_DEVICE: device,
                        CONF_COMMAND: command,
                    }
                )
            return await self.async_step_init()

        options = [
            selector.SelectOptionDict(
                value=f"{device}{_IMPORT_DELIM}{command}",
                label=f"{device}: {command}",
            )
            for device, commands in learned.items()
            for command in commands
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTION): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="import_codes", data_schema=schema)

    async def async_step_remove_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more codes from the library."""
        self._load()
        assert self._codes is not None

        if user_input is not None:
            to_remove = set(user_input.get(CONF_CODES, []))
            self._codes = [
                code for code in self._codes if code[CONF_ID] not in to_remove
            ]
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_CODES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._code_options(),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_code", data_schema=schema)

    async def async_step_edit_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a code to edit, then open its hub."""
        self._load()
        assert self._codes is not None

        if user_input is not None:
            self._edit_id = user_input[CONF_ID]
            return await self.async_step_manage_code()

        schema = vol.Schema(
            {
                vol.Required(CONF_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self._code_options())
                )
            }
        )
        return self.async_show_form(step_id="edit_code", data_schema=schema)

    async def async_step_manage_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub for the selected code."""
        if _find_by_id(self._codes or [], self._edit_id) is None:
            return await self.async_step_init()
        return self.async_show_menu(
            step_id="manage_code",
            menu_options=["edit_code_details", "done_edit"],
        )

    async def async_step_edit_code_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the selected code.

        Raw codes edit name + Base64; reference codes (imported from a remote)
        edit name + the learned device/command they point at.
        """
        self._load()
        assert self._codes is not None
        code = _find_by_id(self._codes, self._edit_id)
        if code is None:
            return await self.async_step_init()

        is_reference = CONF_COMMAND in code
        payload_key = CONF_COMMAND if is_reference else CONF_CODE

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            payload = user_input[payload_key].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not payload:
                errors[payload_key] = "code_required"
            else:
                code[CONF_NAME] = name
                code[payload_key] = payload
                if is_reference:
                    _set_optional(code, CONF_DEVICE, user_input.get(CONF_DEVICE))
                return await self.async_step_manage_code()

        if is_reference:
            schema = vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Optional(CONF_DEVICE): selector.TextSelector(),
                    vol.Required(CONF_COMMAND): selector.TextSelector(),
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(CONF_CODE): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                }
            )
        return self.async_show_form(
            step_id="edit_code_details",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else code
            ),
            errors=errors,
        )

    # --- Buttons -----------------------------------------------------------

    async def async_step_add_button(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a button entity that sends a code from the library."""
        self._load()
        assert self._codes is not None
        assert self._buttons is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                button = {
                    CONF_ID: uuid.uuid4().hex,
                    CONF_NAME: name,
                    CONF_CODE_ID: user_input[CONF_CODE_ID],
                }
                if icon := user_input.get(CONF_ICON):
                    button[CONF_ICON] = icon
                self._buttons.append(button)
                return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Required(CONF_CODE_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self._code_options())
                ),
            }
        )
        return self.async_show_form(
            step_id="add_button",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_remove_button(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more button entities."""
        self._load()
        assert self._buttons is not None

        if user_input is not None:
            to_remove = set(user_input.get(CONF_BUTTONS, []))
            self._buttons = [
                button for button in self._buttons if button[CONF_ID] not in to_remove
            ]
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_BUTTONS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_as_options(self._buttons),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_button", data_schema=schema)

    async def async_step_edit_button(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a button to edit, then open its hub."""
        self._load()
        assert self._buttons is not None

        if user_input is not None:
            self._edit_id = user_input[CONF_ID]
            return await self.async_step_manage_button()

        schema = vol.Schema(
            {
                vol.Required(CONF_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=_as_options(self._buttons))
                )
            }
        )
        return self.async_show_form(step_id="edit_button", data_schema=schema)

    async def async_step_manage_button(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub for the selected button."""
        if _find_by_id(self._buttons or [], self._edit_id) is None:
            return await self.async_step_init()
        return self.async_show_menu(
            step_id="manage_button",
            menu_options=["edit_button_details", "done_edit"],
        )

    async def async_step_edit_button_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the selected button's name, icon, and code."""
        self._load()
        assert self._codes is not None
        assert self._buttons is not None
        button = _find_by_id(self._buttons, self._edit_id)
        if button is None:
            return await self.async_step_init()

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                button[CONF_NAME] = name
                button[CONF_CODE_ID] = user_input[CONF_CODE_ID]
                _set_optional(button, CONF_ICON, user_input.get(CONF_ICON))
                return await self.async_step_manage_button()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Required(CONF_CODE_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self._code_options())
                ),
            }
        )
        return self.async_show_form(
            step_id="edit_button_details",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else button
            ),
            errors=errors,
        )

    # --- Switches ----------------------------------------------------------

    async def async_step_add_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add an optimistic switch built from existing codes.

        Pick an ``on`` code and an ``off`` code. For a toggle-only appliance,
        choose the same code for both.
        """
        self._load()
        assert self._codes is not None
        assert self._switches is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                switch = {
                    CONF_ID: uuid.uuid4().hex,
                    CONF_NAME: name,
                    CONF_ON_CODE: user_input[CONF_ON_CODE],
                    CONF_OFF_CODE: user_input[CONF_OFF_CODE],
                }
                if icon := user_input.get(CONF_ICON):
                    switch[CONF_ICON] = icon
                self._switches.append(switch)
                return await self.async_step_init()

        code_select = selector.SelectSelector(
            selector.SelectSelectorConfig(options=self._code_options())
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Required(CONF_ON_CODE): code_select,
                vol.Required(CONF_OFF_CODE): code_select,
            }
        )
        return self.async_show_form(
            step_id="add_switch",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_remove_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more switch entities."""
        self._load()
        assert self._switches is not None

        if user_input is not None:
            to_remove = set(user_input.get(CONF_SWITCHES, []))
            self._switches = [
                switch for switch in self._switches if switch[CONF_ID] not in to_remove
            ]
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_SWITCHES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_as_options(self._switches),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_switch", data_schema=schema)

    async def async_step_edit_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a switch to edit, then open its hub."""
        self._load()
        assert self._switches is not None

        if user_input is not None:
            self._edit_id = user_input[CONF_ID]
            return await self.async_step_manage_switch()

        schema = vol.Schema(
            {
                vol.Required(CONF_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=_as_options(self._switches))
                )
            }
        )
        return self.async_show_form(step_id="edit_switch", data_schema=schema)

    async def async_step_manage_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub for the selected switch."""
        if _find_by_id(self._switches or [], self._edit_id) is None:
            return await self.async_step_init()
        return self.async_show_menu(
            step_id="manage_switch",
            menu_options=["edit_switch_details", "done_edit"],
        )

    async def async_step_edit_switch_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the selected switch's name, icon, and on/off codes."""
        self._load()
        assert self._codes is not None
        assert self._switches is not None
        switch = _find_by_id(self._switches, self._edit_id)
        if switch is None:
            return await self.async_step_init()

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                switch[CONF_NAME] = name
                switch[CONF_ON_CODE] = user_input[CONF_ON_CODE]
                switch[CONF_OFF_CODE] = user_input[CONF_OFF_CODE]
                _set_optional(switch, CONF_ICON, user_input.get(CONF_ICON))
                return await self.async_step_manage_switch()

        code_select = selector.SelectSelector(
            selector.SelectSelectorConfig(options=self._code_options())
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Required(CONF_ON_CODE): code_select,
                vol.Required(CONF_OFF_CODE): code_select,
            }
        )
        return self.async_show_form(
            step_id="edit_switch_details",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input if user_input is not None else switch
            ),
            errors=errors,
        )

    # --- Lights ------------------------------------------------------------

    def _current_light(self) -> dict[str, Any] | None:
        """Return the light currently being built or edited."""
        assert self._lights is not None
        return _find_by_id(self._lights, self._edit_id)

    def _light_power_schema(self) -> vol.Schema:
        """Return the schema for a light's name, icon, and power codes."""
        code_select = selector.SelectSelector(
            selector.SelectSelectorConfig(options=self._code_options())
        )
        return vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Required(CONF_ON_CODE): code_select,
                vol.Required(CONF_OFF_CODE): code_select,
            }
        )

    async def async_step_add_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a light: set power codes, then move on to brightness levels.

        For a toggle-only appliance, pick the same code for on and off.
        """
        self._load()
        assert self._codes is not None
        assert self._lights is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                light = {
                    CONF_ID: uuid.uuid4().hex,
                    CONF_NAME: name,
                    CONF_ON_CODE: user_input[CONF_ON_CODE],
                    CONF_OFF_CODE: user_input[CONF_OFF_CODE],
                    CONF_LEVELS: [],
                }
                if icon := user_input.get(CONF_ICON):
                    light[CONF_ICON] = icon
                self._lights.append(light)
                self._edit_id = light[CONF_ID]
                return await self.async_step_manage_light()

        return self.async_show_form(
            step_id="add_light",
            data_schema=self.add_suggested_values_to_schema(
                self._light_power_schema(), user_input
            ),
            errors=errors,
        )

    async def async_step_manage_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub for the selected light: power codes and brightness levels."""
        light = self._current_light()
        if light is None:
            return await self.async_step_init()

        menu_options = ["edit_light_details", "add_level"]
        if light.get(CONF_LEVELS):
            menu_options.append("remove_level")
        menu_options.append("done_edit")
        return self.async_show_menu(step_id="manage_light", menu_options=menu_options)

    async def async_step_add_level(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a brightness level (a code mapped to a percentage)."""
        self._load()
        assert self._codes is not None
        light = self._current_light()
        if light is None:
            return await self.async_step_init()

        if user_input is not None:
            light[CONF_LEVELS].append(
                {
                    CONF_ID: uuid.uuid4().hex,
                    CONF_CODE_ID: user_input[CONF_CODE_ID],
                    CONF_PERCENT: int(user_input[CONF_PERCENT]),
                }
            )
            return await self.async_step_manage_light()

        schema = vol.Schema(
            {
                vol.Required(CONF_CODE_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self._code_options())
                ),
                vol.Required(CONF_PERCENT): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=100, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="add_level", data_schema=schema)

    async def async_step_remove_level(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more brightness levels from the current light."""
        self._load()
        assert self._codes is not None
        light = self._current_light()
        if light is None:
            return await self.async_step_init()

        if user_input is not None:
            to_remove = set(user_input.get(CONF_LEVELS, []))
            light[CONF_LEVELS] = [
                level
                for level in light[CONF_LEVELS]
                if level[CONF_ID] not in to_remove
            ]
            return await self.async_step_manage_light()

        options = [
            selector.SelectOptionDict(
                value=level[CONF_ID],
                label=f"{level[CONF_PERCENT]}% — {self._code_name(level[CONF_CODE_ID])}",
            )
            for level in light[CONF_LEVELS]
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_LEVELS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_level", data_schema=schema)

    async def async_step_edit_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a light to edit, then open its hub."""
        self._load()
        assert self._lights is not None

        if user_input is not None:
            self._edit_id = user_input[CONF_ID]
            return await self.async_step_manage_light()

        schema = vol.Schema(
            {
                vol.Required(CONF_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=_as_options(self._lights))
                )
            }
        )
        return self.async_show_form(step_id="edit_light", data_schema=schema)

    async def async_step_edit_light_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the light's power codes."""
        self._load()
        assert self._codes is not None
        light = self._current_light()
        if light is None:
            return await self.async_step_init()

        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                light[CONF_NAME] = name
                light[CONF_ON_CODE] = user_input[CONF_ON_CODE]
                light[CONF_OFF_CODE] = user_input[CONF_OFF_CODE]
                _set_optional(light, CONF_ICON, user_input.get(CONF_ICON))
                return await self.async_step_manage_light()

        return self.async_show_form(
            step_id="edit_light_details",
            data_schema=self.add_suggested_values_to_schema(
                self._light_power_schema(),
                user_input if user_input is not None else light,
            ),
            errors=errors,
        )

    async def async_step_remove_light(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more light entities."""
        self._load()
        assert self._lights is not None

        if user_input is not None:
            to_remove = set(user_input.get(CONF_LIGHTS, []))
            self._lights = [
                light for light in self._lights if light[CONF_ID] not in to_remove
            ]
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_LIGHTS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_as_options(self._lights),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_light", data_schema=schema)

    # --- Climate -----------------------------------------------------------

    def _climate_schema(self) -> vol.Schema:
        """Return the schema for a climate's modes, codes, and temperatures."""
        code_select = selector.SelectSelector(
            selector.SelectSelectorConfig(options=self._code_options())
        )
        return vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Optional(CONF_HEAT, default=True): selector.BooleanSelector(),
                vol.Optional(CONF_COOL, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_HEAT_CODE): code_select,
                vol.Optional(CONF_COOL_CODE): code_select,
                vol.Required(CONF_OFF_CODE): code_select,
                vol.Required(CONF_UP_CODE): code_select,
                vol.Required(CONF_DOWN_CODE): code_select,
                vol.Required(CONF_TEMPERATURES): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
                vol.Optional(CONF_TARGET_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=200, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
            }
        )

    @staticmethod
    def _climate_suggested(climate: dict[str, Any]) -> dict[str, Any]:
        """Return climate values shaped for the form (temperatures as text)."""
        suggested = dict(climate)
        temps = climate.get(CONF_TEMPERATURES) or []
        suggested[CONF_TEMPERATURES] = "\n".join(
            str(int(t)) if float(t).is_integer() else str(t) for t in temps
        )
        return suggested

    @staticmethod
    def _parse_temperatures(text: str) -> list[float] | None:
        """Parse a temperatures text box (one value per line).

        Returns a sorted, de-duplicated list, or ``None`` if a line is not a
        number.
        """
        values: set[float] = set()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                values.add(float(stripped))
            except ValueError:
                return None
        return sorted(values)

    def _build_climate(
        self, user_input: dict[str, Any], climate: dict[str, Any]
    ) -> None:
        """Write validated climate fields from user input into a climate dict."""
        heat = bool(user_input.get(CONF_HEAT))
        cool = bool(user_input.get(CONF_COOL))
        climate[CONF_NAME] = user_input[CONF_NAME].strip()
        climate[CONF_HEAT] = heat
        climate[CONF_COOL] = cool
        climate[CONF_OFF_CODE] = user_input[CONF_OFF_CODE]
        climate[CONF_UP_CODE] = user_input[CONF_UP_CODE]
        climate[CONF_DOWN_CODE] = user_input[CONF_DOWN_CODE]
        climate[CONF_TEMPERATURES] = self._parse_temperatures(
            user_input[CONF_TEMPERATURES]
        )
        _set_optional(
            climate, CONF_HEAT_CODE, user_input.get(CONF_HEAT_CODE) if heat else None
        )
        _set_optional(
            climate, CONF_COOL_CODE, user_input.get(CONF_COOL_CODE) if cool else None
        )
        _set_optional(climate, CONF_ICON, user_input.get(CONF_ICON))
        _set_optional(climate, CONF_TEMP_SENSOR, user_input.get(CONF_TEMP_SENSOR))
        if (target := user_input.get(CONF_TARGET_TEMP)) is not None:
            climate[CONF_TARGET_TEMP] = float(target)
        else:
            climate.pop(CONF_TARGET_TEMP, None)

    @classmethod
    def _validate_climate(cls, user_input: dict[str, Any]) -> dict[str, str]:
        """Return field errors for a climate submission."""
        errors: dict[str, str] = {}
        heat = bool(user_input.get(CONF_HEAT))
        cool = bool(user_input.get(CONF_COOL))
        if not user_input[CONF_NAME].strip():
            errors[CONF_NAME] = "name_required"
        if not heat and not cool:
            errors["base"] = "need_mode"
        if heat and not user_input.get(CONF_HEAT_CODE):
            errors[CONF_HEAT_CODE] = "code_required"
        if cool and not user_input.get(CONF_COOL_CODE):
            errors[CONF_COOL_CODE] = "code_required"
        temps = cls._parse_temperatures(user_input[CONF_TEMPERATURES])
        if temps is None:
            errors[CONF_TEMPERATURES] = "invalid_temps"
        elif not temps:
            errors[CONF_TEMPERATURES] = "temps_required"
        return errors

    async def async_step_add_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a climate (heat and/or cool) built from codes.

        Enable heat, cool, or both. For a toggle-only unit, the mode code and
        the off code can be the same.
        """
        self._load()
        assert self._codes is not None
        assert self._climates is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate_climate(user_input)
            if not errors:
                climate: dict[str, Any] = {CONF_ID: uuid.uuid4().hex}
                self._build_climate(user_input, climate)
                self._climates.append(climate)
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_climate",
            data_schema=self.add_suggested_values_to_schema(
                self._climate_schema(), user_input
            ),
            errors=errors,
        )

    async def async_step_edit_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a climate to edit, then open its hub."""
        self._load()
        assert self._climates is not None

        if user_input is not None:
            self._edit_id = user_input[CONF_ID]
            return await self.async_step_manage_climate()

        schema = vol.Schema(
            {
                vol.Required(CONF_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=_as_options(self._climates))
                )
            }
        )
        return self.async_show_form(step_id="edit_climate", data_schema=schema)

    async def async_step_manage_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hub for the selected climate."""
        if _find_by_id(self._climates or [], self._edit_id) is None:
            return await self.async_step_init()
        return self.async_show_menu(
            step_id="manage_climate",
            menu_options=["edit_climate_details", "done_edit"],
        )

    async def async_step_edit_climate_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the selected climate's codes and temperature range."""
        self._load()
        assert self._codes is not None
        assert self._climates is not None
        climate = _find_by_id(self._climates, self._edit_id)
        if climate is None:
            return await self.async_step_init()

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_climate(user_input)
            if not errors:
                self._build_climate(user_input, climate)
                return await self.async_step_manage_climate()

        return self.async_show_form(
            step_id="edit_climate_details",
            data_schema=self.add_suggested_values_to_schema(
                self._climate_schema(),
                user_input
                if user_input is not None
                else self._climate_suggested(climate),
            ),
            errors=errors,
        )

    async def async_step_remove_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more climate entities."""
        self._load()
        assert self._climates is not None

        if user_input is not None:
            to_remove = set(user_input.get(CONF_CLIMATES, []))
            self._climates = [
                climate
                for climate in self._climates
                if climate[CONF_ID] not in to_remove
            ]
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIMATES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_as_options(self._climates),
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_climate", data_schema=schema)

    # --- Shared navigation -------------------------------------------------

    async def async_step_done_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Leave an item's edit hub and return to the main menu."""
        self._edit_id = None
        return await self.async_step_init()

    # --- Finish ------------------------------------------------------------

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Persist the working copies to the config entry options."""
        self._load()
        return self.async_create_entry(
            data={
                CONF_CODES: self._codes,
                CONF_BUTTONS: self._buttons,
                CONF_SWITCHES: self._switches,
                CONF_LIGHTS: self._lights,
                CONF_CLIMATES: self._climates,
            }
        )
