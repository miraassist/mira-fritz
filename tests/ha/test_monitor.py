"""The call monitor (fritz.md, Told, not asked)."""

from custom_components.mira_fritz.callmonitor import incoming_ended
from custom_components.mira_fritz.const import SAFETY_INTERVAL, SCAN_INTERVAL

from .conftest import FakeMonitor, call, setup


def test_FZ50_an_incoming_call_that_ended_is_told():
    calls: dict[str, bool] = {}
    lines = [
        # missed: rang, nobody took it (as the box sent it 2026-10-30)
        "30.10.26 00:22:11;RING;0;01751234567;77310;SIP2;",
        "30.10.26 00:22:14;DISCONNECT;0;0;",
        # the answering machine took it, on extension 41
        "30.10.26 00:22:45;RING;0;01751234567;0301234;SIP0;",
        "30.10.26 00:22:50;CONNECT;0;41;01751234567;",
        "30.10.26 00:23:07;DISCONNECT;0;17;",
        # outgoing, and what does not read
        "30.10.26 08:01:00;CALL;1;10;0301234;0309876;SIP0;",
        "30.10.26 08:01:30;DISCONNECT;1;0;",
        "garbage",
    ]
    assert [incoming_ended(line, calls) for line in lines] == [None, False, None, None, True, None, None, None]


async def test_FZ51_the_monitor_reads_after_a_call_and_asks_only_as_a_safety_net(hass, box, entry):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    monitor = FakeMonitor.last
    assert coordinator.update_interval == SCAN_INTERVAL
    monitor.connected(True)
    assert coordinator.update_interval == SAFETY_INTERVAL
    box.call_list = [call(7)]
    monitor.call_ended(False)
    await hass.async_block_till_done()
    assert [c.id for c in coordinator.data.calls] == [7]
    monitor.connected(False)
    assert coordinator.update_interval == SCAN_INTERVAL


async def test_FZ52_after_the_answering_machine_it_reads_until_the_message_is_there(hass, box, entry):
    from unittest.mock import patch

    from .conftest import message

    await setup(hass, entry)
    coordinator = entry.runtime_data
    reads = box.reads
    waits: list[float] = []

    async def wait(delay):  # the box saves the recording while we wait
        waits.append(delay)
        box.msgs = [message(1)]

    with patch("custom_components.mira_fritz.coordinator.asyncio.sleep", wait):
        await coordinator._read_after_call(True)
    assert waits == [2] and box.reads == reads + 2
    assert [m.id for m in coordinator.data.messages] == ["0:1"]
