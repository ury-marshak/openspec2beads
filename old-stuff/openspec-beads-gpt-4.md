I examined both repos and did not make changes.

## Short answer

Yes: OpenSpec is customizable enough to support a beads-based implementation handoff, mainly via:

1. **custom schemas**
2. **custom artifact templates/instructions**
3. **project config context/rules injection**
4. **schema-level apply customization**
5. **external automation using OpenSpec’s machine-readable CLI**

But there is an important limitation:

- **OpenSpec does not currently have a first-class plugin/hook system for “when implementation starts, automatically generate beads issues”.**
- The built-in workflow command set is **fixed**.
- The built-in `apply` flow still fundamentally expects a **checkbox-tracked file** for progress, not a beads-native issue board.

So the clean path is likely:
- **keep OpenSpec for planning/spec/design**
- **add a custom pre-implementation artifact that produces a beads issue collection**
- then use **beads for parallel execution**
- optionally keep a thin `tasks.md` as OpenSpec’s apply/archive bridge

---

# What OpenSpec is doing today

OpenSpec’s new OPSX workflow is schema-driven.

Core ideas from docs/source:

- Workflow is artifact-based: `proposal -> specs -> design -> tasks -> implement`
- A **schema** defines:
  - artifact IDs
  - generated files
  - dependencies
  - apply requirements
  - apply tracking file
- Artifacts are resolved from:
  - project-local schemas
  - user schemas
  - built-in schemas

Relevant places:
- `docs/customization.md`
- `docs/workflows.md`
- `docs/opsx.md`
- `schemas/spec-driven/schema.yaml`
- `src/core/artifact-graph/*`
- `src/commands/workflow/instructions.ts`

---

# What beads gives you

From `beads_rust`:

- issue tracking is repo-local
- agent-friendly JSON output via `--json`
- dependency graph via `br dep add`
- actionable work discovery via `br ready`
- claim/close/update lifecycle
- explicit sync model (`br sync --flush-only`)
- ideal for parallel implementation by multiple agents

Good integration primitives:
- `br create`
- `br update --claim`
- `br dep add`
- `br ready --json`
- `br close --reason`
- `br sync --flush-only`

Relevant docs:
- `~/sources/beads_rust/README.md`
- `~/sources/beads_rust/docs/AGENT_INTEGRATION.md`
- `~/sources/beads_rust/docs/CLI_REFERENCE.md`

---

# The main OpenSpec customization points

## 1. Project config: low-friction steering
OpenSpec supports `openspec/config.yaml` with:

- `schema`
- `context`
- `rules`

This is the lightest customization point.

What it can do for beads:
- inject team/process context like:
  - “Before implementation, decompose into beads issues”
  - “Tasks must be parallelizable”
  - “Identify dependency edges explicitly”
  - “Each work item must be independently claimable by an agent”
- add per-artifact rules for:
  - `proposal`
  - `specs`
  - `design`
  - `tasks`

Good fit:
- enforcing beads-friendly writing style
- making `tasks.md` more decomposition-oriented

Not enough by itself for:
- new artifact types
- new workflow stages
- automatic `br` issue creation

---

## 2. Custom schemas: the strongest built-in extension point
This is the most important one.

OpenSpec lets you fork the built-in schema or create a new one under:

- `openspec/schemas/<name>/schema.yaml`
- `openspec/schemas/<name>/templates/*`

A schema controls:
- what artifacts exist
- their dependencies
- what file each artifact generates
- what must exist before apply
- what file apply tracks

This is the best place to introduce beads.

### Example integration shape
A custom schema could add artifacts like:

- `proposal`
- `specs`
- `design`
- `beads-plan`
- `tasks`

or even:

- `proposal`
- `specs`
- `design`
- `issue-map`
- `execution-waves`
- `tasks`

Then define dependencies like:

- `issue-map` requires `specs` + `design`
- `tasks` requires `issue-map`

or:

- `apply.requires: [issue-map, tasks]`

### Why this is strong
It gives you a formal workflow stage:
- after planning is mature
- before implementation starts
- where OpenSpec artifacts are translated into a parallelizable execution plan

That maps exactly to your goal.

---

## 3. Custom templates and per-artifact instructions
Each artifact in a schema has:

- `template`
- `instruction`

The built-in `spec-driven` schema already uses these heavily.

This means you can define an artifact whose output is specifically something like:

- a beads issue decomposition document
- a dependency matrix
- a wave-based execution plan
- even a generated shell script or machine-readable seed file

