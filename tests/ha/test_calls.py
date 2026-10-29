"""Calls (fritz.md: What it reads, Entities)."""

import xml.etree.ElementTree as ET

from custom_components.mira_fritz.box import parse_calls
from custom_components.mira_fritz.const import DOMAIN

from .conftest import call, setup

XML = """<root><Call><Id>7</Id><Type>2</Type><Caller>0175999</Caller><Called>123</Called><Name>Ben</Name>
<Date>29.10.26 16:40</Date><Duration>0:00</Duration></Call>
<Call><Id>8</Id><Type>3</Type><Caller>123</Caller><Called>0301234</Called><Name>Oma</Name>
<Date>29.10.26 17:00</Date><Duration>0:05</Duration></Call></root>"""

SENSOR = "sensor.fritz_box_missed_calls"


async def _fresh(hass, box, entry, calls):
    """Set up with nothing seen yet, then the calls come."""
    coordinator = await setup(hass, entry)
    box.call_list = calls
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    return coordinator


async def test_FZ40_a_call_the_answering_machine_took_is_not_a_missed_call(hass, box, entry):
    parsed = parse_calls(ET.fromstring(XML))
    assert [(c.kind, c.number) for c in parsed] == [("missed", "0175999"), ("outgoing", "0301234")]
    await _fresh(hass, box, entry, [call(1), call(2, kind="incoming", path="/rec.1")])
    assert hass.states.get(SENSOR).state == "1"
    assert "0175999" not in str(hass.states.get(SENSOR).attributes)


async def test_FZ41_mark_calls_seen_sets_the_missed_calls_to_zero(hass, box, entry):
    await _fresh(hass, box, entry, [call(1), call(2)])
    assert hass.states.get(SENSOR).state == "2"
    await hass.services.async_call(DOMAIN, "mark_calls_seen", {}, blocking=True)
    assert hass.states.get(SENSOR).state == "0"
    # After a restart: the point is stored.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == "0"
    response = await hass.services.async_call(
        DOMAIN, "get_calls", {"kind": "missed"}, blocking=True, return_response=True
    )
    assert [c["number"] for c in response["calls"]] == ["0175999", "0175999"]


async def test_FZ42_a_new_missed_call_fires_an_event(hass, box, entry):
    await _fresh(hass, box, entry, [call(5, name="Ben")])
    state = hass.states.get("event.fritz_box_calls")
    assert state.attributes["event_type"] == "missed_call" and state.attributes["name"] == "Ben"
