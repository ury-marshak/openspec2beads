---
name: ops2beads
description: Translate OpenSpec change artifacts into Beads issues with the local ops2beads tool. Use when the OpenSpec change needs to be converted to Beads tasks or vice versa.
---

Use the local tool at `./scripts/ops2beads.py` from this skill directory.

## Preferred workflow

1. Identify the target as either:
   - a change id like `add-dark-mode`
   - or a path like `openspec/changes/add-dark-mode`
2. Prefer read-only inspection first:
   - `python3 ./scripts/ops2beads.py inspect <target> --json`
3. Review the inspect analysis before syncing:
   - `warnings`: artifact-level concerns such as missing `design.md`
   - `analysisWarnings`: task-quality concerns such as tasks that appear too broad
   - `suggestedGaps`: likely missing work such as tests, rollback, monitoring, or resilience
   - `readiness`: advisory summary of whether sync is reasonable now
4. Decide with the user how to respond:
   - proceed to sync as-is
   - edit `tasks.md`
   - revise `design.md` or spec artifacts
   - ask the user whether to refine the plan first
5. Preview a full sync if the user wants a dry run first:
   - `python3 ./scripts/ops2beads.py sync <target> --dry-run --json`
6. Run sync:
   - first run bootstraps the Beads mapping
   - later runs sync OpenSpec planning changes into Beads and mirror Beads status back into local artifacts
   - `python3 ./scripts/ops2beads.py sync <target> --json`

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

- Use `inspect` first and interpret its advisory output before writing anything.
- Treat `analysisWarnings` and `suggestedGaps` as recommendations, not automatic work items.
- If inspect reports likely missing work, prefer updating OpenSpec artifacts first so the approved plan stays authoritative.
- Use `sync` as the default write command once OpenSpec planning artifacts exist.
- Run `sync` again after `tasks.md`, `design.md`, or `specs/` change.
- If `beads-handoff.json` is missing, `sync` bootstraps it automatically.
- `sync` must remain faithful to explicit OpenSpec tasks; it should not invent new Beads issues from advisory inspect output.

## Agent decision policy

- If inspect shows only mild suggestions, summarize them briefly and ask whether to proceed.
- If inspect shows broad tasks, missing tests, missing rollback, or missing resilience/monitoring coverage, recommend refining OpenSpec before sync.
- If the user explicitly wants to proceed anyway, you may run `sync`, but note that only explicit OpenSpec tasks will be created in Beads.
- When appropriate, offer concrete next steps such as:
  - "I can update `tasks.md` to add explicit test tasks first."
  - "I can help refine the broad task into smaller OpenSpec tasks before syncing."
  - "I can run `sync --dry-run` now so you can review the approved plan without mutating Beads."
