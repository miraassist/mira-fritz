"""The FRITZ!Box over TR-064: phone books, answering machines, call list.

Everything here blocks (fritzconnection uses requests); Home Assistant calls
it in its executor. Dates come as the box gives them, local and without a
time zone; the coordinator places them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzAuthorizationError,
    FritzConnectionException,
    FritzSecurityError,
    FritzServiceError,
)
from fritzconnection.core.utils import get_xml_root

ON_TEL = "X_AVM-DE_OnTel1"
TAM = "X_AVM-DE_TAM1"
TIMEOUT = 10

# The call list's types (AVM, x_contact): 9 and 11 are calls going on.
KINDS = {1: "incoming", 2: "missed", 3: "outgoing", 9: "incoming", 10: "refused", 11: "outgoing"}


class CannotConnect(Exception):
    """The box does not answer at that address."""


class LoginRefused(Exception):
    """The box refused user or password."""


class MissingRight(Exception):
    """The box's user lacks a right: "phone" (Telefonie) or "calls"
    (Sprachnachrichten, Faxnachrichten, FRITZ!App Fon und Anrufliste)."""

    def __init__(self, right: str) -> None:
        super().__init__(right)
        self.right = right


@dataclass(frozen=True)
class Message:
    """A message on an answering machine."""

    tam: int
    index: int
    name: str
    number: str
    date: datetime | None
    duration: str
    new: bool
    path: str

    @property
    def id(self) -> str:
        return f"{self.tam}:{self.index}"


@dataclass(frozen=True)
class Call:
    """A call of the call list; path is set when the answering machine took
    it."""

    id: int
    kind: str
    name: str
    number: str
    date: datetime | None
    duration: str
    path: str


@dataclass
class Contact:
    """A phone book entry."""

    name: str
    numbers: list[dict[str, Any]] = field(default_factory=list)


def parse_id(message_id: str) -> tuple[int, int]:
    """A message id "<tam>:<index>" as numbers."""
    tam, _, index = message_id.partition(":")
    return int(tam), int(index)


def _date(text: str | None) -> datetime | None:
    try:
        return datetime.strptime(text or "", "%d.%m.%y %H:%M")
    except ValueError:
        return None


def _text(node: ET.Element, tag: str) -> str:
    return (node.findtext(tag) or "").strip()


class Box:
    """One FRITZ!Box, reached with a user of its own."""

    def __init__(self, host: str, user: str, password: str) -> None:
        self.host = host
        self.user = user
        self.password = password
        self._fc: FritzConnection | None = None

    def _conn(self) -> FritzConnection:
        if self._fc is None:
            try:
                self._fc = FritzConnection(
                    address=self.host, user=self.user, password=self.password, timeout=TIMEOUT
                )
            except FritzConnectionException as err:
                raise CannotConnect(str(err)) from err
            except OSError as err:
                raise CannotConnect(str(err)) from err
        return self._fc

    def _call(self, right: str, service: str, action: str, **arguments: Any) -> dict[str, Any]:
        try:
            return self._conn().call_action(service, action, arguments=arguments or None)
        except FritzAuthorizationError as err:
            raise LoginRefused(str(err)) from err
        except (FritzSecurityError, FritzActionError, FritzServiceError) as err:
            raise MissingRight(right) from err
        except FritzConnectionException as err:
            raise CannotConnect(str(err)) from err
        except OSError as err:
            self._fc = None
            raise CannotConnect(str(err)) from err

    def _xml(self, url: str) -> ET.Element:
        try:
            return get_xml_root(url, timeout=TIMEOUT, session=self._conn().session)
        except (FritzConnectionException, OSError) as err:
            raise CannotConnect(str(err)) from err

    def check(self) -> None:
        """Log in and read once what the integration needs: raises
        LoginRefused, MissingRight or CannotConnect."""
        self._call("phone", ON_TEL, "GetPhonebookList")
        self._call("calls", ON_TEL, "GetCallList")
        self._call("calls", TAM, "GetList")

    # --- Phone book ---------------------------------------------------------------------------------------

    def phonebooks(self) -> dict[int, str]:
        """The box's phone books by id, with their names."""
        ids = self._call("phone", ON_TEL, "GetPhonebookList")["NewPhonebookList"]
        out = {}
        for part in str(ids).split(","):
            if part.strip().isdigit():
                book = self._call("phone", ON_TEL, "GetPhonebook", NewPhonebookID=int(part))
                out[int(part)] = book["NewPhonebookName"]
        return out

    def phonebook(self, names: list[str]) -> tuple[list[str], list[Contact]]:
        """The names of the books read and their contacts (none named: the
        first book). A name in two books with the same numbers comes once."""
        books = self.phonebooks()
        chosen = [i for i, n in books.items() if n in names] or sorted(books)[:1]
        out: list[Contact] = []
        for book_id in chosen:
            url = self._call("phone", ON_TEL, "GetPhonebook", NewPhonebookID=book_id)["NewPhonebookURL"]
            for contact in parse_phonebook(self._xml(url)):
                if not any(c.name == contact.name and _same(c.numbers, contact.numbers) for c in out):
                    out.append(contact)
        return [books[i] for i in chosen], out

    # --- Answering machines -------------------------------------------------------------------------------

    def tams(self) -> list[int]:
        """The answering machines set up on the box."""
        listing = self._call("calls", TAM, "GetList")["NewTAMList"]
        root = ET.fromstring(listing)
        return [int(_text(i, "Index")) for i in root.iter("Item") if _text(i, "Display") == "1"]

    def messages(self) -> list[Message]:
        out: list[Message] = []
        for tam in self.tams():
            url = self._call("calls", TAM, "GetMessageList", NewIndex=tam)["NewURL"]
            out += parse_messages(self._xml(url), tam)
        return out

    def mark_heard(self, tam: int, index: int) -> None:
        self._call("calls", TAM, "MarkMessage", NewIndex=tam, NewMessageIndex=index, NewMarkedAsRead=1)

    def delete(self, tam: int, index: int) -> None:
        self._call("calls", TAM, "DeleteMessage", NewIndex=tam, NewMessageIndex=index)

    def recording(self, tam: int, index: int) -> bytes:
        """A message's recording as the box keeps it (WAV). It is fetched
        where the message list is, on the TR-064 port with the list's
        session id; the web port refuses it (tried 2026-10-29)."""
        url = self._call("calls", TAM, "GetMessageList", NewIndex=tam)["NewURL"]
        parts = urlparse(url)
        sid = parse_qs(parts.query).get("sid", [""])[0]
        message = next((m for m in parse_messages(self._xml(url), tam) if m.index == index), None)
        if message is None or not message.path:
            raise KeyError(f"{tam}:{index}")
        conn = self._conn()
        try:
            response = conn.session.get(
                f"{parts.scheme}://{parts.netloc}{message.path}&sid={sid}", timeout=TIMEOUT
            )
            response.raise_for_status()
        except OSError as err:
            raise CannotConnect(str(err)) from err
        return response.content

    # --- Calls --------------------------------------------------------------------------------------------

    def calls(self, days: int) -> list[Call]:
        url = self._call("calls", ON_TEL, "GetCallList")["NewCallListURL"]
        return parse_calls(self._xml(f"{url}&days={days}"))


