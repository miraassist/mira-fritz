"""A new message or a missed call as an event, for automations."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_MISSED_CALL, EVENT_NEW_MESSAGE
from .coordinator import FritzConfigEntry
from .entity import FritzEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: FritzConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([CallEvents(entry.runtime_data, "calls")])


class CallEvents(FritzEntity, EventEntity):
    _attr_event_types = [EVENT_NEW_MESSAGE, EVENT_MISSED_CALL]

    @callback
    def _handle_coordinator_update(self) -> None:
        for event_type, data in self.coordinator.fresh:
            self._trigger_event(event_type, data)
        super()._handle_coordinator_update()
