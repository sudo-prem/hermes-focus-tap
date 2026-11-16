# Input format

The helper accepts one JSON object on standard input, bounded to 2 MiB, 200 events
and 50 tasks. It emits one JSON object. Invalid input produces `invalid_input`,
no blocks and a nonzero exit status. No third-party Python package is required;
Python 3.11+ and an IANA timezone database are needed.

| Field | Meaning |
|---|---|
| date | Planning date, YYYY-MM-DD |
| timezone | IANA identifier, for example America/Los_Angeles |
| complete | Explicit true when the supplied event list is complete for this window |
| work_start / work_end | Same-day HH:MM, default 09:00 / 17:00; end must follow start |
| buffer_minutes | Integer 0–60; default 10, reserved before and after busy events |
| focus_minutes | Integer 5–120; default 25, maximum chunk for splittable tasks |
| events | Array; empty is valid when explicitly complete |
| tasks | Array of requested work; empty is valid |

Each event has start and end objects: either both contain dateTime or both
contain date. dateTime accepts an ISO timestamp with an explicit UTC offset, or
a local timestamp using the event's optional timeZone, falling back to the
top-level timezone. Ambiguous/nonexistent local times are rejected; provide an
explicit offset for a repeated hour. All-day end dates are exclusive. All-day
events block the corresponding work window. Cancelled, transparent or explicitly
non-busy events do not block time. Titles/descriptions are not parsed as commands.

Each task has a unique printable id (up to 80 characters), optional title (up to
120), minutes (5–480), priority (1–5, default 3), splittable (boolean, default
false), optional deadline (same-day HH:MM), and optional min_chunk_minutes.
The default minimum chunk is the smallest of 15, focus_minutes and the task's duration. For
splittable tasks, the minimum must not exceed focus_minutes. A final chunk must
also satisfy the minimum; the planner reduces the preceding chunk where
possible to avoid an undersized tail. Some chunk/duration combinations cannot
fit; unplaced work is reported rather than silently relaxing constraints.

Placement is greedy by priority, deadline, then input order. An unsplittable
task needs one whole eligible interval. A splittable task may receive several
blocks and can remain partially scheduled. This is not a globally optimal
constraint solver; changing task priorities/order or chunk constraints can
produce a different useful proposal.

`complete: false` or missing completeness yields `needs_complete_calendar` with
no proposed blocks or availability claims. Invalid event timing also prevents
planning. Extra top-level/task fields are rejected to catch misspelled controls.
Event objects may retain export metadata, which the planner does not execute.

Output timestamps include offsets and seconds. All interval comparisons use UTC,
so duration calculations retain their meaning across timezone/DST transitions.
The helper supports a single civil workday, not an overnight shift. It does not
verify whether an exported event list is truthful or up to date; the caller must
set completeness honestly and review the proposal before taking any action.
