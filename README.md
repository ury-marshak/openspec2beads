# OpenSpec → Beads bridge

Use this when you want to keep **OpenSpec** as the planning system, but use **Beads** (`br`) for the implementation stage.

Use the `openspec2beads-apply-change` skill instead of stock `/opsx:apply` for Beads-backed implementation.

Workflow:

```text
/opsx:propose
    ↓
refine proposal.md / specs/ / design.md / tasks.md
    ↓
openspec2beads-apply-change
    ↓
/opsx:archive
```

The `openspec2beads-apply-change` skill wraps the Beads-backed implementation loop:

```text
ops2beads inspect → ops2beads sync → br ready/claim/implement/close → ops2beads sync back
```

## What goes where

- **OpenSpec** defines the plan:
  - `proposal.md`
  - `specs/`
  - `design.md`
  - `tasks.md`
- **Beads** tracks execution:
  - issue IDs
  - ready / in progress / closed work

This tool syncs explicit OpenSpec tasks into Beads, then syncs Beads status back into `tasks.md`.

Main script:

- `skills/openspec2beads/scripts/ops2beads.py`

Skill definition in this repo:

- `skills/openspec2beads-apply-change/SKILL.md`

## Before you start

Make sure:

- your repo already uses OpenSpec
- the change exists at `openspec/changes/<change>/`
- `br` is installed
- Beads is initialized in the repo

```bash
br init
```

## Quickstart

### 1. Create the change in OpenSpec

```text
/opsx:propose add-dark-mode
```

### 2. Use the Beads-backed implementation skill

For example:

```text
Use openspec2beads-apply-change for add-dark-mode.
```

Or ask naturally:

```text
Implement add-dark-mode through Beads.
```

The skill will:
- inspect the OpenSpec change
- sync explicit tasks into Beads
- work ready Beads items
- sync Beads status back into `tasks.md`

### 3. Archive in OpenSpec

```text
/opsx:archive add-dark-mode
```

## Manual equivalent

If you want to run the same flow manually:

```bash
python3 skills/openspec2beads/scripts/ops2beads.py inspect add-dark-mode --json
python3 skills/openspec2beads/scripts/ops2beads.py sync add-dark-mode --json
br ready
br show <id>
br update <id> --claim
# implement
br close <id> --reason "Completed"
python3 skills/openspec2beads/scripts/ops2beads.py sync add-dark-mode --json
```

Repeat the `br` loop and final sync until all Beads issues are closed.

## Copy-paste prompt sequence

```text
/opsx:propose add-dark-mode
Use openspec2beads-apply-change for add-dark-mode.
/opsx:archive add-dark-mode
```

## Rules of thumb

- If you want a new Beads issue, add the task to OpenSpec first, then sync.
- If OpenSpec changes during implementation, use the skill again or re-run `sync` manually.
- If Beads and `tasks.md` disagree, Beads wins on sync.
- `sync` writes:
  - `openspec/changes/<change>/beads-handoff.json`
  - `openspec/changes/<change>/beads-summary.md`
  - updated `openspec/changes/<change>/tasks.md`

## Skill note

Some agents expose installed skills through explicit invocation syntax or convenience commands, while others simply make the skill available when asked naturally. So the exact way you invoke `openspec2beads-apply-change` may differ by agent/editor, but the workflow is the same.
