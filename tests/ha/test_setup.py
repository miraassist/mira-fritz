"""Setting up (fritz.md: Setting up)."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mira_fritz.box import LoginRefused, MissingRight
from custom_components.mira_fritz.const import DEFAULT_HOST, DOMAIN


async def _form(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_FZ01_only_user_and_password_must_be_typed(hass, box):
    result = await _form(hass)
    host = next(k for k in result["data_schema"].schema if k == CONF_HOST)
    assert host.default() == DEFAULT_HOST
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: DEFAULT_HOST, CONF_USERNAME: "ha", CONF_PASSWORD: "secret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == DEFAULT_HOST


async def test_FZ02_a_refused_login_is_said_in_plain_words(hass, box):
    box.refuse = LoginRefused("401")
    result = await _form(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: DEFAULT_HOST, CONF_USERNAME: "ha", CONF_PASSWORD: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "invalid_auth"}


async def test_FZ03_a_missing_right_is_named(hass, box):
    box.refuse = MissingRight("calls")
    result = await _form(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: DEFAULT_HOST, CONF_USERNAME: "ha", CONF_PASSWORD: "secret"}
    )
    assert result["errors"] == {"base": "missing_right_calls"}
    import json
    from pathlib import Path

    strings = json.loads((Path(__file__).parents[2] / "custom_components/mira_fritz/strings.json").read_text())
    assert "System → FRITZ!Box Users" in strings["config"]["error"]["missing_right_calls"]
