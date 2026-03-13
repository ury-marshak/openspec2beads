# OpenSpec → Beads Option C: External Translator Handoff

## Goal

Sketch an implementation of **Option C**:

> Keep standard OpenSpec artifacts mostly unchanged, then run an external conversion step after planning (typically after `/opsx:ff` or just before `/opsx:apply`) that reads the OpenSpec change artifacts and creates a detailed Beads issue collection for parallel execution.

This approach deliberately avoids modifying OpenSpec internals. It treats:

- **OpenSpec** as the planning/specification layer
- **Beads** as the execution/dispatch layer
- a new **translator tool** as the handoff bridge

---

## Why Option C

Option C is the least invasive path because it does **not** require:

- patching OpenSpec workflow commands
- introducing new first-class OPSX commands
- replacing OpenSpec's checkbox-based `apply` progress model
- changing OpenSpec archive/sync logic

It uses the already-available integration seams:

- OpenSpec artifact files in `openspec/changes/<change>/`
- OpenSpec CLI JSON/status/instructions output
- Beads CLI JSON and agent-friendly mutation commands

---

## Summary of the Proposed System

Add a standalone tool, tentatively called:

- `ops2beads`
- or `openspec-beads`
- or `osb`

that performs the following:

1. locate an OpenSpec change
2. read its planning artifacts
3. extract implementation work items and dependencies
4. generate a normalized intermediate issue plan
5. create/update issues in Beads via `br`
6. optionally update `tasks.md` with a Beads handoff summary
7. optionally produce a machine-readable artifact for auditing/replay

### Recommended invocation points

- **After planning is complete**
  - after `/opsx:propose`
  - after `/opsx:ff`
- **Before execution starts**
  - immediately before `/opsx:apply`
- **During replanning**
  - rerun after proposal/spec/design/tasks changes

---

## High-Level Workflow

```text
/opsx:propose or /opsx:ff
        |
        v
OpenSpec change folder populated:
  proposal.md
  specs/**/spec.md
  design.md
  tasks.md
        |
        v
ops2beads handoff
  - parse artifacts
  - infer issue graph
  - emit plan
  - call br create / br dep add
        |
        v
Beads issue collection in .beads/
        |
        v
Parallel execution via br ready / br update --claim / br close
        |
        v
Optional OpenSpec mirror update + verify + archive
```

---

## Desired UX

### Minimal UX

```bash
ops2beads handoff --change add-dark-mode
```

Expected behavior:

1. verify OpenSpec change exists
2. verify required artifacts exist
3. parse proposal/specs/design/tasks
4. show dry-run summary
5. create or update Beads issues
6. print next commands for execution

### Recommended everyday flow

```bash
# planning
/opsx:propose add-dark-mode

# convert plan to beads
ops2beads handoff --change add-dark-mode

# parallel execution uses beads
br ready --json
br update <id> --claim --json
...
br close <id> --reason "done" --json
br sync --flush-only
```

### Useful companion commands

```bash
ops2beads inspect --change add-dark-mode
ops2beads plan --change add-dark-mode --format json
ops2beads handoff --change add-dark-mode --dry-run
ops2beads reconcile --change add-dark-mode
ops2beads mirror --change add-dark-mode
```

---

## Scope of the Translator

### In scope

- read existing OpenSpec artifacts
- build a decomposition suitable for parallel implementation
- create Beads issues and dependency edges
- preserve traceability back to the OpenSpec change
- support reruns without creating duplicates
- support agent-safe, non-interactive operation

### Out of scope for the first version

- modifying OpenSpec source
- replacing `/opsx:apply`
- automatic OpenSpec archive completion from Beads status
- fully semantic requirement-to-code verification
- automatic conflict resolution across multiple OpenSpec changes

---

## Core Design Principle

The translator should produce and persist a **normalized intermediate plan** before calling `br`.

This is important because it separates:

1. **interpretation of OpenSpec artifacts**
2. **mutation of Beads state**

That gives us better:

- testability
- idempotency
- auditability
- diffability
- rerun safety

### Recommended intermediate artifact

Write a generated file such as:

```text
openspec/changes/<change>/beads-handoff.json
```

or

```text
openspec/changes/<change>/beads-plan.json
```

This file should contain:

- source metadata
- extracted work items
- inferred dependencies
- labels/priorities/types
- fingerprints for idempotent reconciliation
- mapping from local work-item keys to Beads issue IDs once created

---

## Proposed File Layout

If implemented as a standalone tool inside a project or utility repo:

