"""Fixtures: a FRITZ!Box in memory instead of TR-064, and an entry for it."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mira_fritz.box import Call, Contact, Message
from custom_components.mira_fritz.const import DOMAIN

HOST = "192.168.178.1"


def message(index, name="Oma", new=True, date="2026-10-29 14:12", tam=0, number="0301234"):
    return Message(tam, index, name, number, datetime.fromisoformat(date), "0:23", new, f"/download.lua?path=/rec.{index}")


def call(id_, kind="missed", name="Ben", date="2026-10-29 16:40", path="", number="0175999"):
    return Call(id_, kind, name, number, datetime.fromisoformat(date), "0:00", path)


class FakeBox:
    """A FRITZ!Box: what it holds, and what it was told."""

    def __init__(self, host, user, password):
        self.host, self.user, self.password = host, user, password
        self.refuse: Exception | None = None
        self.msgs: list[Message] = []
        self.call_list: list[Call] = []
        self.books = {0: ("Telefonbuch", []), 1: ("Google", [])}
        self.marked: list[tuple[int, int]] = []
        self.deleted: list[tuple[int, int]] = []

    def check(self):
        if self.refuse:
            raise self.refuse

    def phonebooks(self):
        return {i: name for i, (name, _) in self.books.items()}

    def phonebook(self, names):
        chosen = [i for i, (n, _) in self.books.items() if n in names] or [0]
        out: list[Contact] = []
        for i in chosen:
            for c in self.books[i][1]:
                if not any(o.name == c.name and o.numbers == c.numbers for o in out):
                    out.append(c)
        return out

    def messages(self):
        return list(self.msgs)

    def calls(self, days):
        return list(self.call_list)

    def mark_heard(self, tam, index):
        self.marked.append((tam, index))

    def delete(self, tam, index):
        self.deleted.append((tam, index))

    def recording(self, tam, index):
        if not any(m.tam == tam and m.index == index for m in self.msgs):
            raise KeyError(index)
        return b"RIFF....WAVE"


@pytest.fixture(autouse=True)
def custom(enable_custom_integrations):
    yield


@pytest.fixture
def box():
    """The one FakeBox every Box(...) of the integration becomes."""
    fake = FakeBox(HOST, "ha", "secret")
    with (
        patch("custom_components.mira_fritz.Box", lambda *a: fake),
        patch("custom_components.mira_fritz.config_flow.Box", lambda *a: fake),
    ):
        yield fake


@pytest.fixture
def entry(hass) -> MockConfigEntry:
    e = MockConfigEntry(
        domain=DOMAIN,
        title=f"FRITZ!Box {HOST}",
        unique_id=HOST,
        data={CONF_HOST: HOST, CONF_USERNAME: "ha", CONF_PASSWORD: "secret"},
    )
    e.add_to_hass(hass)
    return e


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data
