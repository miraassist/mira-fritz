"""The messages as a media source: playable on every media player, a voice
satellite too. Resolving gives a signed address of the integration's view,
so a device without a login fetches the recording; nothing is stored."""

from __future__ import annotations

from datetime import datetime, timedelta

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .box import CannotConnect, LoginRefused, Message, MissingRight
from .const import DOMAIN
from .coordinator import FritzCoordinator

URL = "/api/mira_fritz/message/{entry_id}/{tam}/{index}"
SIGNED_FOR = timedelta(hours=1)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    return FritzMediaSource(hass)


def media_content_id(entry_id: str, message: Message) -> str:
    return f"media-source://{DOMAIN}/{entry_id}/{message.tam}/{message.index}"


def _coordinator(hass: HomeAssistant, entry_id: str) -> FritzCoordinator | None:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        return None
    return entry.runtime_data


def _title(coordinator: FritzCoordinator, m: Message) -> str:
    date = coordinator.local(m.date)
    when = date.strftime("%d.%m. %H:%M") if date else ""
    return f"{coordinator.name_of(m.name)} – {when} ({max(m.minutes, 1)} min)"


class FritzMediaSource(MediaSource):
    name = "FRITZ!Box"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        try:
            entry_id, tam, index = item.identifier.split("/")
        except ValueError as err:
            raise Unresolvable(f"unknown message {item.identifier}") from err
        coordinator = _coordinator(self.hass, entry_id)
        if coordinator is None or coordinator.message(f"{tam}:{index}") is None:
            raise Unresolvable(f"unknown message {item.identifier}")
        path = URL.format(entry_id=entry_id, tam=tam, index=index)
        return PlayMedia(async_sign_path(self.hass, path, SIGNED_FOR), "audio/wav")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        entries = [e for e in self.hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
        if item.identifier:
            coordinator = _coordinator(self.hass, item.identifier)
            if coordinator is None:
                raise BrowseError(f"unknown FRITZ!Box {item.identifier}")
            return self._box(item.identifier, coordinator)
        if len(entries) == 1:
            return self._box(entries[0].entry_id, entries[0].runtime_data)
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=e.entry_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=e.title,
                    can_play=False,
                    can_expand=True,
                )
                for e in entries
            ],
        )

    def _box(self, entry_id: str, coordinator: FritzCoordinator) -> BrowseMediaSource:
        messages = sorted(coordinator.data.messages, key=lambda m: m.date or datetime.min, reverse=True)
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=entry_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=coordinator.config_entry.title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.MUSIC,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry_id}/{m.tam}/{m.index}",
                    media_class=MediaClass.MUSIC,
                    media_content_type="audio/wav",
                    title=_title(coordinator, m),
                    can_play=True,
                    can_expand=False,
                )
                for m in messages
            ],
        )


class MessageView(HomeAssistantView):
    """A message's recording, fetched from the box when asked. Reached with a
    login or a signed address."""

    url = URL
    name = "api:mira_fritz:message"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, entry_id: str, tam: str, index: str) -> web.Response:
        coordinator = _coordinator(self.hass, entry_id)
        if coordinator is None or not tam.isdigit() or not index.isdigit():
            raise web.HTTPNotFound
        try:
            known = coordinator.message(f"{tam}:{index}")
            path = known.path if known else ""
            body = await self.hass.async_add_executor_job(coordinator.box.recording, int(tam), int(index), path)
        except KeyError as err:
            raise web.HTTPNotFound from err
        except (CannotConnect, LoginRefused, MissingRight) as err:
            raise web.HTTPBadGateway from err
        return web.Response(body=body, content_type="audio/wav")
