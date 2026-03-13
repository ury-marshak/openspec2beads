---
name: ops2beads-handoff
description: Translate OpenSpec change artifacts into Beads issues with the local ops2beads tool. Use when a repo contains ops2beads.py and the user wants to inspect or sync an OpenSpec change id or change directory into Beads, with Beads authoritative for execution status and OpenSpec authoritative for planning structure.
---

Use the local tool at `../ops2beads.py` from this skill directory.

## Preferred workflow

1. Identify the target as either:
   - a change id like `add-dark-mode`
   - or a path like `openspec/changes/add-dark-mode`
2. Prefer read-only inspection first:
   - `python3 ../ops2beads.py inspect <target> --json`
3. Preview a full sync if the user wants a dry run first:
   - `python3 ../ops2beads.py sync <target> --dry-run --json`
4. Run sync:
   - first run bootstraps the Beads mapping
   - later runs sync OpenSpec planning changes into Beads and mirror Beads status back into local artifacts
   - `python3 ../ops2beads.py sync <target> --json`

## Common flags

- Add `--project-root <path>` only when passing a change id from outside the repo root.
- Add `--allow-task-only` only when the change intentionally has no `specs/` directory.
- Prefer `--json` for agent use.

## Conflict policy

Apply this mental model while operating the tool:

- OpenSpec is authoritative for planning structure:
  - task existence
  - task text
  - dependency graph
- Beads is authoritative for execution state:
  - issue IDs
  - issue status
  - checkbox mirroring in `tasks.md`

Expected outcomes:
- if a task disappears from OpenSpec, keep the Beads issue and report it as stale
- if `tasks.md` says checked but Beads is still open, rewrite the task as unchecked
- if Beads says closed, rewrite the task as checked

## Outputs

The tool writes:

- `openspec/changes/<change>/beads-handoff.json`
- `openspec/changes/<change>/beads-summary.md`
- updated `openspec/changes/<change>/tasks.md` during `sync`

## Operator guidance

- Use `sync` as the default write command once OpenSpec planning artifacts exist.
- Run `sync` again after `tasks.md`, `design.md`, or `specs/` change.
- If `beads-handoff.json` is missing, `sync` bootstraps it automatically.