def parse_phonebook(root: ET.Element) -> list[Contact]:
    out = []
    for contact in root.iter("contact"):
        name = _text(contact, "person/realName")
        numbers = [
            {"number": (n.text or "").strip(), "type": n.get("type") or "", "main": n.get("prio") == "1"}
            for n in contact.iter("number")
            if (n.text or "").strip()
        ]
        if name and numbers:
            out.append(Contact(name, numbers))
    return out


def _same(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> bool:
    return sorted(n["number"] for n in a) == sorted(n["number"] for n in b)


def parse_messages(root: ET.Element, tam: int) -> list[Message]:
    return [
        Message(
            tam=tam,
            index=int(_text(m, "Index") or 0),
            name=_text(m, "Name"),
            number=_text(m, "Number"),
            date=_date(m.findtext("Date")),
            duration=_text(m, "Duration"),
            new=_text(m, "New") == "1",
            path=_text(m, "Path"),
        )
        for m in root.iter("Message")
    ]


def parse_calls(root: ET.Element) -> list[Call]:
    out = []
    for c in root.iter("Call"):
        kind = KINDS.get(int(_text(c, "Type") or 0))
        if kind is None:
            continue
        outgoing = kind == "outgoing"
        out.append(
            Call(
                id=int(_text(c, "Id") or 0),
                kind=kind,
                name=_text(c, "Name"),
                number=_text(c, "Called" if outgoing else "Caller"),
                date=_date(c.findtext("Date")),
                duration=_text(c, "Duration"),
                path=_text(c, "Path"),
            )
        )
    return out
