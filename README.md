# OpenSpec → Beads bridge

Use this when you want to keep **OpenSpec** as the planning system, but use **Beads** (`br`) for the implementation stage.

Workflow:

```text
/opsx:propose
    ↓
refine proposal.md / specs/ / design.md / tasks.md
    ↓
ops2beads inspect
    ↓
ops2beads sync
    ↓
br execution loop
(ready → claim → implement → close)
    ↓
ops2beads sync
    ↓
/opsx:archive
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

### 2. Inspect the plan

```text
Use openspec2beads to inspect change add-dark-mode and summarize anything I should fix before syncing to Beads.
```

```bash
python3 skills/openspec2beads/scripts/ops2beads.py inspect add-dark-mode --json
```

If needed, fix OpenSpec first. `inspect` is advisory only.

### 3. Preview the sync

```text
Use openspec2beads to dry-run the sync for add-dark-mode.
```

```bash
python3 skills/openspec2beads/scripts/ops2beads.py sync add-dark-mode --dry-run --json
```

### 4. Sync into Beads

```text
Use openspec2beads to sync change add-dark-mode into Beads.
```

```bash
python3 skills/openspec2beads/scripts/ops2beads.py sync add-dark-mode --json
```

### 5. Implement from Beads

```bash
br ready
br show <id>
br update <id> --claim
# implement
br close <id> --reason "Completed"
```

Typical prompts:

```text
Show me the ready Beads issues for add-dark-mode.
```

```text
Pick the next ready Beads issue for add-dark-mode and implement it.
```

### 6. Re-sync back into OpenSpec

```text
Use openspec2beads to sync add-dark-mode again and mirror Beads status back into tasks.md.
```

```bash
python3 skills/openspec2beads/scripts/ops2beads.py sync add-dark-mode --json
```

### 7. Archive in OpenSpec

```text
/opsx:archive add-dark-mode
```

## Copy-paste prompt sequence

```text
/opsx:propose add-dark-mode
Use openspec2beads to inspect change add-dark-mode and summarize anything I should fix before syncing to Beads.
Use openspec2beads to dry-run the sync for add-dark-mode.
Use openspec2beads to sync change add-dark-mode into Beads.
Show me the ready Beads issues for add-dark-mode.
Pick the next ready Beads issue for add-dark-mode and implement it.
Use openspec2beads to sync add-dark-mode again and mirror Beads status back into tasks.md.
Repeat until all Beads issues are closed.
/opsx:archive add-dark-mode
```

## Rules of thumb

- If you want a new Beads issue, add the task to OpenSpec first, then sync.
- If OpenSpec changes during implementation, run `sync` again.
- If Beads and `tasks.md` disagree, Beads wins on sync.
- `sync` writes:
  - `openspec/changes/<change>/beads-handoff.json`
  - `openspec/changes/<change>/beads-summary.md`
  - updated `openspec/changes/<change>/tasks.md`

## Command-name note

This README uses commands like `/opsx:propose` and `/opsx:archive`. Your OpenSpec installation may use slightly different names; the workflow is the same.