```text
ops2beads/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   └── rollout.md
├── src/
│   ├── cli/
│   ├── openspec/
│   ├── planner/
│   ├── beads/
│   ├── reconcile/
│   └── render/
└── tests/
```

If implemented as a script first:

```text
scripts/
└── ops2beads.py
```

For a first practical version, Python is attractive because:

- fast to prototype
- easy markdown parsing
- easy shelling out to `openspec` and `br`
- good JSON handling

A Rust implementation may be preferable later if we want stronger packaging and parity with `br`.

---

## Data Sources

### Primary OpenSpec sources

From the change directory:

- `proposal.md`
- `design.md` (if present)
- `tasks.md`
- `specs/**/*.md`
- `.openspec.yaml`

### Secondary OpenSpec sources

From CLI, when useful:

- `openspec status --change <name> --json`
- `openspec instructions apply --change <name> --json`
- `openspec show <name> --json` if helpful

### Primary Beads interface

- `br create --json`
- `br dep add`
- `br show --json`
- `br list --json`
- `br ready --json`
- `br update --json`
- `br close --json`
- `br sync --flush-only`

---

## Translation Strategy

The translator should derive Beads issues from a combination of:

1. **tasks.md** as the primary unit list
2. **specs** as acceptance/behavior grounding
3. **design.md** as dependency and architecture context
4. **proposal.md** as scope and change-level metadata

### Why make `tasks.md` primary

OpenSpec already positions `tasks.md` as the implementation checklist.
It is the closest existing artifact to execution units.

However, plain task lists are often too linear or too coarse for parallel work, so the translator should:

- split overly broad tasks when safe
- infer dependencies only where needed
- avoid serializing unrelated work

### Translation rule of thumb

- `proposal.md` defines **intent and scope**
- `specs` define **behavioral outcomes / acceptance boundaries**
- `design.md` defines **technical constraints and ordering hints**
- `tasks.md` defines **candidate work items**
- translator emits **parallelizable Beads issues**

---

## Intermediate Data Model

Suggested normalized structure:

```json
{
  "changeName": "add-dark-mode",
  "changePath": "openspec/changes/add-dark-mode",
  "schemaName": "spec-driven",
  "generatedAt": "2026-03-13T20:00:00Z",
  "sourceFiles": {
    "proposal": "openspec/changes/add-dark-mode/proposal.md",
    "design": "openspec/changes/add-dark-mode/design.md",
    "tasks": "openspec/changes/add-dark-mode/tasks.md",
    "specs": [
      "openspec/changes/add-dark-mode/specs/ui/spec.md"
    ]
  },
  "changeLabels": [
    "openspec",
    "change:add-dark-mode"
  ],
  "workItems": [
    {
      "key": "theme-context",
      "title": "Add theme context provider",
      "description": "Implement ThemeContext and provider wiring for app-wide theme state.",
      "type": "task",
      "priority": 1,
      "labels": ["openspec", "change:add-dark-mode", "capability:ui"],
      "dependsOn": [],
      "acceptance": [
        "Theme state available to consumers",
        "Supports light/dark selection"
      ],
      "sourceRefs": [
        "tasks.md#1.1",
        "design.md#technical-approach",
        "specs/ui/spec.md#requirement-theme-selection"
      ],
      "fingerprint": "sha256:...",
      "beadsId": null
    }
  ]
}
```

### Important fields

- `key`: stable local identifier used before a Beads issue exists
- `fingerprint`: derived from normalized issue content for idempotency
- `sourceRefs`: traceability back to OpenSpec artifacts
- `beadsId`: filled after creation/reconciliation

---

## Work Item Extraction Rules

### Stage 1: parse tasks.md

Extract checklist items of the form:

```text
- [ ] 1.1 Create ThemeContext with light/dark state
- [ ] 1.2 Add CSS custom properties for colors
```

For each task:

- capture ordinal (`1.1`, `1.2`, ...)
- capture section heading (`Theme Infrastructure`, etc.)
- capture description

This gives the initial candidate issue list.

### Stage 2: enrich using design and specs

For each candidate task, try to infer:

- capability/domain label from spec path
- likely issue type (`task`, `feature`, `bug`, `chore`, `docs`)
- acceptance bullets from matching requirement/scenario text
- dependency hints from design or task ordering
- implementation cluster/wave

### Stage 3: split broad tasks when necessary

Example:

```text
2.2 Add CSS variables and update all components
```

might become:

