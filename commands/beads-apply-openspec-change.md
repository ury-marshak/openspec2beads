---
name: beads:apply-openspec-change
description: Implement an OpenSpec change through Beads by syncing tasks into Beads, working ready items, and syncing status back into OpenSpec.
arguments: "[change-name]"
---

Implement an OpenSpec change through **Beads** instead of the stock `/opsx:apply` task-checkbox loop.

This command wraps the Beads-backed implementation flow:
- `ops2beads inspect`
- `ops2beads sync`
- `br ready` / claim / implement / close
- `ops2beads sync` back into `tasks.md`

When all implementation work is complete, the next step is usually `/opsx:archive`.

---

**Input**: Optionally specify a change name (e.g. `/beads:apply-openspec-change add-dark-mode`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST ask the user to choose an active change.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - infer from conversation context if the user mentioned a change
   - auto-select if only one active change exists
   - if ambiguous, inspect available changes and ask the user to choose

   Always announce: `Using change: <name>` and how to override it.

2. **Check that the change is ready for Beads-backed implementation**

   Verify:
   - `openspec/changes/<name>/` exists
   - the change has `tasks.md`
   - `br` is installed and available
   - Beads is initialized in the repo before the first real sync

   If Beads is not initialized, explain that `br init` is required before the first non-dry-run sync.

3. **Inspect the OpenSpec change first**

   Run:

   ```bash
   python3 skills/openspec2beads/scripts/ops2beads.py inspect <name> --json
   ```

   Summarize:
   - `warnings`
   - `analysisWarnings`
   - `suggestedGaps`
   - `readiness`

   **Handle states:**
   - If inspect shows serious planning gaps, pause and recommend refining OpenSpec first
   - If inspect is broadly acceptable, proceed to sync
   - If the user wants review before mutation, offer a dry-run sync

   Important policy:
   - `inspect` is advisory only
   - do not create Beads work from inspect suggestions alone
   - only explicit OpenSpec tasks should become Beads issues

4. **Sync OpenSpec tasks into Beads**

   If the user wants a preview first, run:

   ```bash
   python3 skills/openspec2beads/scripts/ops2beads.py sync <name> --dry-run --json
   ```

   For a real sync, run:

   ```bash
   python3 skills/openspec2beads/scripts/ops2beads.py sync <name> --json
   ```

   After sync:
   - treat Beads as the execution tracker
   - use Beads state as the source of truth for completion
   - expect `tasks.md` to be updated by later syncs

5. **Read current execution state from Beads**

   Start from ready work:

   ```bash
   br ready
   ```

   Then inspect the next relevant item:

   ```bash
   br show <id>
   ```

   If useful, also read:
   - `openspec/changes/<name>/beads-summary.md`
   - `openspec/changes/<name>/tasks.md`

6. **Implement ready Beads items (loop until done or blocked)**

   For each ready item:
   - show which Beads item is being worked on
   - inspect it with `br show <id>`
   - claim or start it
   - implement the required code changes
   - run relevant checks/tests when appropriate
   - close the item when complete

   Typical commands:

   ```bash
   br update <id> --claim
   br close <id> --reason "Completed"
   ```

   **Pause if:**
   - the Beads item is unclear
   - implementation reveals a planning or design issue
   - no item is ready
   - a blocker or command failure occurs
   - the user interrupts

7. **Sync status back into OpenSpec**

   After completing one or more Beads items, run:

   ```bash
   python3 skills/openspec2beads/scripts/ops2beads.py sync <name> --json
   ```

   This mirrors Beads IDs and statuses back into `tasks.md`.

8. **On completion or pause, show status**

   Display:
   - change name
   - inspect/sync summary
   - Beads items completed this session
   - overall progress
   - if all work appears done, suggest `/opsx:archive <name>`
   - if paused, explain why and wait for guidance

**Authority Model**

Use this mental model throughout:

- **OpenSpec is authoritative for planning structure**
  - which tasks exist
  - task wording
  - dependency intent
- **Beads is authoritative for execution state**
  - issue IDs
  - open / in_progress / closed
  - what is actually complete

Expected implications:
- if the user wants a new Beads issue, add it to OpenSpec first, then sync
- if inspect suggests missing tests or rollback work, that stays advisory until added to OpenSpec
- if Beads and `tasks.md` disagree, Beads wins on sync

**Output During Implementation**

```text
## Implementing via Beads: <change-name>

Using change: <change-name>
Inspect says the plan is ready to sync, with one advisory suggestion about test coverage.
Synced OpenSpec tasks into Beads.

Working on Beads item bd-123: <task description>
[...implementation happening...]
✓ Beads item complete
✓ Synced status back into tasks.md
```

**Output On Completion**

```text
## Beads Implementation Complete

**Change:** <change-name>
**Progress:** all synced Beads items complete

### Completed This Session
- [x] bd-123 Task 1
- [x] bd-124 Task 2

All current Beads work is complete and status has been synced back into OpenSpec.
Next step: /opsx:archive <change-name>
```

**Output On Pause (Issue Encountered)**

```text
## Beads Implementation Paused

**Change:** <change-name>

### Issue Encountered
<description of the issue>

**Options:**
1. refine OpenSpec artifacts first
2. review a dry-run sync
3. stop here

What would you like to do?
```

**Guardrails**

- always run `inspect` before the first real sync in a session
- prefer dry-run sync when the user wants review before mutation
- do not create Beads work that is not explicit in OpenSpec
- do not manually check off OpenSpec tasks when Beads is the execution source of truth
- sync back into OpenSpec after implementation progress
- pause on ambiguity, blockers, or planning drift
- keep code changes minimal and scoped to the current Beads item
