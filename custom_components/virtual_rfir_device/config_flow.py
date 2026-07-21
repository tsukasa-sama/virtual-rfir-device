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
    CONF_CODE,
    CONF_COMMANDS,
    CONF_ICON,
    CONF_ID,
    CONF_OFF_COMMAND,
    CONF_ON_COMMAND,
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
        """Return the options flow used to manage this device's commands."""
        return VirtualRfirDeviceOptionsFlow()


class VirtualRfirDeviceOptionsFlow(OptionsFlow):
    """Manage the commands (buttons) attached to a virtual RF/IR device."""

    def __init__(self) -> None:
        """Initialize the options flow with a lazily-loaded working copy."""
        self._commands: list[dict[str, Any]] | None = None
        self._switches: list[dict[str, Any]] | None = None

    def _load(self) -> None:
        """Load the current options into editable working copies once."""
        if self._commands is None:
            self._commands = [
                dict(command)
                for command in self.config_entry.options.get(CONF_COMMANDS, [])
            ]
        if self._switches is None:
            self._switches = [
                dict(switch)
                for switch in self.config_entry.options.get(CONF_SWITCHES, [])
            ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the top-level menu for managing commands and switches."""
        self._load()
        assert self._commands is not None and self._switches is not None
        menu_options = ["add_command"]
        if self._commands:
            menu_options.append("remove_command")
            # Switches reference commands, so only offer them once commands exist.
            menu_options.append("add_switch")
        if self._switches:
            menu_options.append("remove_switch")
        menu_options.append("finish")
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_add_command(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a single command: name, icon, and IR/RF code to send."""
        self._load()
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            code = user_input[CONF_CODE].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not code:
                errors[CONF_CODE] = "code_required"
            else:
                command = {
                    CONF_ID: uuid.uuid4().hex,
                    CONF_NAME: name,
                    CONF_CODE: code,
                }
                if icon := user_input.get(CONF_ICON):
                    command[CONF_ICON] = icon
                assert self._commands is not None
                self._commands.append(command)
                return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Required(CONF_CODE): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="add_command",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_remove_command(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more existing commands."""
        self._load()
        assert self._commands is not None

        if user_input is not None:
            to_remove = set(user_input.get(CONF_COMMANDS, []))
            self._commands = [
                command
                for command in self._commands
                if command[CONF_ID] not in to_remove
            ]
            return await self.async_step_init()

        options = [
            selector.SelectOptionDict(
                value=command[CONF_ID], label=command[CONF_NAME]
            )
            for command in self._commands
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_COMMANDS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="remove_command", data_schema=schema)

    async def async_step_add_switch(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add an optimistic switch built from existing commands.

        Pick an ``on`` command and an ``off`` command. For a toggle-only
        appliance, choose the same command for both.
        """
        self._load()
        assert self._commands is not None and self._switches is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                switch = {
                    CONF_ID: uuid.uuid4().hex,
                    CONF_NAME: name,
                    CONF_ON_COMMAND: user_input[CONF_ON_COMMAND],
                    CONF_OFF_COMMAND: user_input[CONF_OFF_COMMAND],
                }
                if icon := user_input.get(CONF_ICON):
                    switch[CONF_ICON] = icon
                self._switches.append(switch)
                return await self.async_step_init()

        command_options = [
            selector.SelectOptionDict(
                value=command[CONF_ID], label=command[CONF_NAME]
            )
            for command in self._commands
        ]
        command_select = selector.SelectSelector(
            selector.SelectSelectorConfig(options=command_options)
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_ICON): selector.IconSelector(),
                vol.Required(CONF_ON_COMMAND): command_select,
                vol.Required(CONF_OFF_COMMAND): command_select,
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
        """Remove one or more existing switches."""
        self._load()
        assert self._switches is not None

        if user_input is not None:
            to_remove = set(user_input.get(CONF_SWITCHES, []))
            self._switches = [
                switch
                for switch in self._switches
                if switch[CONF_ID] not in to_remove
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

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Persist the working copies to the config entry options."""
        self._load()
        return self.async_create_entry(
            data={
                CONF_COMMANDS: self._commands,
                CONF_SWITCHES: self._switches,
            }
        )
