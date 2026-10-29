"""Reading the FRITZ!Box every minute: messages and calls, what is new, and
"seen up to" for missed calls, which the box does not keep."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .box import Box, Call, CannotConnect, LoginRefused, Message, MissingRight
from .const import CALL_DAYS, DOMAIN, EVENT_MISSED_CALL, EVENT_NEW_MESSAGE, SCAN_INTERVAL, UNKNOWN, UNKNOWN_DEFAULT

_LOGGER = logging.getLogger(__name__)


@dataclass
class FritzData:
    messages: list[Message] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)


type FritzConfigEntry = ConfigEntry[FritzCoordinator]


class FritzCoordinator(DataUpdateCoordinator[FritzData]):
    """One FRITZ!Box's messages and calls."""

    config_entry: FritzConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FritzConfigEntry, box: Box) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.box = box
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        # The newest call id when the missed calls were last seen; None
        # until the first read sets it, so nothing is new at the start.
        self.seen_up_to: int | None = None
        # What was there at the last read; None before the first.
        self._known: set[str] | None = None
        # The events of the last read: (event type, data).
        self.fresh: list[tuple[str, dict[str, Any]]] = []

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.seen_up_to = stored.get("seen_up_to")

    async def _async_update_data(self) -> FritzData:
        try:
            messages = await self.hass.async_add_executor_job(self.box.messages)
            calls = await self.hass.async_add_executor_job(self.box.calls, CALL_DAYS)
        except (CannotConnect, LoginRefused, MissingRight) as err:
            raise UpdateFailed(f"the FRITZ!Box did not answer: {err!r}") from err
        if self.seen_up_to is None:
            await self._set_seen(max((c.id for c in calls), default=0))
        keys = {_message_key(m) for m in messages} | {f"call:{c.id}" for c in calls}
        self.fresh = []
        if self._known is not None:
            for m in messages:
                if m.new and _message_key(m) not in self._known:
                    self.fresh.append((EVENT_NEW_MESSAGE, {"name": self.name_of(m.name), "date": _iso(self.local(m.date))}))
            for c in calls:
                if self._missed(c) and f"call:{c.id}" not in self._known:
                    self.fresh.append((EVENT_MISSED_CALL, {"name": self.name_of(c.name), "date": _iso(self.local(c.date))}))
        self._known = keys
        return FritzData(messages, calls)

    def _missed(self, call: Call) -> bool:
        """A missed call: nobody took it, not even the answering machine."""
        return call.kind == "missed" and not call.path

    @property
    def new_messages(self) -> list[Message]:
        return sorted((m for m in self.data.messages if m.new), key=_newest, reverse=True)

    @property
    def missed_calls(self) -> list[Call]:
        """The missed calls after "seen up to"."""
        seen = self.seen_up_to or 0
        return sorted((c for c in self.data.calls if self._missed(c) and c.id > seen), key=_newest, reverse=True)

    def local(self, date: datetime | None) -> datetime | None:
        """A date of the box (local, naive) in Home Assistant's time zone."""
        return date.replace(tzinfo=dt_util.get_default_time_zone()) if date else None

    def name_of(self, name: str) -> str:
        return name or UNKNOWN.get(self.hass.config.language, UNKNOWN_DEFAULT)

    def message(self, message_id: str) -> Message | None:
        return next((m for m in self.data.messages if m.id == message_id), None)

    async def async_mark_heard(self, messages: list[Message]) -> None:
        for m in messages:
            await self.hass.async_add_executor_job(self.box.mark_heard, m.tam, m.index)
        heard = {m.id for m in messages}
        self.fresh = []
        self.async_set_updated_data(
            replace(self.data, messages=[replace(m, new=False) if m.id in heard else m for m in self.data.messages])
        )

    async def async_delete(self, messages: list[Message]) -> None:
        for m in messages:
            await self.hass.async_add_executor_job(self.box.delete, m.tam, m.index)
        gone = {m.id for m in messages}
        self.fresh = []
        self.async_set_updated_data(replace(self.data, messages=[m for m in self.data.messages if m.id not in gone]))

    async def async_mark_calls_seen(self) -> None:
        await self._set_seen(max((c.id for c in self.data.calls), default=self.seen_up_to or 0))
        self.fresh = []
        self.async_update_listeners()

    async def _set_seen(self, call_id: int) -> None:
        self.seen_up_to = call_id
        await self._store.async_save({"seen_up_to": call_id})


def _message_key(m: Message) -> str:
    # The box numbers messages anew after a delete; the date keeps them apart.
    return f"message:{m.id}:{m.date}"


def _newest(item: Message | Call) -> datetime:
    return item.date or datetime.min


def _iso(date: datetime | None) -> str | None:
    return date.isoformat() if date else None
