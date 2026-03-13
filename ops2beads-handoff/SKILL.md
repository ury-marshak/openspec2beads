---
name: ops2beads-handoff
description: Translate OpenSpec change artifacts into Beads issues with the local ops2beads tool. Use when a repo contains ops2beads.py and the user wants to inspect, plan, hand off, or reconcile an OpenSpec change under openspec/changes/CHANGE_NAME into Beads, including status-aware task annotations on repeated handoff runs.
---

Use the local tool at `../ops2beads.py` from this skill directory.

## Workflow

1. Confirm the target change name under `openspec/changes/<change>/`.
2. Prefer read-only inspection first:
   - `python3 ../ops2beads.py inspect --change <change> --json`
3. Generate or refresh the normalized plan when needed:
   - `python3 ../ops2beads.py plan --change <change> --json`
4. Preview the first handoff before writing if the user has not asked for direct execution:
   - `python3 ../ops2beads.py handoff --change <change> --dry-run --json`
5. Run handoff:
   - first run creates or updates Beads issues
   - later runs refresh Beads status from the saved handoff
   - `python3 ../ops2beads.py handoff --change <change> --json`
6. Rebuild from changed OpenSpec artifacts and reconcile existing Beads state:
   - `python3 ../ops2beads.py reconcile --change <change> --json`

## Common flags

- Add `--project-root <path>` when running outside the repo root.
- Add `--annotate-tasks` on `plan`, `handoff`, or `reconcile` to write `[beads: <id> status: <status>]` tags into `tasks.md`.
- On a repeated `handoff`, combine `--annotate-tasks` with status refresh to mirror Beads state into `tasks.md`.
- Add `--allow-task-only` only when the change intentionally has no `specs/` directory.

## Expectations

- Expect OpenSpec inputs in:
  - `openspec/changes/<change>/proposal.md`
  - `openspec/changes/<change>/tasks.md`
  - `openspec/changes/<change>/design.md` (optional)
  - `openspec/changes/<change>/specs/**/*.md`
- Expect Beads to be initialized before non-dry-run `handoff` or `reconcile`.
- Prefer `--json` for agent use and parse `beads-handoff.json` for stable mappings.

## Outputs

The tool writes:

- `openspec/changes/<change>/beads-handoff.json`
- `openspec/changes/<change>/beads-summary.md`
- optionally updated `openspec/changes/<change>/tasks.md`

## Operator guidance

- Use `inspect` or `handoff --dry-run` before mutating Beads when the dependency graph is uncertain.
- Use `reconcile` after `tasks.md`, `design.md`, or `specs/` change.
- Use a repeated `handoff` when the user wants `tasks.md` to reflect current Beads status, especially after issues are claimed or closed.
- If `beads-handoff.json` is missing, the first `handoff` bootstraps it; `reconcile` still requires an existing handoff.
