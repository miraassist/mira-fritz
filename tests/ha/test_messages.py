"""Messages and the media source (fritz.md: What it reads, Entities, Media source)."""

from http import HTTPStatus
import xml.etree.ElementTree as ET

from homeassistant.components.media_source import async_browse_media, async_resolve_media
from homeassistant.setup import async_setup_component

from custom_components.mira_fritz.box import parse_messages
from custom_components.mira_fritz.const import DOMAIN

from .conftest import message, setup

XML = """<Root><Message><Index>3</Index><Tam>0</Tam><Called>123</Called><Date>29.10.26 14:12</Date>
<Duration>0:01</Duration><Inbook>1</Inbook><Name>Oma</Name><New>1</New><Number>0301234</Number>
<Path>/download.lua?path=/data/tam/rec/rec.0.003</Path></Message></Root>"""

SENSOR = "sensor.fritz_box_new_messages"


async def test_FZ20_new_messages_are_counted_without_numbers(hass, box, entry):
    parsed = parse_messages(ET.fromstring(XML), 0)
    assert parsed[0].id == "0:3" and parsed[0].new and parsed[0].number == "0301234"
    box.msgs = [message(1), message(2, name="Ben"), message(3, new=False)]
    await setup(hass, entry)
    state = hass.states.get(SENSOR)
    assert state.state == "2"
    assert {m["name"] for m in state.attributes["messages"]} == {"Oma", "Ben"}
    assert "0301234" not in str(state.attributes)


async def test_FZ21_mark_heard_marks_at_the_box(hass, box, entry):
    box.msgs = [message(1)]
    await setup(hass, entry)
    await hass.services.async_call(DOMAIN, "mark_heard", {"message_ids": ["0:1"]}, blocking=True)
    assert box.marked == [(0, 1)]
    assert hass.states.get(SENSOR).state == "0"


async def test_FZ22_get_messages_gives_what_a_player_needs(hass, box, entry):
    box.msgs = [message(1)]
    await setup(hass, entry)
    response = await hass.services.async_call(DOMAIN, "get_messages", {}, blocking=True, return_response=True)
    m = response["messages"][0]
    assert m["id"] == "0:1" and m["name"] == "Oma" and m["number"] == "0301234" and m["duration"] == "0:23"
    assert m["date"].startswith("2026-10-29T14:12")
    assert m["media_content_id"] == f"media-source://{DOMAIN}/{entry.entry_id}/0/1"


async def test_FZ23_what_is_there_at_the_start_fires_no_event(hass, box, entry):
    box.msgs = [message(1)]
    coordinator = await setup(hass, entry)
    events = "event.fritz_box_calls"
    assert hass.states.get(events).state == "unknown"
    box.msgs = [message(1), message(2, name="Ben", date="2026-10-29 15:00")]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(events)
    assert state.attributes["event_type"] == "new_message" and state.attributes["name"] == "Ben"


async def test_FZ30_a_message_plays_without_a_login(hass, box, entry, hass_client_no_auth):
    assert await async_setup_component(hass, "media_source", {})
    box.msgs = [message(1)]
    await setup(hass, entry)
    played = await async_resolve_media(hass, f"media-source://{DOMAIN}/{entry.entry_id}/0/1", None)
    assert played.mime_type == "audio/wav" and "authSig=" in played.url
    client = await hass_client_no_auth()
    response = await client.get(played.url)
    assert response.status == HTTPStatus.OK and await response.read() == b"RIFF....WAVE"
    unsigned = await client.get(played.url.split("?")[0])
    assert unsigned.status == HTTPStatus.UNAUTHORIZED


async def test_FZ31_the_browser_lists_messages_newest_first(hass, box, entry):
    assert await async_setup_component(hass, "media_source", {})
    box.msgs = [
        message(1, date="2026-10-27 09:00"),
        message(2, name="Ben", date="2026-10-29 16:00"),
        message(3, name="", date="2026-10-28 12:30"),
    ]
    await setup(hass, entry)
    browsed = await async_browse_media(hass, f"media-source://{DOMAIN}")
    assert [c.title for c in browsed.children] == [
        "Ben – 29.10. 16:00 (0:23)",
        "unknown – 28.10. 12:30 (0:23)",
        "Oma – 27.10. 09:00 (0:23)",
    ]
