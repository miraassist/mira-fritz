"""Mira FRITZ!Box: a FRITZ!Box's phone book, answering machines and missed
calls in Home Assistant (docs/spec/fritz.md)."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .box import Box
from .callmonitor import CallMonitor
from .const import DOMAIN
from .coordinator import FritzConfigEntry, FritzCoordinator
from .media_source import MessageView
from .services import async_register_services

PLATFORMS = [Platform.EVENT, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_services(hass)
    hass.http.register_view(MessageView(hass))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FritzConfigEntry) -> bool:
    box = Box(entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = FritzCoordinator(hass, entry, box)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Told after a call instead of asking every minute (fritz.md).
    monitor = CallMonitor(entry.data[CONF_HOST], coordinator.monitor_connected, coordinator.call_ended)
    monitor.start(hass)
    entry.async_on_unload(monitor.stop)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FritzConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await hass.async_add_executor_job(entry.runtime_data.box.close)
    return unloaded
