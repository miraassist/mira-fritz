"""The actions: messages, calls and the phone book, with a response. For
every user, as the box's own app shows the call list to everyone at home."""

from __future__ import annotations

from datetime import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .box import CannotConnect, LoginRefused, MissingRight
from .const import CONF_PHONEBOOKS, DOMAIN
from .coordinator import FritzCoordinator
from .media_source import media_content_id

KINDS = ["missed", "incoming", "outgoing", "refused"]

_ENTRY = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
_IDS = {**_ENTRY, vol.Optional("message_ids", default=[]): vol.All(cv.ensure_list, [cv.string])}


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> FritzCoordinator:
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        entries = [e for e in entries if e.entry_id == entry_id]
    if len(entries) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="which_box" if entries else "no_box"
        )
    return entries[0].runtime_data


async def _box_call(coro):
    try:
        return await coro
    except (CannotConnect, LoginRefused, MissingRight) as err:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="box_failed") from err


def _messages(coordinator: FritzCoordinator, ids: list[str]):
    if not ids:
        return list(coordinator.data.messages)
    found = [coordinator.message(i) for i in ids]
    if None in found:
        unknown = [i for i, m in zip(ids, found) if m is None]
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="unknown_message", translation_placeholders={"ids": ", ".join(unknown)}
        )
    return found


@callback
def async_register_services(hass: HomeAssistant) -> None:
    async def get_messages(call: ServiceCall) -> ServiceResponse:
        c = _coordinator(hass, call)
        messages = c.new_messages if call.data["new_only"] else sorted(
            c.data.messages, key=lambda m: m.date or datetime.min, reverse=True
        )
        return {
            "messages": [
                {
                    "id": m.id,
                    "answering_machine": m.tam,
                    "name": c.name_of(m.name),
                    "number": m.number,
                    "date": _iso(c.local(m.date)),
                    "duration": m.duration,
                    "new": m.new,
                    "media_content_id": media_content_id(c.config_entry.entry_id, m),
                }
                for m in messages
            ]
        }

    async def mark_heard(call: ServiceCall) -> None:
        c = _coordinator(hass, call)
        await _box_call(c.async_mark_heard([m for m in _messages(c, call.data["message_ids"]) if m.new]))

    async def delete_messages(call: ServiceCall) -> None:
        c = _coordinator(hass, call)
        if not call.data["message_ids"]:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_ids")
        await _box_call(c.async_delete(_messages(c, call.data["message_ids"])))

    async def get_calls(call: ServiceCall) -> ServiceResponse:
        c = _coordinator(hass, call)
        kind = call.data.get("kind")
        if call.data["new_only"]:
            calls = c.missed_calls
        else:
            calls = sorted(c.data.calls, key=lambda x: x.id, reverse=True)
        # A call the answering machine took is the message of the same
        # caller at the same minute.
        messages = {(m.number, m.date): m for m in c.data.messages}
        out = []
        for x in calls:
            if kind and x.kind != kind:
                continue
            message = messages.get((x.number, x.date)) if x.path else None
            out.append(
                {
                    "kind": x.kind,
                    "name": c.name_of(x.name),
                    "number": x.number,
                    "date": _iso(c.local(x.date)),
                    "duration": x.duration,
                    "message_id": message.id if message else None,
                }
            )
        return {"calls": out}

    async def mark_calls_seen(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_mark_calls_seen()

    async def get_phonebook(call: ServiceCall) -> ServiceResponse:
        c = _coordinator(hass, call)
        books = c.config_entry.options.get(CONF_PHONEBOOKS, [])
        read, contacts = await _box_call(hass.async_add_executor_job(c.box.phonebook, books))
        return {
            "books": read,
            "url": f"http://{c.box.host}",
            "contacts": [{"name": x.name, "numbers": x.numbers} for x in contacts],
        }

    for name, handler, schema, response in (
        ("get_messages", get_messages, {**_ENTRY, vol.Optional("new_only", default=False): cv.boolean}, SupportsResponse.ONLY),
        ("mark_heard", mark_heard, _IDS, SupportsResponse.NONE),
        ("delete_messages", delete_messages, _IDS, SupportsResponse.NONE),
        (
            "get_calls",
            get_calls,
            {**_ENTRY, vol.Optional("kind"): vol.In(KINDS), vol.Optional("new_only", default=False): cv.boolean},
            SupportsResponse.ONLY,
        ),
        ("mark_calls_seen", mark_calls_seen, _ENTRY, SupportsResponse.NONE),
        ("get_phonebook", get_phonebook, _ENTRY, SupportsResponse.ONLY),
    ):
        hass.services.async_register(DOMAIN, name, handler, vol.Schema(schema), supports_response=response)


def _iso(date) -> str | None:
    return date.isoformat() if date else None


