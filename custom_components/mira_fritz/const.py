"""Constants of Mira FRITZ!Box."""

from datetime import timedelta

DOMAIN = "mira_fritz"
# The address a FRITZ!Box has out of the box.
DEFAULT_HOST = "192.168.178.1"
CONF_PHONEBOOKS = "phonebooks"
# Asking the box: every minute while its call monitor is not there, as a
# safety net while it is (fritz.md, Told, not asked).
SCAN_INTERVAL = timedelta(seconds=60)
SAFETY_INTERVAL = timedelta(minutes=15)
# After a call an answering machine took, how long to wait before each read
# again until its message is there (seconds; it took 2, tried 2026-10-30).
TAM_SAVED = (2, 3, 5)
# How far back the call list is read.
CALL_DAYS = 7

EVENT_NEW_MESSAGE = "new_message"
EVENT_MISSED_CALL = "missed_call"

# A caller the box has no name for, in Home Assistant's language.
UNKNOWN = {"de": "unbekannt"}
UNKNOWN_DEFAULT = "unknown"
