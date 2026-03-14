# OpenSpec → Beads bridge

Use this when you want to keep **OpenSpec** as the planning system, but use **Beads** (`br`) for the implementation stage.

Use `/beads:apply-openspec-change` instead of stock `/opsx:apply` for Beads-backed implementation.

Workflow:

```text
/opsx:propose
    ↓
refine proposal.md / specs/ / design.md / tasks.md
    ↓
/beads:apply-openspec-change
    ↓
/opsx:archive
```

`/beads:apply-openspec-change` is the Beads-backed implementation step. It wraps the main loop:

```text
ops2beads inspect → ops2beads sync → br ready/claim/implement/close → ops2beads sync back
```

## What goes where

- **OpenSpec** defines the plan:
  - `proposal.md`
  - `specs/`
  - `design.md`
  - `tasks.md`
- **Beads** tracks implementation:
  - issue IDs
  - ready / in progress / closed work

This tool syncs explicit OpenSpec tasks into Beads, then syncs Beads status back into `tasks.md`.

Main script:

- `skills/openspec2beads/scripts/ops2beads.py`

Command draft in this repo:

- `commands/beads-apply-openspec-change.md`

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

### 2. Run the Beads-backed implementation command

```text
/beads:apply-openspec-change add-dark-mode
```

This command:
- inspects the OpenSpec change
- syncs explicit tasks into Beads
- works the next ready Beads items
- syncs Beads status back into `tasks.md`

### 3. Archive in OpenSpec

```text
/opsx:archive add-dark-mode
```

## Manual equivalent

If you want to do the same flow manually, it is:

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
/beads:apply-openspec-change add-dark-mode
/opsx:archive add-dark-mode
```

## Rules of thumb

- If you want a new Beads issue, add the task to OpenSpec first, then sync.
- If OpenSpec changes during implementation, run `/beads:apply-openspec-change` again or re-run `sync` manually.
- If Beads and `tasks.md` disagree, Beads wins on sync.
- `sync` writes:
  - `openspec/changes/<change>/beads-handoff.json`
  - `openspec/changes/<change>/beads-summary.md`
  - updated `openspec/changes/<change>/tasks.md`

## Command-name note

This README uses OpenSpec commands like `/opsx:propose` and `/opsx:archive`, plus the custom integration command `/beads:apply-openspec-change`. Depending on your agent/editor, the exact command syntax may differ; the workflow is the same.
