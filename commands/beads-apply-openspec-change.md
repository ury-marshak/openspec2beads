---
name: beads:apply-openspec-change
description: Execute an OpenSpec change through Beads by syncing tasks into Beads, working ready items, and syncing status back into OpenSpec.
arguments: "[change-name]"
---

Implement an OpenSpec change through **Beads** instead of the stock `/opsx:apply` task-checkbox loop.

## Purpose

Use this command when:
- the change is already planned in OpenSpec
- `tasks.md` exists and is ready for implementation
- Beads (`br`) should be the execution tracker

This command is the Beads-backed implementation flow:

```text
OpenSpec plan → ops2beads inspect/sync → br execution loop → ops2beads sync back
```

## Input

Optionally specify a change name, for example:

```text
/beads:apply-openspec-change add-dark-mode
```

If no change name is provided:
- infer it from conversation context if possible
- auto-select if only one active change exists
- otherwise ask the user to choose

Always announce:

```text
Using change: <name>
```

and mention how to override it.

## Preconditions

Before proceeding, verify:
- the repo contains `openspec/changes/<name>/`
- `tasks.md` exists for the change
- `br` is installed and available
- Beads is initialized in the repo if a real sync will be performed

If Beads is not initialized, explain that `br init` is required before the first real sync.

## Workflow

### 1. Inspect the OpenSpec change

Run `ops2beads inspect` first.

Preferred command:

```bash
python3 skills/openspec2beads/scripts/ops2beads.py inspect <change-name> --json
```

Summarize:
- warnings
- task-quality issues
- suggested planning gaps
- readiness

Important policy:
- `inspect` is advisory only
- do not invent new Beads issues from inspect suggestions
- if important planning gaps exist, recommend refining OpenSpec first

If the result shows serious planning issues, pause and ask whether to:
1. refine OpenSpec artifacts first
2. do a dry-run sync anyway
3. proceed with sync as-is

### 2. Preview or perform sync

If the user wants a preview, run:

```bash
python3 skills/openspec2beads/scripts/ops2beads.py sync <change-name> --dry-run --json
```

For a real sync, run:

```bash
python3 skills/openspec2beads/scripts/ops2beads.py sync <change-name> --json
```

After sync, treat Beads as the execution tracker.

### 3. Read current execution state from Beads

Check ready work first.

Typical commands:

```bash
br ready
br show <id>
```

If useful, also inspect the OpenSpec-side outputs:
- `openspec/changes/<name>/beads-summary.md`
- `openspec/changes/<name>/tasks.md`

### 4. Work the next ready Beads item

When a ready item exists:
- select the next ready item
- inspect it with `br show <id>`
- claim or move it into progress
- implement the task in code
- run relevant checks/tests when appropriate
- close the Beads item when complete

Typical commands:

```bash
br update <id> --claim
br close <id> --reason "Completed"
```

If the item is unclear, blocked, or reveals a planning/design problem:
- do not guess
- pause and explain the issue
- recommend updating OpenSpec artifacts if needed

### 5. Sync back into OpenSpec

After completing one or more Beads items, run:

```bash
python3 skills/openspec2beads/scripts/ops2beads.py sync <change-name> --json
```

This mirrors Beads IDs/status back into `tasks.md`.

### 6. Continue until done or paused

Keep looping while there is ready work and no blocker:
- inspect/sync if needed
- pick ready Beads work
- implement
- close item
- sync back

Pause if:
- no ready Beads items exist
- implementation reveals a design/spec/task problem
- the user needs to make a planning decision
- a command fails or the environment is not ready

## Authority model

Use this mental model throughout:

- **OpenSpec is authoritative for planning structure**
  - which tasks exist
  - task wording
  - dependency intent
- **Beads is authoritative for execution state**
  - issue IDs
  - open / in_progress / closed
  - what is actually complete

Implications:
- if the user wants a new Beads issue, add it to OpenSpec first, then sync
- if `inspect` suggests a missing test task, that stays advisory until added to OpenSpec
- if Beads and `tasks.md` disagree, Beads wins on sync

## Expected outputs

During execution, report concise progress such as:

```text
Using change: add-dark-mode
Inspect says the plan is ready to sync, with one advisory suggestion about test coverage.
Synced OpenSpec tasks into Beads.
Next ready item: bd-123 Create ThemeContext.
Claimed bd-123 and starting implementation.
Completed bd-123 and synced status back into tasks.md.
```

If blocked, report clearly:

```text
Implementation paused for add-dark-mode.
Reason: the next Beads item depends on a missing OpenSpec task split.
Options:
1. refine tasks.md first
2. continue with a dry-run review
3. stop here
```

If all work is complete, suggest:

```text
All Beads items for <change-name> appear complete and status has been synced back into OpenSpec.
Next step: /opsx:archive <change-name>
```

## Guardrails

- always run `inspect` before the first real sync in a session
- prefer a dry-run sync when the user wants review before mutation
- do not create Beads work that is not explicit in OpenSpec
- do not mark OpenSpec tasks done manually when Beads is the source of execution truth
- sync back into OpenSpec after implementation progress
- pause on ambiguity, blockers, or planning drift
- keep code changes scoped to the current Beads item
