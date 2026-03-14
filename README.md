# ops2beads PoC

Proof-of-concept implementation of OpenSpec → Beads Option C.

## What it does

`skills/ops2beads/scripts/ops2beads.py` reads an OpenSpec change from:

- `openspec/changes/<change>/proposal.md`
- `openspec/changes/<change>/design.md` (optional)
- `openspec/changes/<change>/tasks.md`
- `openspec/changes/<change>/specs/**/*.md`

It then:

1. builds a normalized handoff plan
2. performs inspect-time advisory analysis of task quality and likely planning gaps
3. writes `beads-handoff.json`
4. writes `beads-summary.md`
5. syncs planning changes into Beads via `br`
6. mirrors Beads IDs and live statuses back into `tasks.md`

## Recommended workflow

```bash
# inspect inferred work items and advisory analysis
python3 skills/ops2beads/scripts/ops2beads.py inspect <change-id>
# or
python3 skills/ops2beads/scripts/ops2beads.py inspect openspec/changes/<change-id>

# if inspect reports likely gaps, refine OpenSpec artifacts first

# preview the full sync without changing Beads or local files
python3 skills/ops2beads/scripts/ops2beads.py sync <change-id> --dry-run

# bootstrap on first run; afterwards sync plan changes and mirror status
python3 skills/ops2beads/scripts/ops2beads.py sync <change-id>
# or
python3 skills/ops2beads/scripts/ops2beads.py sync openspec/changes/<change-id>
```

`sync` applies this authority model:
- OpenSpec is authoritative for planning structure
  - task existence
  - titles/descriptions
  - dependency graph
- Beads is authoritative for execution state
  - issue IDs
  - open / in_progress / closed status
  - task checkbox mirroring

`inspect` is allowed to critique the plan:
- infer suggested metadata such as priority, suggested type, and complexity
- warn about broad tasks or weak planning structure
- report suggested gaps such as missing tests, rollback coverage, monitoring, or resilience work

Important boundary:
- advisory output from `inspect` is **not** converted into Beads issues automatically
- `sync` only reconciles explicit OpenSpec tasks that already exist in `tasks.md`

Conflict policy:
- if a task is removed from OpenSpec but the Beads issue still exists, report it as stale; do not auto-close it
- if `tasks.md` is checked off but the Beads issue is still open, Beads wins and the task is rewritten as unchecked
- if a Beads issue is closed, the corresponding task is mirrored as `- [x]`

## Inspect output

`inspect --json` now includes advisory fields such as:

- `analysisWarnings`
- `suggestedGaps`
- `readiness`

and enriches each explicit OpenSpec work item with inferred metadata such as:

- `suggestedType`
- `priority`
- `complexity`
- `origin`

These fields are meant to help an operator or AI agent decide whether to refine OpenSpec before syncing.

## Notes

- The tool is non-interactive and agent-friendly.
- The supported commands are now `inspect` and `sync`.
- It keeps rerun state in `openspec/changes/<change>/beads-handoff.json`.
- `sync` always updates local artifacts; no `--annotate-tasks` switch is required.
- `tasks.md` annotations look like `[beads: bd-123 status: in_progress]`.
- `sync` reports stale work items that disappeared from `tasks.md` and preserves their old Beads IDs for manual review.
- Dependency inference is still heuristic, but it combines:
  - explicit `after` / `depends on` task references
  - shared vocabulary between foundational and later tasks
  - same-section / same-major-group relationships
- Advisory planning analysis is deterministic but conservative; the agent or user decides whether to amend OpenSpec.
- It expects an initialized Beads workspace for `sync` without `--dry-run`.
