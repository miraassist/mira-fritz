# Mira FRITZ!Box – Spec

Status 2026-10-29: steps 1 to 3 built in the integration and read against a real FRITZ!Box (phone books, messages, a recording, the call list); Mira's side and the release are next. Scenarios: [fritz.feature](fritz.feature).

## Goal

A FRITZ!Box knows the household's phone book, its answering machines and who called. Home Assistant shows little of
it: the core integration `fritz` dials, `fritzbox_callmonitor` says whether a line rings. Two integrations from HACS
cover a half each (one has events and missed calls, the other a media source). Mira needs all of it, at a
satellite:

1. The ring of the Dot in the kitchen glows: a message on the answering machine.
2. Anna: "Habe ich neue Nachrichten?" Mira: "Eine, von Oma, heute um 14:12. Soll ich sie abspielen?"
3. Anna: "Ja." The satellite plays the recording; afterwards it counts as heard, and the ring goes out.
4. Anna: "Wer hat angerufen?" Mira: "Ben, zweimal, zuletzt um 16:40. Er hat keine Nachricht hinterlassen."
5. Anna: "Ruf ihn zurück." (Mira's `phone_call`, with the phone book from here.)

**Mira FRITZ!Box** (`mira_fritz`) brings these into Home Assistant as entities, actions and a media source, usable
without Mira as well (dashboard, automations, any media player). Mira uses it; she keeps no access to the FRITZ!Box of
her own.

## Decided (2026-10-29)

| # | Question | Decision |
|---|---|---|
| 1 | Where the FRITZ!Box is read | In this integration, not in Mira and not by an integration from HACS; Home Assistant's core offers none of it |
| 2 | The phone book | Moves here from Mira's skill `telefon`; the FRITZ!Box's access is in one place. That breaks Mira's current setup; accepted, as few users have it yet |
| 3 | Name | "Mira FRITZ!Box", domain `mira_fritz` (not `fritz` or `fritzbox`, which are core's), repository `miraassist/mira-fritz` |
| 4 | Its own repository | Yes, so it can be used without Mira; HACS takes one integration per repository |
| 5 | Specs | In this repository; Mira's specs point here |

## Setting up

- **Config flow**: address, user, password. The address is filled in with the FRITZ!Box's factory one
  (`192.168.178.1`); only user and password must be typed. The flow tries the login and says what is wrong
  (address not reachable, login refused, a right missing).
- **The FRITZ!Box user**: one of its own for Home Assistant, with the rights **Telefonie** (phone book) and
  **Sprachnachrichten, Faxnachrichten, FRITZ!App Fon und Anrufliste** (answering machine, call list). The flow's
  text says where (FRITZ!Box → System → FRITZ!Box-Benutzer) and which two boxes to tick.
- **Options**: which phone books (all the box has, ticked: the first). Nothing else; the answering machines are all
  read, the box's own switch decides which one answers.
- **One device** per FRITZ!Box, everything below hangs on it.
- **Library**: `fritzconnection`, the version core's `fritz` pins; TR-064 on port 49000.

## What it reads

Every 60 seconds, two calls:

- **Messages** (`X_AVM-DE_TAM`: `GetList`, then `GetMessageList` per answering machine): index, answering machine,
  name (from the box's phone book), number, date, duration, `new`, the path of the recording.
- **Calls** (`X_AVM-DE_OnTel`: `GetCallList`, `days=7`): type (incoming, missed, outgoing, refused), name, number,
  date, duration, and the path of a recording when the answering machine took the call.

A call the answering machine took is a **message**, not a missed call: the call list has it as incoming, with the
path of a recording, and the message has the same number and minute. A **missed call** is one of type missed without a
recording.

**Seen**: the box marks messages as heard (`MarkMessage`), but has no such mark for missed calls. The integration
keeps "seen up to" per FRITZ!Box in Home Assistant's storage: the newest call's id when the missed calls were last
seen (the box numbers calls upwards; a date has only minutes). Missed calls after it are new. At the first start it is
the newest call then, so the calls of the last days are not all new at once.

**Recordings** are fetched where the message list is: on the TR-064 port, with the list's session id and the
message's path. The web port refuses them (tried 2026-10-29).

## Entities

| Entity | State | Attributes |
|---|---|---|
| `sensor.<box>_new_messages` | number of messages not heard | `messages`: name, date, duration per new message |
| `sensor.<box>_missed_calls` | number of missed calls after "seen up to" | `calls`: name, date per new missed call |
| `event.<box>_calls` | the last event | event types `new_message`, `missed_call`, each with name and date |

- **No phone numbers in states or attributes**: they would go to the recorder and to every user's dashboard. The
  attributes are also left out of the recorder; the actions give numbers.
- A call from someone not in the phone book has the name the box gives (often none); the attribute says "unbekannt"
  / "unknown" in Home Assistant's language.
- **Events** come once per new message or missed call, after the first read since the start (what is there at the
  start is not new to Home Assistant, only to the sensors).

## Media source

- `media-source://mira_fritz/<entry>/<tam>/<index>`: one message, playable on every media player, a satellite too.
  Browsable: per answering machine, newest first, titled "Oma – heute 14:12 (0:23)".
- Resolving gives a signed URL of the integration's HTTP view, so a device without a login can fetch it. The view
  fetches the recording from the box at that moment (WAV, as the box keeps it); nothing is stored.

## Actions

All with a response, for every Home Assistant user (not only admins), as reading the call list in the box's own app
is.

| Action | Data | Response |
|---|---|---|
| `mira_fritz.get_messages` | `new_only` (default false) | messages: id, answering machine, name, number, date, duration, new, `media_content_id` |
| `mira_fritz.mark_heard` | `message_ids` (empty: all) | – |
| `mira_fritz.delete_messages` | `message_ids` | – |
| `mira_fritz.get_calls` | `kind` (missed, incoming, outgoing; empty: all), `new_only` | calls: kind, name, number, date, duration, `message_id` |
| `mira_fritz.mark_calls_seen` | – | – |
| `mira_fritz.get_phonebook` | – | books: the names read; url: the box's page; contacts: name, numbers (number, type, main) |

- A message id is `<tam>:<index>` as the box numbers them; it is valid until the message is deleted.
- `get_phonebook` gives the whole chosen books; finding a name stays with whoever asks (Mira: `phone_call`). Fax
  numbers come with their type; whoever dials leaves them out.
- Every action names the FRITZ!Box with `config_entry_id` when there are several; with one it may be left out.

## What Mira uses

Mira's side is specified in Mira's repository; in short:

- **`telefon`** reads the phone book with `get_phonebook` before every call, instead of TR-064. The skill's settings
  (user, password, address, books) go away; without the integration the skill is a problem: "Die Integration Mira
  FRITZ!Box fehlt."
- **The answering machine at the satellite**: the indicator (card, ring) from the two sensors; "Habe ich neue
  Nachrichten?" from `get_messages`; playing by `media_player.play_media` with the message's `media_content_id` at
  the satellite being spoken at; `mark_heard` after playing; `get_calls` and `mark_calls_seen` for missed calls.

## Steps

1. **Repository and setup**: config flow, device, options, `get_phonebook` (built); Mira's `telefon` switches over.
2. **Messages**: reading, `sensor.<box>_new_messages`, the media source, `get_messages`, `mark_heard`,
   `delete_messages` (built).
3. **Calls**: `sensor.<box>_missed_calls`, "seen up to", `get_calls`, `mark_calls_seen`, `event.<box>_calls` (built).
4. **Release** through HACS; the guide's section in Mira.

## Open

- **Mira at the satellite**: whether missed calls and messages show differently (two counts on the screen, two
  colours on the ring) or as one "something new"; and whether Mira only plays a message or may also sum it up
  (that needs the recording sent to a model: a stranger's voice to Google, or local speech recognition).
- **Real time**: the call monitor (port 1012) would say a missed call at once instead of within 60 seconds; for an
  answering machine 60 seconds are enough, so not for now.
