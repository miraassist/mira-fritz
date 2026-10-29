# Working on Mira FRITZ!Box

A Home Assistant integration (`custom_components/mira_fritz`) for a FRITZ!Box's phone book, answering machines and
call list. It is used by Mira ([miraassist/mira](https://github.com/miraassist/mira)) and works without her. The
rules are Mira's.

## How work goes

- **Plan, propose, go, build.** What you notice is a proposal with options; wait for a go. Build exactly what was
  asked. A question is answered, not acted on.
- **Every question with lettered options** (A, B, C), also yes/no; several decisions numbered (1, 2, 3).
- **No fallbacks or workarounds of your own**: an edge case or a problem is discussed first.
- **Replies to the maintainer in German**; everything in the repository in English (specs, code, comments,
  commits), except the user-facing texts, which come in German and English.

## Specs first

- A feature starts as `docs/spec/<topic>.md` with its goal, the decisions (with date), what it does, and numbered
  **Steps**; its testable rules in `docs/spec/<topic>.feature`.
- Every scenario has a fixed id (`FZ-07`) that is never reused, and a tag `@stepN` for the step that builds it.
- A built step goes into `BUILT_STEPS` in `tests/test_scenarios.py`; every scenario of it then needs a test named
  `test_FZ07_…`.
- The spec's status line and its steps say what is built.

## Design rules

- **Do not rebuild what Home Assistant offers.** `fritzconnection` at the version core's `fritz` pins; entities,
  events, actions with a response, a media source, as Home Assistant does them.
- **Convention over configuration; few settings.** A setting for an edge case is not added. A setting lives in one
  place only: the FRITZ!Box's access is here, nowhere in Mira.
- **The interface with Mira** (actions, their data and responses, entity ids): new fields are optional both ways, so
  an older Mira and an older integration keep working. Check every change of it against Mira.
- **Phone numbers never in states or recorded attributes**; the actions give them.
- **User-facing texts** (config flow, options, repairs) are for Home Assistant users who are not technical: the next
  click, no terms they do not know.
- **Keep it understandable**: the simple variant; no elaborate safeguards where the worst case is a nuisance.
- **Public repository**: no facts of a real setup (addresses, host names, users, paths, secrets), only abstract
  recipes. The FRITZ!Box's factory address is a fact of the product and may appear.

## Releasing

- **Semantic versioning** in `manifest.json`: a patch for fixes, a minor version for features and changed
  configuration. Every live change gets a new version.
- **`scripts/check.sh` before every push** (pytest with the scenario check, hassfest).
- Push and tags only to `origin` (miraassist).