- define CSS variables
- switch shared layout components
- switch form controls
- switch dialogs/overlays

Splitting should be conservative in v1.
A simple rule:

- split only when task clearly contains multiple coordinate clauses
- or when task references more than one independent subsystem

### Stage 4: infer dependencies

Default policy:

- preserve **explicit** task ordering only when needed
- avoid making every N+1 task depend on N
- infer dependencies from words like:
  - create foundation for
  - wire into
  - after
  - depends on
  - migrate existing consumers to

Examples:

- `Add ThemeContext` -> foundation issue
- `Add toggle to settings page` depends on `ThemeContext`
- `Persist preference in localStorage` may depend on `ThemeContext`
- `Update components to use CSS variables` depends on `Define CSS variables`

### Stage 5: emit execution waves

Not required for Beads itself, but useful in the plan output:

- wave 0: setup/foundations
- wave 1: parallel feature branches
- wave 2: integration/polish
- wave 3: verification/docs

This improves operator understanding and future automation.

---

## Mapping to Beads

### Change-level metadata

Every issue created for a change should get common labels:

- `openspec`
- `change:<change-name>`
- maybe `schema:<schema-name>`

If spec capabilities can be inferred, add:

- `capability:<name>`

If source artifact class is useful, possibly:

- `source:openspec-task`

### Issue types

Suggested mapping:

- implementation step -> `task`
- large user-visible end-to-end unit -> `feature`
- defect found during handoff -> `bug`
- tests / migration / docs -> `chore` or `docs`

Keep v1 simple: default most derived issues to `task`.

### Priorities

Suggested initial mapping:

- foundational blockers -> P1
- normal implementation items -> P2
- nice-to-have polish -> P3
- critical production bugfix work -> P0

If no strong signal exists, default to P2.

### Dependencies

For each `dependsOn` edge:

```bash
br dep add <child> <parent>
```

meaning the child is blocked until the parent is done.

### Parent/epic handling

Optional but recommended:

Create one top-level Beads issue representing the whole OpenSpec change:

```text
Feature: Implement OpenSpec change add-dark-mode
```

Then attach derived work items under it using:

- `--parent <epic-id>`

This makes querying and cleanup easier.

---

## Idempotency and Reconciliation

This is the most important engineering requirement.

The translator must be safe to rerun.

### Problem

If the user edits `tasks.md` and reruns handoff, we do **not** want:

- duplicate Beads issues
- broken dependency graphs
- orphaned old issues without explanation

### Solution

Maintain a persistent mapping in:

```text
openspec/changes/<change>/beads-handoff.json
```

For each work item, store:

- local key
- normalized fingerprint
- last emitted title/description
- mapped Beads issue ID
- current status

### Reconciliation policy (v1)

On rerun:

1. load previous handoff file if present
2. rebuild normalized work items from current OpenSpec artifacts
3. match by:
   - local key first
   - fingerprint second
   - fallback exact title match third
4. if matched:
   - update issue if mutable fields changed
5. if new:
   - create issue
6. if old item no longer exists:
   - mark as stale in report
   - do not auto-close in v1

### Reconciliation policy (v2)

Could optionally support:

- close removed issues with reason:
  - `Removed from OpenSpec change plan during replanning`
- create discovered-from links for split work

But skip that initially.

---

## Proposed CLI Surface

## `ops2beads inspect`

Read OpenSpec change artifacts and print a structured interpretation without touching Beads.

```bash
ops2beads inspect --change add-dark-mode
ops2beads inspect --change add-dark-mode --format json
```

Use cases:

- debug parsing
- explain inferred work graph
- validate before mutation

## `ops2beads plan`

Build and persist the normalized handoff plan.

```bash
ops2beads plan --change add-dark-mode
ops2beads plan --change add-dark-mode --format json
```

Effects:

- writes `beads-handoff.json`
- does not call `br`

## `ops2beads handoff`

Create or reconcile Beads issues from the plan.

```bash
ops2beads handoff --change add-dark-mode
ops2beads handoff --change add-dark-mode --dry-run
ops2beads handoff --change add-dark-mode --yes
```

Effects:

- reads/creates normalized plan
- creates or updates Beads issues
- adds dependency edges
- writes mapping back to handoff file

## `ops2beads mirror`

Update `tasks.md` or a companion summary file with Beads IDs and progress mirrors.

```bash
ops2beads mirror --change add-dark-mode
```

This is optional but useful.

## `ops2beads reconcile`

Explicit rerun/repair command for existing handoffs.

