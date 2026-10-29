"""Setting up: address (the factory one filled in), user and password; the
login is tried, and what is wrong is said. Options: which phone books."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .box import Box, CannotConnect, LoginRefused, MissingRight
from .const import CONF_PHONEBOOKS, DEFAULT_HOST, DOMAIN


async def _check(hass, data: dict[str, Any]) -> str | None:
    """None when the box answers with every right, else the form's error."""
    box = Box(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
    try:
        await hass.async_add_executor_job(box.check)
    except CannotConnect:
        return "cannot_connect"
    except LoginRefused:
        return "invalid_auth"
    except MissingRight as err:
        return f"missing_right_{err.right}"
    return None


class MiraFritzConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            if (error := await _check(self.hass, user_input)) is None:
                return self.async_create_entry(title=f"FRITZ!Box {user_input[CONF_HOST]}", data=user_input)
            errors["base"] = error
        defaults = user_input or {CONF_HOST: DEFAULT_HOST}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): str,
                vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MiraFritzOptionsFlow()


class MiraFritzOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        box = self.config_entry.runtime_data.box
        try:
            books = await self.hass.async_add_executor_job(box.phonebooks)
        except (CannotConnect, LoginRefused, MissingRight):
            return self.async_abort(reason="cannot_connect")
        names = list(books.values())
        chosen = self.config_entry.options.get(CONF_PHONEBOOKS) or names[:1]
        schema = vol.Schema(
            {
                vol.Optional(CONF_PHONEBOOKS, default=chosen): SelectSelector(
                    SelectSelectorConfig(options=names, multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
