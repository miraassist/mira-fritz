"""Constants of Mira FRITZ!Box."""

from datetime import timedelta

DOMAIN = "mira_fritz"
# The address a FRITZ!Box has out of the box.
DEFAULT_HOST = "192.168.178.1"
CONF_PHONEBOOKS = "phonebooks"
SCAN_INTERVAL = timedelta(seconds=60)
# How far back the call list is read.
CALL_DAYS = 7

EVENT_NEW_MESSAGE = "new_message"
EVENT_MISSED_CALL = "missed_call"

# A caller the box has no name for, in Home Assistant's language.
UNKNOWN = {"de": "unbekannt"}
UNKNOWN_DEFAULT = "unknown"