Important nuance from source:
- the schema system does **not** strongly enforce “artifact must be Markdown”
- practically the docs/examples are Markdown-first, but the engine mostly treats artifacts as files

So you could plausibly generate:
- `beads-plan.md`
- `beads-issues.yaml`
- `beads-import.json`
- `.beads/bootstrap.sh`
- etc.

That said, the surrounding docs and skills are markdown-oriented, so the smoothest route is still probably a markdown artifact that an agent/tool later converts into actual `br` commands.

---

## 4. Schema-level `apply` customization
Schemas also support an `apply` block.

This is key.

The `apply` config can define:
- `requires`
- `tracks`
- `instruction`

So you can customize:
- what artifacts must exist before implementation begins
- which file is used for progress tracking
- what apply tells the agent to do

### Why this matters for beads
You could require that a beads-prep artifact exist before apply:
- `apply.requires: [beads-plan, tasks]`

And customize apply instruction to say things like:
- initialize/refresh beads issues first
- use `br ready --json` to select work
- claim issues with `br update --claim`
- close work with `br close`
- sync at the end

### Limitation
This is the biggest functional constraint I found:

OpenSpec’s apply logic parses the tracking file as **Markdown checkboxes**.

So although `apply.tracks` is configurable, the parser still expects lines like:
- `- [ ] ...`
- `- [x] ...`

That means:
- OpenSpec cannot natively treat `.beads/issues.jsonl` or the SQLite DB as its progress model
- if you want OpenSpec’s `apply` to keep working well, you likely still need a checkbox-based file

So the practical hybrid is:

- use beads as the real execution substrate
- keep `tasks.md` as a lightweight mirror/index/checklist for OpenSpec

---

## 5. Change-level schema selection
Schema selection precedence is:

1. explicit CLI flag
2. change-local `.openspec.yaml`
3. `openspec/config.yaml`
4. default `spec-driven`

This is useful because you could roll out a beads-integrated workflow:
- only for some projects
- only for some changes
- without forking all of OpenSpec globally

That makes experimentation easy.

---

## 6. User/global schema overrides
OpenSpec also supports user-level schemas.

So if you want a reusable “OpenSpec + beads” workflow across many repos, you can install it globally first, then later vendor it into each project.

Good for:
- experimenting centrally
- standardizing later

---

## 7. Machine-readable CLI: good external integration seam
This is the other major integration point.

OpenSpec exposes structured workflow state via CLI:
- `openspec status --json`
- `openspec instructions <artifact> --json`
- `openspec templates --json`
- `openspec schemas --json`

That means you do **not** need to patch OpenSpec internals to build a converter.

You can write an external tool/skill/script that:
1. reads the change status
2. reads proposal/specs/design/tasks
3. converts them into beads issues + dependencies
4. calls `br create`, `br dep add`, etc.

This is probably the cleanest engineering seam.

### Why this matters
Because OpenSpec lacks hook/plugin callbacks, the safest integration is:
- **treat OpenSpec as a planning system**
- **treat beads as an execution system**
- connect them with a translator using stable CLIs

---

# Customization points that are weaker than they look

## 1. Workflow/profile selection is configurable, but workflow IDs are fixed
OpenSpec lets you choose which workflows are installed via profile/workflow selection.

But the available workflow IDs are hardcoded:
- `propose`
- `explore`
- `new`
- `continue`
- `apply`
- `ff`
- `sync`
- `archive`
- `bulk-archive`
- `verify`
- `onboard`

So you can:
- enable/disable built-ins

But you cannot, through normal config alone, add:
- `/opsx:beadsify`
- `/opsx:issue-plan`
- `/opsx:dispatch`

To get new slash commands, you’d need:
- source changes in OpenSpec, or
- separate custom skills/commands outside OpenSpec’s built-in workflow registry

This is a real limitation.

---

## 2. Skill/command generation is not schema-pluggable
OpenSpec’s workflow skills/commands are generated from hardcoded template registries.

So even though artifact workflows are schema-driven, the top-level chat commands are not fully open-ended.

Implication:
- you can customize artifact flow deeply
- but if you want a first-class new command for beads conversion, that is outside the current customization surface

---

## 3. `apply` is not beads-native
Even with custom schema apply instructions, the apply engine still assumes:
- read context artifacts
- parse tracking file
- implement tasks
- mark checkboxes

So beads can be introduced into apply guidance, but apply itself does not become a beads issue executor automatically.

---

# Best places to insert beads in the lifecycle

