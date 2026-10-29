"""The phone book (fritz.md: Actions, get_phonebook)."""

import xml.etree.ElementTree as ET

from custom_components.mira_fritz.box import Contact, parse_phonebook
from custom_components.mira_fritz.const import CONF_PHONEBOOKS, DOMAIN

from .conftest import setup

XML = """<phonebooks><phonebook name="Telefonbuch">
<contact><person><realName>Oma Erika</realName></person><telephony>
<number type="home" prio="1">0301234</number><number type="mobile">0172555</number></telephony></contact>
<contact><person><realName>Fax</realName></person><telephony><number type="fax_work">0309</number></telephony></contact>
</phonebook></phonebooks>"""


async def test_FZ10_get_phonebook_gives_the_chosen_books(hass, box, entry):
    contacts = parse_phonebook(ET.fromstring(XML))
    assert contacts[0].numbers == [
        {"number": "0301234", "type": "home", "main": True},
        {"number": "0172555", "type": "mobile", "main": False},
    ]
    box.books = {0: ("Telefonbuch", contacts), 1: ("Google", [Contact("Ben", [{"number": "1", "type": "", "main": True}])])}
    hass.config_entries.async_update_entry(entry, options={CONF_PHONEBOOKS: ["Telefonbuch"]})
    await setup(hass, entry)
    response = await hass.services.async_call(DOMAIN, "get_phonebook", {}, blocking=True, return_response=True)
    names = [c["name"] for c in response["contacts"]]
    assert names == ["Oma Erika", "Fax"]
    assert response["books"] == ["Telefonbuch"] and response["url"] == "http://192.168.178.1"
    assert response["contacts"][0]["numbers"][0] == {"number": "0301234", "type": "home", "main": True}


async def test_FZ11_a_contact_in_two_books_comes_once(hass, box, entry):
    oma = [{"number": "0301234", "type": "home", "main": True}]
    box.books = {0: ("Telefonbuch", [Contact("Oma", list(oma))]), 1: ("Google", [Contact("Oma", list(oma))])}
    hass.config_entries.async_update_entry(entry, options={CONF_PHONEBOOKS: ["Telefonbuch", "Google"]})
    await setup(hass, entry)
    response = await hass.services.async_call(DOMAIN, "get_phonebook", {}, blocking=True, return_response=True)
    assert [c["name"] for c in response["contacts"]] == ["Oma"]
