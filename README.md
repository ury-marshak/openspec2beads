# ops2beads PoC

Proof-of-concept implementation of OpenSpec → Beads Option C.

## What it does

`ops2beads.py` reads an OpenSpec change from:

- `openspec/changes/<change>/proposal.md`
- `openspec/changes/<change>/design.md` (optional)
- `openspec/changes/<change>/tasks.md`
- `openspec/changes/<change>/specs/**/*.md`

It then:

1. builds a normalized handoff plan
2. writes `beads-handoff.json`
3. writes `beads-summary.md`
4. optionally creates Beads issues via `br` on first handoff, then mirrors Beads status on later handoff runs
5. can annotate `tasks.md` with `[beads: <id> status: <status>]` tags

## Commands

```bash
# inspect inferred work items
python3 ops2beads.py inspect --change <change>

# persist the normalized plan only
python3 ops2beads.py plan --change <change>

# preview Beads handoff without mutating .beads/
python3 ops2beads.py handoff --change <change> --dry-run

# first run: create/update Beads issues from the current OpenSpec artifacts
# later runs: mirror current Beads status from the saved handoff
python3 ops2beads.py handoff --change <change>

# rebuild the plan and reconcile it against an existing handoff
python3 ops2beads.py reconcile --change <change>
```

Repeated `handoff` is status-aware:
- first run bootstraps the Beads mapping
- later runs refresh current Beads statuses from `.beads/`
- with `--annotate-tasks`, it writes tags like `[beads: bd-123 status: in_progress]`
- if a Beads issue is `closed`, the corresponding task checkbox is mirrored as `- [x]`

Useful options:

```bash
# target a different repo
python3 ops2beads.py handoff --project-root ~/sources/myrepo --change add-dark-mode

# update tasks.md with Beads IDs during plan/handoff/reconcile
python3 ops2beads.py handoff --change add-dark-mode --annotate-tasks
```

## Notes

- The tool is non-interactive and agent-friendly.
- It keeps rerun state in `openspec/changes/<change>/beads-handoff.json`.
- `handoff` is now two-phase by existence of the saved handoff file:
  - no handoff file yet: create the Beads mapping
  - handoff file already exists: mirror Beads status back into the saved handoff and optionally `tasks.md`
- `reconcile` reports stale work items that disappeared from `tasks.md` and preserves their old Beads IDs for manual review.
- Dependency inference is still heuristic, but it now combines:
  - explicit `after` / `depends on` task references
  - shared vocabulary between foundational and later tasks
  - same-section / same-major-group relationships
- It expects an initialized Beads workspace for `handoff` or `reconcile` without `--dry-run`.