## Option A — Best overall: add a pre-implementation artifact
Recommended insertion point:

**after `specs` + `design`, before implementation**

Custom schema shape:
- `proposal`
- `specs`
- `design`
- `beads-plan`
- `tasks`

What `beads-plan` would contain:
- issue breakdown
- issue titles/descriptions
- dependency edges
- labels/types/priorities
- suggested parallel execution waves
- maybe exact `br` commands to run

Why this is best:
- enough context exists to decompose work well
- still early enough to maximize parallelism
- preserves OpenSpec planning rigor

---

## Option B — Replace “tasks” with “beads-ready execution plan”, keep a thin tracked file
If you want beads to be primary:

- create a custom artifact that is the real execution plan
- keep `tasks.md` only as:
  - summary checkpoints
  - synchronization bridge for OpenSpec apply/archive

This avoids fighting OpenSpec’s checkbox expectations too hard.

---

## Option C — External translator at handoff time
Keep OpenSpec artifacts mostly unchanged, then run a separate conversion step:
- after `/opsx:ff`
- or right before `/opsx:apply`

This would:
- read artifacts
- create beads issues
- optionally update `tasks.md` with issue IDs / wave summaries

This is probably the least invasive option operationally.

---

# What a beads-oriented OpenSpec schema could encode

A good custom schema could force the planning output to include things beads needs:

## In design
Add required sections like:
- decomposition strategy
- dependency graph
- parallelization constraints
- merge boundaries
- ownership/claim strategy
- cross-issue integration points

## In issue-map artifact
Require each issue to include:
- title
- type
- priority
- description
- acceptance criteria
- dependencies
- labels
- estimated parallelism group
- discovered-from relation if split from another issue

## In tasks
Keep only a few high-level checkboxes such as:
- [ ] beads issue collection generated
- [ ] all issues synced to `.beads/`
- [ ] parallel execution complete
- [ ] integration/verification complete

That would preserve OpenSpec compatibility while letting beads do the real work.

---

# Constraints and caveats

## 1. No built-in automatic hook system
I did not find a native “on artifact completion, run custom command” extension point.

So any automatic conversion to beads would need to be:
- agent-instruction driven, or
- done by an external script/tool/skill

## 2. Archive/sync remain spec-centric
OpenSpec’s archive logic is about merging delta specs into `openspec/specs/`.

That’s fine, but it means beads integration is mainly an **execution-layer customization**, not a replacement for OpenSpec’s archive model.

## 3. Beads state is external to OpenSpec state
OpenSpec tracks workflow completion by artifact existence + checkbox progress.
Beads tracks execution by issue DB/JSONL state.

These are separate systems.
You’ll likely want one of:
- a mirror file in OpenSpec
- or a convention for when a change is “done enough” to archive

---

# My recommendation

If your goal is:

> follow OpenSpec’s spec-driven process, then convert artifacts into a detailed beads issue collection for maximally parallel implementation

then the best-fit design is:

## Recommended architecture
1. **Fork `spec-driven` into a custom schema**
2. Add a new artifact, something like:
   - `beads-plan`
   - or `issue-map`
3. Make it depend on:
   - `specs`
   - `design`
4. Keep `tasks.md`, but reduce it to:
   - orchestration checkpoints
   - not the true implementation decomposition
5. Set `apply.requires` to include the new beads artifact
6. Use an **external translator/skill** to turn that artifact into actual `br` issues
7. Run implementation in beads using:
   - `br ready --json`
   - `br update --claim`
   - `br close`
   - `br sync --flush-only`

## Why this is best
- minimal friction with OpenSpec internals
- maximal leverage of OpenSpec customization
- beads becomes the execution substrate
- OpenSpec remains the planning/spec/archive substrate

---

# Bottom line

## Strong customization points for your use case
- `openspec/config.yaml`
- `openspec/schemas/<name>/schema.yaml`
- `openspec/schemas/<name>/templates/*`
- schema `apply.requires / apply.tracks / apply.instruction`
- OpenSpec CLI JSON outputs for external automation

## Weak/missing customization points
- no native hook/plugin system
- no config-defined new `/opsx:*` workflows
- apply progress is still checkbox-file based, not beads-native

So: **yes, OpenSpec can be adapted for this, but the natural solution is a hybrid, not a pure in-core beads plugin.**

If you want, next I can turn this into a concrete proposal for:
1. a custom OpenSpec schema design for beads handoff, and/or
2. a specific translation flow from OpenSpec artifacts to `br create/dep add` commands.
