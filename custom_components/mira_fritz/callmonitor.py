"""The box's call monitor (fritz.md, Told, not asked): TCP port 1012 sends a
line for every call. After an incoming call ends the box is read once; asking
every minute is only the safety net while the monitor is not there."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

_LOGGER = logging.getLogger(__name__)

PORT = 1012
# How long to wait before connecting again after the monitor went away: the
# box restarting, the monitor switched off. Not a coordination of anything.
RECONNECT = 30


class CallMonitor:
    """Listens to the call monitor and tells when an incoming call ended.

    connected(bool) is told when the monitor comes and goes; call_ended(tam)
    when a call that rang has ended, tam whether an answering machine took
    it."""

    def __init__(self, host: str, connected: Callable[[bool], None], call_ended: Callable[[bool], None]) -> None:
        self.host = host
        self._connected = connected
        self._call_ended = call_ended
        self._task: asyncio.Task | None = None

    def start(self, hass) -> None:
        self._task = hass.async_create_background_task(self._run(), "mira_fritz call monitor")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, PORT)
            except OSError as err:
                _LOGGER.debug("call monitor not reachable (%s); asking every minute", type(err).__name__)
                self._connected(False)
                await asyncio.sleep(RECONNECT)
                continue
            self._connected(True)
            _LOGGER.info("listening to the FRITZ!Box's call monitor")
            try:
                await self._listen(reader)
            except OSError:
                pass
            finally:
                writer.close()
            self._connected(False)
            await asyncio.sleep(RECONNECT)

    async def _listen(self, reader: asyncio.StreamReader) -> None:
        calls: dict[str, bool] = {}
        while line := await reader.readline():
            if (ended := incoming_ended(line.decode(errors="replace"), calls)) is not None:
                self._call_ended(ended)


# The box's answering machines take a call on extensions 40 to 49 (tried
# 2026-10-30: CONNECT on 41).
TAM_EXTENSIONS = range(40, 50)


def incoming_ended(line: str, calls: dict[str, bool]) -> bool | None:
    """One line of the monitor ("date;RING;id;..."). When an incoming call
    ended: whether an answering machine took it; else None. calls keeps the
    connection ids that rang, and whether a machine took them. No number is
    kept or logged."""
    parts = line.strip().split(";")
    if len(parts) < 4:
        return None
    kind, call_id = parts[1], parts[2]
    if kind == "RING":
        calls[call_id] = False
    elif kind == "CONNECT" and call_id in calls:
        calls[call_id] = parts[3].isdigit() and int(parts[3]) in TAM_EXTENSIONS
    elif kind == "DISCONNECT" and call_id in calls:
        return calls.pop(call_id)
    return None
