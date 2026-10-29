"""New messages and missed calls as counts. The lists in the attributes
name caller and time, never a number, and stay out of the recorder."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FritzConfigEntry
from .entity import FritzEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: FritzConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([NewMessages(coordinator, "new_messages"), MissedCalls(coordinator, "missed_calls")])


class NewMessages(FritzEntity, SensorEntity):
    _unrecorded_attributes = frozenset({"messages"})

    @property
    def native_value(self) -> int:
        return len(self.coordinator.new_messages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        return {
            "messages": [
                {"name": c.name_of(m.name), "date": _iso(c.local(m.date)), "minutes": m.minutes}
                for m in c.new_messages
            ]
        }


class MissedCalls(FritzEntity, SensorEntity):
    _unrecorded_attributes = frozenset({"calls"})

    @property
    def native_value(self) -> int:
        return len(self.coordinator.missed_calls)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        return {"calls": [{"name": c.name_of(x.name), "date": _iso(c.local(x.date))} for x in c.missed_calls]}


def _iso(date):
    return date.isoformat() if date else None
