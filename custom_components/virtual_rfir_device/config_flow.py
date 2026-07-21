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
from homeassistant.helpers import selector

from .const import (
    CONF_BUTTONS,
    CONF_CODE,
    CONF_CODE_ID,
    CONF_CODES,
    CONF_ICON,
    CONF_ID,
    CONF_OFF_CODE,
    CONF_ON_CODE,
    CONF_REMOTE,
    CONF_SWITCHES,
    DOMAIN,
)


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

    def _load(self) -> None:
        """Load the current options into editable working copies once."""
        options = self.config_entry.options
        if self._codes is None:
            self._codes = [dict(item) for item in options.get(CONF_CODES, [])]
        if self._buttons is None:
            self._buttons = [dict(item) for item in options.get(CONF_BUTTONS, [])]
        if self._switches is None:
            self._switches = [dict(item) for item in options.get(CONF_SWITCHES, [])]

    def _code_options(self) -> list[selector.SelectOptionDict]:
        """Return the code library as select options."""
        assert self._codes is not None
        return [
            selector.SelectOptionDict(value=code[CONF_ID], label=code[CONF_NAME])
            for code in self._codes
        ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the top-level menu for managing the device's contents."""
        self._load()
        assert self._codes is not None
        assert self._buttons is not None
        assert self._switches is not None

        menu_options = ["add_code"]
        if self._codes:
            menu_options.append("remove_code")
            # Buttons and switches reference codes, so require codes first.
            menu_options.append("add_button")
        if self._buttons:
            menu_options.append("remove_button")
        if self._codes:
            menu_options.append("add_switch")
        if self._switches:
            menu_options.append("remove_switch")
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
                        options=self._code_options(), multiple=True
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_code", data_schema=schema)

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

        options = [
            selector.SelectOptionDict(value=button[CONF_ID], label=button[CONF_NAME])
            for button in self._buttons
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_BUTTONS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="remove_button", data_schema=schema)

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

        options = [
            selector.SelectOptionDict(value=switch[CONF_ID], label=switch[CONF_NAME])
            for switch in self._switches
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_SWITCHES): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="remove_switch", data_schema=schema)

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
            }
        )