```bash
ops2beads reconcile --change add-dark-mode
```

---

## Suggested Initial Implementation Order

### Phase 1: Read-only planner

Implement:

- change discovery
- file loading
- task extraction
- basic issue inference
- JSON plan output

Success criterion:

```bash
ops2beads plan --change X
```

produces a useful `beads-handoff.json` without touching Beads.

### Phase 2: Basic handoff

Implement:

- `br create --json`
- `br dep add`
- top-level epic issue creation
- labels and priorities
- mapping persistence

Success criterion:

- one rerunnable command seeds Beads issues for a change

### Phase 3: Reconciliation

Implement:

- stable key matching
- fingerprint matching
- safe updates on rerun
- stale/removed item reporting

Success criterion:

- user can edit tasks and rerun without duplicate issues

### Phase 4: Mirror/reporting

Implement:

- generated markdown summary
- optional `tasks.md` annotation
- execution-wave output
- operator report

### Phase 5: Agent integration

Implement:

- JSON-only mode for all commands
- non-interactive flags
- failure codes
- recommended agent workflow doc

---

## Handoff Output Example

A human-friendly dry run might look like:

```text
Change: add-dark-mode
Schema: spec-driven
Source: openspec/changes/add-dark-mode

Planned Beads issues: 7

Epic
- add-dark-mode implementation umbrella

Wave 0
- Add theme context provider
- Define CSS custom properties

Wave 1
- Persist theme preference
- Add toggle to settings page
- Add quick toggle to header

Wave 2
- Migrate components to CSS variables
- Add accessibility verification

Dependencies
- Persist theme preference -> Add theme context provider
- Add toggle to settings page -> Add theme context provider
- Add quick toggle to header -> Add theme context provider
- Migrate components to CSS variables -> Define CSS custom properties

Dry run only. No Beads changes written.
```

---

## Mirror Strategy

The translator should not try to make OpenSpec and Beads share the exact same progress model. Instead, it should maintain a **lightweight bridge**.

### Recommended bridge file

Write:

```text
openspec/changes/<change>/beads-summary.md
```

Contents:

- umbrella Beads issue ID
- work item to Beads ID mapping
- wave grouping
- current `br` statuses (if refreshed)
- rerun instructions

This is safer than mutating `tasks.md` aggressively.

### Optional tasks.md annotations

If we later choose to annotate `tasks.md`, keep it minimal, e.g.:

```text
- [ ] 1.1 Create ThemeContext with light/dark state  [beads: bd-abc123]
```

But for v1, prefer a separate generated summary file.

---

## Parsing Heuristics

V1 should use robust but simple heuristics.

### Proposal parsing

Extract:

- change title/name
- capabilities mentioned
- impact areas

Use for labels and umbrella issue description.

### Specs parsing

Extract requirement names and scenarios.

Use for:

- acceptance bullets
- capability labels
- identifying which tasks map to which behavioral areas

### Design parsing

Extract sections like:

- decisions
- risks/trade-offs
- migration plan
- open questions

Use for:

- dependency hints
- identifying work that must be sequenced
- adding context to umbrella issue

### Tasks parsing

Extract:

- heading
- checkbox state
- task number
- task text

Use as the primary source of issue seeds.

---

## Failure Modes and Handling

## 1. Missing artifacts

If `tasks.md` is missing:

- fail with actionable message
- suggest rerunning `/opsx:ff` or `/opsx:continue`

If `design.md` is missing:

- proceed with reduced inference
- warn about weaker dependency extraction

If `specs/` is missing:

- proceed only if user requests `--allow-task-only`

## 2. Ambiguous task decomposition

If task is too broad or unclear:

- emit one issue instead of over-splitting
- add warning in plan output

## 3. Beads not initialized

If `.beads/` does not exist:

- fail with message suggesting `br init`
- optionally support `--init-beads` later

## 4. Duplicate or conflicting existing issues

If labels suggest issues already exist for the same change:

- require reconciliation path
- do not create duplicates blindly

## 5. Rerun after significant replan

If the handoff plan changes materially:

- show diff summary
- require confirmation unless `--yes`

---

## Traceability Model

Every created Beads issue should preserve a backlink to OpenSpec.

### Recommended Beads description block

Append a standard section:

```text
OpenSpec source:
- Change: add-dark-mode
- Task ref: tasks.md#1.1
- Related spec refs:
  - specs/ui/spec.md#Requirement: Theme Selection
- Related design refs:
  - design.md#Technical Approach
```

