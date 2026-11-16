# Hermes focus-window-planner tap

A reusable, offline daily focus planner: place tasks by priority/deadline around
calendar events, reserve meeting buffers and report work that does not fit.
It supports all-day events, explicit timezone offsets, incomplete-calendar holds
and optional task splitting. It uses Python 3.11+ and its standard library.

This public GitHub Hermes skills tap contains the skill, fictional input,
implementation, tests and attribution;
it does not need the assignment application, credentials or live accounts.

## Use locally

From the repository root:

```bash
python3 skills/focus-window-planner/scripts/plan_focus.py --pretty < skills/focus-window-planner/examples/fictional-day.json
python3 -m unittest discover -s tests -v
```

The script reads JSON from stdin and emits a proposal on stdout. It does not
read calendar accounts, inspect environment secrets, access the network or
create/edit events. The input timezone requires an IANA timezone database;
systems without one must supply it through their normal Python/system setup.

## Install as a public Hermes tap

```bash
hermes skills tap add sudo-prem/hermes-focus-tap
hermes skills install sudo-prem/hermes-focus-tap/skills/focus-window-planner
```

Review the native scanner result. Do not force installation past a dangerous
scan. Then invoke the installed focus-window-planner skill with a planning date,
timezone, complete schedule and task durations/priorities, or run its installed
helper against the included fictional example.

The tested pinned Hermes GitHub adapter resolves one repository revision before
fetching a skill and records its source revision. For independent installation evidence, record
the actual commit SHA, successful native scan/install and execution in a fresh
isolated HERMES_HOME. Verify the installed bytes against that revision. A local
bundle rehearsal is useful preparation but is not a public-tap install result.

## Interpretation and attribution

Placement is deterministic and greedy, not a globally optimal task solver.
Calendar completeness is a caller-provided assertion. Proposed work is not
completed work, and no allocation is itself permission to act on an account.
Meeting buffers do not automatically insert breaks between adjacent focus chunks.

Original implementation developed for Assignment 3 with Codex assistance. Python
datetime/zoneinfo and JSON provide the standard-library primitives. The planner
does not import or copy the assignment's calendar backend or depend on its
private configuration. Hermes supplies discovery, scanning and installation.

License: MIT; see LICENSE. Publish only this tap directory, never private calendar
exports or the surrounding assignment workspace.