### Recommended labels

- `openspec`
- `change:add-dark-mode`
- `capability:ui`
- `wave:0`

This allows later queries like:

```bash
br list --json --label change:add-dark-mode
```

---

## Example Pseudocode

```python
def handoff(change_name: str, dry_run: bool = False):
    change = load_openspec_change(change_name)
    validate_change(change)

    plan = build_plan(change)
    previous = load_existing_handoff(change)
    reconciled = reconcile(plan, previous)

    if dry_run:
        print_summary(reconciled)
        return

    ensure_beads_workspace()

    epic_id = ensure_change_epic(reconciled.change)

    for item in reconciled.work_items:
        if item.beads_id is None:
            item.beads_id = br_create(item, parent=epic_id)
        else:
            maybe_update_issue(item)

    for edge in reconciled.dependency_edges:
        br_ensure_dependency(edge.child_beads_id, edge.parent_beads_id)

    save_handoff_file(reconciled)
    write_beads_summary(reconciled)
```

---

## Concrete First-Version Command Behavior

### `ops2beads handoff --change add-dark-mode --dry-run`

- verify `openspec/changes/add-dark-mode` exists
- read `.openspec.yaml`
- read `proposal.md`, `tasks.md`, all `specs/**/*.md`
- read `design.md` if present
- build normalized plan
- print issue list + dependencies + wave summary
- exit without touching `.beads/`

### `ops2beads handoff --change add-dark-mode`

- same as above
- ensure `.beads/` exists
- create change epic if absent
- create/update child issues
- add dependency edges
- write `beads-handoff.json`
- write `beads-summary.md`
- print next commands:

```text
Next steps:
- br ready --json --label change:add-dark-mode
- br sync --flush-only
```

---

## Recommended Rollout Strategy

### Stage A: Manual operator use

Use translator only as a human-invoked command.

Flow:

1. do normal OpenSpec planning
2. run `ops2beads handoff --dry-run`
3. inspect
4. run `ops2beads handoff`
5. execute using Beads

### Stage B: Agent-assisted use

Teach agents a workflow convention:

1. if OpenSpec change is apply-ready, run handoff
2. then use `br ready --json`
3. claim/execute/close Beads issues
4. sync Beads at session end

### Stage C: Project-local command wrappers

Add project scripts like:

```bash
make ops-handoff CHANGE=add-dark-mode
```

or

```bash
just ops-handoff add-dark-mode
```

### Stage D: Optional custom OpenSpec schema later

Only after Option C proves itself should we consider adding:

- a dedicated `beads-plan` artifact
- a slimmer `tasks.md`
- richer planning instructions for better issue decomposition

---

## Open Questions

1. Should the translator always create a top-level epic/umbrella issue?
2. Should task splitting happen in v1, or should v1 remain 1 task -> 1 issue?
3. Should changed tasks update existing Beads issue titles/descriptions automatically?
4. Should removed work items be auto-closed, or only reported?
5. Do we want a generated `beads-summary.md`, `beads-handoff.json`, or both?
6. Should wave grouping be persisted as labels (`wave:0`) or only rendered in reports?
7. Should acceptance criteria be copied directly into Beads descriptions, or summarized?

---

## Recommended v1 Decisions

To keep the first implementation tractable:

- **1 task -> 1 Beads issue** by default
- create **one umbrella feature/epic issue** per OpenSpec change
- infer only **obvious** dependencies
- write both:
  - `beads-handoff.json`
  - `beads-summary.md`
- support:
  - `inspect`
  - `plan`
  - `handoff`
- defer:
  - issue auto-closing on deletion
  - aggressive task splitting
  - automatic OpenSpec progress mirroring

---

## Practical Next Step

Build a minimal prototype that supports exactly this flow:

```bash
/opsx:propose add-dark-mode
ops2beads handoff --change add-dark-mode --dry-run
ops2beads handoff --change add-dark-mode
br ready --json --label change:add-dark-mode
```

If that works end-to-end, then add:

- reconciliation
- summary generation
- agent-oriented JSON output
- optional `tasks.md` mirroring

---

## Bottom Line

Option C is the best starting implementation because it:

- preserves OpenSpec unchanged
- leverages OpenSpec's strongest stable seam: artifact files + CLI JSON
- leverages Beads exactly how it wants to be used: explicit CLI-driven issue orchestration
- creates a clear, testable handoff boundary
- can later evolve toward Option A if deeper workflow integration proves worthwhile
