#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TASK_RE = re.compile(r"^(?P<indent>\s*)[-*]\s*\[(?P<done>[ xX])]\s*(?P<body>.+?)\s*$")
TASK_NUMBER_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<title>.+)$")
DEPENDS_RE = re.compile(
    r"(?:depends\s+on|after|blocked\s+by|requires?)\s+((?:\d+(?:\.\d+)?)(?:\s*(?:,|and)\s*\d+(?:\.\d+)?)*)",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CAPABILITIES_SECTION_RE = re.compile(
    r"^##\s+(?:New\s+Capabilities|Modified\s+Capabilities|Capabilities)\s*$", re.IGNORECASE
)
LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
ANNOTATION_RE = re.compile(r"\s+\[beads:\s*(?P<id>[^\]\s]+)(?:\s+status:\s*(?P<status>[^\]]+))?\]\s*$")

FOUNDATION_PREFIXES = ("create", "define", "implement", "introduce", "add")
FOUNDATION_KEYWORDS = {
    "foundation",
    "infrastructure",
    "setup",
    "scaffold",
    "schema",
    "model",
    "context",
    "provider",
    "api",
    "types",
    "storage",
    "variables",
    "palette",
    "hook",
}
INTEGRATION_KEYWORDS = {
    "use",
    "wire",
    "integrate",
    "connect",
    "toggle",
    "persist",
    "settings",
    "header",
    "page",
    "component",
    "migrate",
    "apply",
    "render",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "or",
    "the",
    "to",
    "for",
    "of",
    "with",
    "into",
    "from",
    "in",
    "on",
    "by",
    "via",
    "using",
    "add",
    "create",
    "implement",
    "update",
    "define",
    "wire",
    "persist",
    "migrate",
    "support",
    "allow",
    "make",
    "page",
    "component",
    "components",
    "state",
}


class Ops2BeadsError(RuntimeError):
    pass


@dataclass
class TaskRecord:
    key: str
    title: str
    raw_text: str
    task_number: str | None
    section: str | None
    done: bool
    line_number: int
    source_ref: str


@dataclass
class ParsedTaskLine:
    line_number: int
    indent: str
    done: bool
    body: str


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise Ops2BeadsError(f"Missing required file: {path}") from exc


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def run_json(cmd: list[str], cwd: Path) -> Any:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise Ops2BeadsError(f"Command failed ({' '.join(cmd)}): {stderr}")
    stdout = proc.stdout.strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise Ops2BeadsError(f"Expected JSON from {' '.join(cmd)}, got: {stdout[:300]}") from exc


def iso_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def load_schema_name(change_dir: Path) -> str:
    config_path = change_dir / ".openspec.yaml"
    if not config_path.exists():
        return "spec-driven"
    match = re.search(r"^\s*schema\s*:\s*([A-Za-z0-9_-]+)\s*$", read_text(config_path), re.MULTILINE)
    return match.group(1) if match else "spec-driven"


def discover_spec_files(change_dir: Path) -> list[Path]:
    specs_dir = change_dir / "specs"
    if not specs_dir.exists():
        return []
    return sorted(path for path in specs_dir.rglob("*.md") if path.is_file())


def extract_capabilities_from_specs(spec_files: list[Path], change_dir: Path) -> list[str]:
    capabilities: list[str] = []
    for spec_file in spec_files:
        rel_parts = spec_file.relative_to(change_dir).parts
        if len(rel_parts) >= 3 and rel_parts[0] == "specs":
            capability = rel_parts[1]
            if capability not in capabilities:
                capabilities.append(capability)
    return capabilities


def extract_capabilities_from_proposal(proposal_text: str) -> list[str]:
    lines = proposal_text.splitlines()
    capabilities: list[str] = []
    in_section = False
    for line in lines:
        if HEADING_RE.match(line):
            in_section = bool(CAPABILITIES_SECTION_RE.match(line))
            continue
        if not in_section:
            continue
        item = LIST_ITEM_RE.match(line)
        if not item:
            if line.strip():
                break
            continue
        value = item.group(1).strip().strip("`")
        value = value.split(":", 1)[0].strip()
        if value and value not in capabilities:
            capabilities.append(value)
    return capabilities


def parse_tasks(tasks_text: str) -> list[TaskRecord]:
    tasks: list[TaskRecord] = []
    current_section: str | None = None
    seen_keys: dict[str, int] = {}

    for line_number, line in enumerate(tasks_text.splitlines(), start=1):
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            if level <= 3:
                current_section = heading.group(2).strip()
            continue

        match = TASK_RE.match(line)
        if not match:
            continue

        done = match.group("done").lower() == "x"
        raw_text = ANNOTATION_RE.sub("", match.group("body")).strip()
        task_number = None
        title = raw_text

        numbered = TASK_NUMBER_RE.match(raw_text)
        if numbered:
            task_number = numbered.group("number")
            title = numbered.group("title").strip()

        key_base = task_number or slugify(title)
        key = key_base
        if key in seen_keys:
            seen_keys[key] += 1
            key = f"{key}-{seen_keys[key]}"
        else:
            seen_keys[key] = 1

        tasks.append(
            TaskRecord(
                key=key,
                title=title,
                raw_text=raw_text,
                task_number=task_number,
                section=current_section,
                done=done,
                line_number=line_number,
                source_ref=f"tasks.md#L{line_number}",
            )
        )
    return tasks


def parse_task_line(line: str, line_number: int) -> ParsedTaskLine | None:
    match = TASK_RE.match(line)
    if not match:
        return None
    return ParsedTaskLine(
        line_number=line_number,
        indent=match.group("indent"),
        done=match.group("done").lower() == "x",
        body=match.group("body"),
    )


def extract_requirements(spec_text: str, spec_path: str) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []
    current_requirement: str | None = None
    for line_number, line in enumerate(spec_text.splitlines(), start=1):
        if line.startswith("### "):
            current_requirement = line[4:].strip()
        elif line.startswith("#### Scenario:") and current_requirement:
            requirements.append(
                {
                    "requirement": current_requirement,
                    "scenario": line[len("#### Scenario:") :].strip(),
                    "sourceRef": f"{spec_path}#L{line_number}",
                }
            )
    return requirements


def tokenize(text: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", expanded.lower()) if token not in STOPWORDS}


def is_foundational(task: TaskRecord) -> bool:
    title = task.title.lower()
    section = (task.section or "").lower()
    tokens = tokenize(task.title)
    if title.startswith(FOUNDATION_PREFIXES):
        return True
    if any(keyword in tokens for keyword in FOUNDATION_KEYWORDS):
        return True
    return any(keyword in section for keyword in ("foundation", "infrastructure", "setup"))


def overlap_score(a: set[str], b: set[str]) -> int:
    return len(a & b)


def infer_dependencies(tasks: list[TaskRecord]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    by_number = {task.task_number: task for task in tasks if task.task_number}
    deps: dict[str, list[str]] = {task.key: [] for task in tasks}
    reasons: dict[str, list[str]] = {task.key: [] for task in tasks}
    task_tokens = {task.key: tokenize(task.title) for task in tasks}

    def add_dep(child: TaskRecord, parent: TaskRecord, reason: str) -> None:
        if child.key == parent.key:
            return
        if parent.key not in deps[child.key]:
            deps[child.key].append(parent.key)
            reasons[child.key].append(reason)

    # 1. Explicit numbered references in task text.
    for task in tasks:
        for match in DEPENDS_RE.finditer(task.raw_text):
            numbers = re.findall(r"\d+(?:\.\d+)?", match.group(1))
            for number in numbers:
                parent = by_number.get(number)
                if parent:
                    add_dep(task, parent, f"explicit reference to task {number}")

    # 2. Foundation and shared-domain inference.
    for index, task in enumerate(tasks):
        earlier = tasks[:index]
        if not earlier:
            continue
        tokens = task_tokens[task.key]
        for candidate in earlier:
            candidate_tokens = task_tokens[candidate.key]
            score = overlap_score(tokens, candidate_tokens)
            if score <= 0:
                continue
            same_major = bool(task.task_number and candidate.task_number and task.task_number.split(".", 1)[0] == candidate.task_number.split(".", 1)[0])
            if is_foundational(candidate) and (score >= 1 or same_major):
                add_dep(task, candidate, f"shared foundation vocabulary with {candidate.key}")
                continue
            if same_major and score >= 1 and candidate.line_number < task.line_number:
                add_dep(task, candidate, f"same major task group as {candidate.key}")
                continue
            if candidate.section and task.section and candidate.section == task.section and score >= 1:
                add_dep(task, candidate, f"same section and overlapping terms with {candidate.key}")

    # 3. Prefer sparse graphs: if multiple dependencies imply each other, keep only direct ones.
    task_by_key = {task.key: task for task in tasks}
    changed = True
    while changed:
        changed = False
        closure: dict[str, set[str]] = {key: set(values) for key, values in deps.items()}
        for key in list(closure):
            stack = list(closure[key])
            while stack:
                current = stack.pop()
                for ancestor in closure.get(current, set()):
                    if ancestor not in closure[key]:
                        closure[key].add(ancestor)
                        stack.append(ancestor)
        for child_key, parents in list(deps.items()):
            direct = list(parents)
            child = task_by_key[child_key]
            for parent in direct:
                parent_task = task_by_key[parent]
                for other in direct:
                    if parent == other:
                        continue
                    if parent not in closure.get(other, set()):
                        continue
                    preserve_cross_foundation = is_foundational(parent_task) and (
                        not child.task_number
                        or not parent_task.task_number
                        or child.task_number.split('.', 1)[0] != parent_task.task_number.split('.', 1)[0]
                    )
                    if preserve_cross_foundation:
                        continue
                    idx = deps[child_key].index(parent)
                    deps[child_key].pop(idx)
                    reasons[child_key].pop(idx)
                    changed = True
                    break
                if changed:
                    break
            if changed:
                break

    return deps, reasons


def compute_waves(work_items: list[dict[str, Any]]) -> None:
    by_key = {item["key"]: item for item in work_items}
    memo: dict[str, int] = {}

    def depth(key: str, stack: set[str]) -> int:
        if key in memo:
            return memo[key]
        if key in stack:
            return 0
        stack.add(key)
        item = by_key[key]
        parents = [parent for parent in item.get("dependsOn", []) if parent in by_key]
        result = 0 if not parents else 1 + max(depth(parent, stack) for parent in parents)
        stack.remove(key)
        memo[key] = result
        return result

    for item in work_items:
        item["wave"] = depth(item["key"], set())


def fingerprint_work_item(item: dict[str, Any]) -> str:
    normalized = {
        "key": item["key"],
        "title": item["title"],
        "description": item["description"],
        "type": item["type"],
        "priority": item["priority"],
        "labels": sorted(item["labels"]),
        "dependsOn": sorted(item["dependsOn"]),
        "acceptance": item.get("acceptance", []),
        "sourceRefs": item.get("sourceRefs", []),
    }
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def select_acceptance(requirements: list[dict[str, str]], task: TaskRecord) -> list[str]:
    tokens = tokenize(task.title)
    scored: list[tuple[int, dict[str, str]]] = []
    for requirement in requirements:
        haystack = f"{requirement['requirement']} {requirement['scenario']}"
        overlap = overlap_score(tokens, tokenize(haystack))
        if overlap:
            scored.append((overlap, requirement))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["sourceRef"]))
    result: list[str] = []
    for _, requirement in scored[:3]:
        bullet = f"{requirement['requirement']}: {requirement['scenario']}"
        if bullet not in result:
            result.append(bullet)
    return result


def build_description(change_name: str, task: TaskRecord, acceptance: list[str], capabilities: list[str]) -> str:
    lines = [task.title]
    if task.section:
        lines.extend(["", f"Section: {task.section}"])
    if capabilities:
        lines.append(f"Capabilities: {', '.join(capabilities)}")
    if acceptance:
        lines.extend(["", "Acceptance hints:"])
        lines.extend(f"- {bullet}" for bullet in acceptance)
    lines.extend(["", "OpenSpec source:", f"- Change: {change_name}", f"- Task ref: {task.source_ref}"])
    return "\n".join(lines).strip()


def build_plan(project_root: Path, change_name: str, allow_task_only: bool = False) -> dict[str, Any]:
    change_dir = project_root / "openspec" / "changes" / change_name
    if not change_dir.exists():
        raise Ops2BeadsError(f"OpenSpec change not found: {change_dir}")

    proposal_path = change_dir / "proposal.md"
    tasks_path = change_dir / "tasks.md"
    design_path = change_dir / "design.md"
    spec_files = discover_spec_files(change_dir)

    if not proposal_path.exists():
        raise Ops2BeadsError(f"Missing proposal.md in {change_dir}")
    if not tasks_path.exists():
        raise Ops2BeadsError(f"Missing tasks.md in {change_dir}")
    if not spec_files and not allow_task_only:
        raise Ops2BeadsError(
            f"No delta specs found under {change_dir / 'specs'} (pass --allow-task-only to override)"
        )

    proposal_text = read_text(proposal_path)
    tasks_text = read_text(tasks_path)
    design_exists = design_path.exists()
    design_text = read_text(design_path) if design_exists else ""

    tasks = parse_tasks(tasks_text)
    if not tasks:
        raise Ops2BeadsError(f"No checkbox tasks found in {tasks_path}")

    capabilities = extract_capabilities_from_specs(spec_files, change_dir)
    for capability in extract_capabilities_from_proposal(proposal_text):
        if capability not in capabilities:
            capabilities.append(capability)

    requirements: list[dict[str, str]] = []
    for spec_file in spec_files:
        rel = spec_file.relative_to(change_dir).as_posix()
        requirements.extend(extract_requirements(read_text(spec_file), rel))

    change_labels = ["openspec", f"change:{change_name}"]
    schema_name = load_schema_name(change_dir)
    if schema_name:
        change_labels.append(f"schema:{schema_name}")

    common_capability_labels = [f"capability:{capability}" for capability in capabilities]
    dependencies, dependency_reasons = infer_dependencies(tasks)

    work_items: list[dict[str, Any]] = []
    for task in tasks:
        acceptance = select_acceptance(requirements, task)
        labels = list(change_labels)
        if len(common_capability_labels) == 1:
            labels.extend(common_capability_labels)
        if task.section:
            labels.append(f"section:{slugify(task.section)}")
        work_item = {
            "key": task.key,
            "taskNumber": task.task_number,
            "title": task.title,
            "description": build_description(change_name, task, acceptance, capabilities),
            "type": "task",
            "priority": 2,
            "labels": sorted(dict.fromkeys(labels)),
            "dependsOn": dependencies.get(task.key, []),
            "dependencyReasons": dependency_reasons.get(task.key, []),
            "acceptance": acceptance,
            "sourceRefs": [task.source_ref],
            "doneInTasksMd": task.done,
            "fingerprint": "",
            "beadsId": None,
        }
        work_item["fingerprint"] = fingerprint_work_item(work_item)
        work_items.append(work_item)

    compute_waves(work_items)

    return {
        "changeName": change_name,
        "changePath": str(change_dir.relative_to(project_root)),
        "schemaName": schema_name,
        "generatedAt": iso_now(),
        "sourceFiles": {
            "proposal": str(proposal_path.relative_to(project_root)),
            "design": str(design_path.relative_to(project_root)) if design_exists else None,
            "tasks": str(tasks_path.relative_to(project_root)),
            "specs": [str(path.relative_to(project_root)) for path in spec_files],
        },
        "changeLabels": change_labels,
        "capabilities": capabilities,
        "warnings": ([] if design_exists else ["design.md missing; dependency inference is reduced"]),
        "summary": {
            "taskCount": len(work_items),
            "completedTasksInTasksMd": sum(1 for task in tasks if task.done),
            "dependencyCount": sum(len(item["dependsOn"]) for item in work_items),
            "maxWave": max(item["wave"] for item in work_items) if work_items else 0,
        },
        "epic": {
            "title": f"Implement OpenSpec change {change_name}",
            "description": f"Umbrella issue for OpenSpec change {change_name}.",
            "type": "epic",
            "priority": 2,
            "labels": sorted(dict.fromkeys(change_labels + common_capability_labels)),
            "beadsId": None,
        },
        "workItems": work_items,
        "designExcerpt": design_text[:4000] if design_text else None,
    }


def handoff_path(project_root: Path, change_name: str) -> Path:
    return project_root / "openspec" / "changes" / change_name / "beads-handoff.json"


def summary_path(project_root: Path, change_name: str) -> Path:
    return project_root / "openspec" / "changes" / change_name / "beads-summary.md"


def tasks_path(project_root: Path, change_name: str) -> Path:
    return project_root / "openspec" / "changes" / change_name / "tasks.md"


def load_existing_handoff(project_root: Path, change_name: str) -> dict[str, Any] | None:
    path = handoff_path(project_root, change_name)
    if not path.exists():
        return None
    return json.loads(read_text(path))


def merge_previous_ids(plan: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    merged = copy.deepcopy(plan)
    if not previous:
        return merged

    previous_items = previous.get("workItems", [])
    by_key = {item.get("key"): item for item in previous_items if item.get("key")}
    by_fingerprint = {item.get("fingerprint"): item for item in previous_items if item.get("fingerprint")}
    by_title = {item.get("title"): item for item in previous_items if item.get("title")}

    for item in merged["workItems"]:
        previous_item = by_key.get(item["key"]) or by_fingerprint.get(item["fingerprint"]) or by_title.get(item["title"])
        if previous_item:
            item["beadsId"] = previous_item.get("beadsId")

    if previous.get("epic", {}).get("beadsId"):
        merged["epic"]["beadsId"] = previous["epic"]["beadsId"]

    removed = []
    current_keys = {item["key"] for item in merged["workItems"]}
    for old in previous_items:
        if old.get("key") not in current_keys:
            removed.append({"key": old.get("key"), "title": old.get("title"), "beadsId": old.get("beadsId")})
    if removed:
        merged.setdefault("warnings", []).append(
            f"{len(removed)} prior work item(s) are no longer present; review stale Beads issues manually"
        )
        merged["staleItems"] = removed

    return merged


def ensure_beads_workspace(project_root: Path) -> None:
    beads_dir = project_root / ".beads"
    if not beads_dir.exists():
        raise Ops2BeadsError(f"Beads workspace not initialized at {beads_dir}. Run 'br init' first.")


def list_beads_issues(project_root: Path) -> list[dict[str, Any]]:
    issues = run_json(["br", "list", "--json", "--all"], cwd=project_root)
    if not isinstance(issues, list):
        raise Ops2BeadsError("Unexpected response from 'br list --json --all'")
    return issues


def find_existing_issue(
    issues: list[dict[str, Any]], *, label: str, title: str, issue_type: str | None = None
) -> dict[str, Any] | None:
    for issue in issues:
        labels = issue.get("labels") or []
        if label not in labels:
            continue
        if issue.get("title") != title:
            continue
        if issue_type and issue.get("issue_type") != issue_type:
            continue
        return issue
    return None


def br_create_issue(project_root: Path, item: dict[str, Any], parent_id: str | None = None) -> str:
    cmd = [
        "br",
        "create",
        item["title"],
        "--json",
        "-t",
        item["type"],
        "-p",
        str(item["priority"]),
        "-d",
        item["description"],
    ]
    labels = item.get("labels") or []
    if labels:
        cmd.extend(["-l", ",".join(labels)])
    if parent_id:
        cmd.extend(["--parent", parent_id])
    created = run_json(cmd, cwd=project_root)
    if not isinstance(created, dict) or "id" not in created:
        raise Ops2BeadsError("Unexpected response from br create")
    return created["id"]


def br_update_issue(project_root: Path, issue_id: str, item: dict[str, Any], parent_id: str | None = None) -> None:
    cmd = [
        "br",
        "update",
        issue_id,
        "--json",
        "--title",
        item["title"],
        "--description",
        item["description"],
        "-t",
        item["type"],
        "-p",
        str(item["priority"]),
    ]
    labels = item.get("labels") or []
    cmd.extend(["--set-labels", ",".join(labels)])
    if parent_id:
        cmd.extend(["--parent", parent_id])
    run_json(cmd, cwd=project_root)


def br_add_dependency(project_root: Path, child_id: str, parent_id: str) -> None:
    run_json(["br", "dep", "add", child_id, parent_id, "--json"], cwd=project_root)


def refresh_plan_statuses(project_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    beads_dir = project_root / ".beads"
    if not beads_dir.exists():
        return plan
    issues = list_beads_issues(project_root)
    by_id = {issue.get("id"): issue for issue in issues if issue.get("id")}
    epic_id = plan.get("epic", {}).get("beadsId")
    if epic_id:
        plan["epic"]["beadsStatus"] = by_id.get(epic_id, {}).get("status")
    for item in plan.get("workItems", []):
        beads_id = item.get("beadsId")
        item["beadsStatus"] = by_id.get(beads_id, {}).get("status") if beads_id else None
    return plan


def annotate_tasks_file(project_root: Path, plan: dict[str, Any]) -> Path:
    path = tasks_path(project_root, plan["changeName"])
    lines = read_text(path).splitlines()
    items_by_line = {item["sourceRefs"][0].split("#L", 1)[1]: item for item in plan["workItems"] if item.get("sourceRefs")}
    updated_lines: list[str] = []
    for index, line in enumerate(lines, start=1):
        parsed = parse_task_line(line, index)
        item = items_by_line.get(str(index))
        if not parsed or not item:
            updated_lines.append(line)
            continue
        clean_body = ANNOTATION_RE.sub("", parsed.body).rstrip()
        beads_id = item.get("beadsId")
        beads_status = item.get("beadsStatus")
        if beads_id:
            status_suffix = f" status: {beads_status}" if beads_status else ""
            clean_body = f"{clean_body} [beads: {beads_id}{status_suffix}]"
        done = parsed.done or beads_status == "closed"
        updated_lines.append(f"{parsed.indent}- [{'x' if done else ' '}] {clean_body}")
    path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return path


def render_summary(plan: dict[str, Any]) -> str:
    lines = [
        f"# Beads handoff summary: {plan['changeName']}",
        "",
        f"- Change path: `{plan['changePath']}`",
        f"- Schema: `{plan['schemaName']}`",
        f"- Generated: `{plan['generatedAt']}`",
    ]
    if plan.get("epic", {}).get("beadsId"):
        lines.append(f"- Epic: `{plan['epic']['beadsId']}` — {plan['epic']['title']}")
    lines.append("")
    if plan.get("warnings"):
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in plan["warnings"])
        lines.append("")
    if plan.get("staleItems"):
        lines.append("## Stale items")
        for stale in plan["staleItems"]:
            stale_id = stale.get("beadsId") or "pending"
            lines.append(f"- `{stale_id}` {stale.get('key')}: {stale.get('title')}")
        lines.append("")
    lines.append("## Work items")
    by_wave: dict[int, list[dict[str, Any]]] = {}
    for item in plan["workItems"]:
        by_wave.setdefault(item.get("wave", 0), []).append(item)
    for wave in sorted(by_wave):
        lines.extend(["", f"### Wave {wave}"])
        for item in by_wave[wave]:
            beads = item.get("beadsId") or "pending"
            deps = ", ".join(item.get("dependsOn", [])) or "none"
            reasons = "; ".join(item.get("dependencyReasons", [])) or "none"
            prefix = item.get("taskNumber") or item["key"]
            lines.append(f"- `{beads}` `{prefix}` {item['title']} _(depends on: {deps}; reasons: {reasons})_")
    lines.extend([
        "",
        "## Next commands",
        f"- `br ready --json | jq '.[] | select(.labels[]? == \"change:{plan['changeName']}\")'`",
        "- `br sync --flush-only`",
    ])
    return "\n".join(lines) + "\n"


def save_plan(project_root: Path, plan: dict[str, Any], annotate_tasks: bool = False) -> None:
    refresh_plan_statuses(project_root, plan)
    write_json(handoff_path(project_root, plan["changeName"]), plan)
    summary_path(project_root, plan["changeName"]).write_text(render_summary(plan), encoding="utf-8")
    if annotate_tasks:
        annotate_tasks_file(project_root, plan)


def human_plan_summary(plan: dict[str, Any]) -> str:
    lines = [
        f"Change: {plan['changeName']}",
        f"Schema: {plan['schemaName']}",
        f"Work items: {len(plan['workItems'])}",
        f"Dependencies: {plan['summary']['dependencyCount']}",
    ]
    for warning in plan.get("warnings", []):
        lines.append(f"Warning: {warning}")
    if plan.get("staleItems"):
        lines.append(f"Stale items: {len(plan['staleItems'])}")
    for item in plan["workItems"]:
        deps = ", ".join(item["dependsOn"]) or "none"
        prefix = item.get("taskNumber") or item["key"]
        lines.append(f"- [{item['wave']}] {prefix} {item['title']} (deps: {deps})")
    return "\n".join(lines)


def execute_reconcile(project_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    ensure_beads_workspace(project_root)
    issues = list_beads_issues(project_root)
    epic = plan["epic"]
    change_label = f"change:{plan['changeName']}"

    if not epic.get("beadsId"):
        existing_epic = find_existing_issue(issues, label=change_label, title=epic["title"], issue_type="epic")
        if existing_epic:
            epic["beadsId"] = existing_epic["id"]

    if epic.get("beadsId"):
        br_update_issue(project_root, epic["beadsId"], epic)
    else:
        epic["beadsId"] = br_create_issue(project_root, epic)

    issues = list_beads_issues(project_root)
    indexed_issues = {issue["id"]: issue for issue in issues}

    for item in plan["workItems"]:
        if not item.get("beadsId"):
            existing = find_existing_issue(issues, label=change_label, title=item["title"], issue_type=item["type"])
            if existing:
                item["beadsId"] = existing["id"]
        if item.get("beadsId") and item["beadsId"] in indexed_issues:
            br_update_issue(project_root, item["beadsId"], item)
        else:
            item["beadsId"] = br_create_issue(project_root, item, parent_id=epic["beadsId"])

    by_key = {item["key"]: item for item in plan["workItems"]}
    for item in plan["workItems"]:
        child_id = item.get("beadsId")
        if not child_id:
            continue
        for dep_key in item.get("dependsOn", []):
            parent_item = by_key.get(dep_key)
            if parent_item and parent_item.get("beadsId"):
                br_add_dependency(project_root, child_id, parent_item["beadsId"])

    plan["generatedAt"] = iso_now()
    return plan


def build_merged_plan(project_root: Path, change_name: str, allow_task_only: bool) -> dict[str, Any]:
    current = build_plan(project_root, change_name, allow_task_only=allow_task_only)
    previous = load_existing_handoff(project_root, change_name)
    return merge_previous_ids(current, previous)


def do_inspect(args: argparse.Namespace) -> int:
    plan = build_plan(args.project_root, args.change, allow_task_only=args.allow_task_only)
    print(json.dumps(plan, indent=2) if args.json else human_plan_summary(plan))
    return 0


def do_plan(args: argparse.Namespace) -> int:
    plan = build_merged_plan(args.project_root, args.change, args.allow_task_only)
    save_plan(args.project_root, plan, annotate_tasks=args.annotate_tasks)
    print(json.dumps(plan, indent=2) if args.json else f"Wrote {handoff_path(args.project_root, args.change)}")
    return 0


def do_handoff(args: argparse.Namespace) -> int:
    existing = load_existing_handoff(args.project_root, args.change)
    if existing:
        refresh_plan_statuses(args.project_root, existing)
        if args.dry_run:
            print(json.dumps(existing, indent=2) if args.json else human_plan_summary(existing))
            return 0
        write_json(handoff_path(args.project_root, args.change), existing)
        if args.annotate_tasks:
            annotate_tasks_file(args.project_root, existing)
        print(
            json.dumps(existing, indent=2)
            if args.json
            else f"Handoff already exists; mirrored Beads status into {handoff_path(args.project_root, args.change)}"
        )
        return 0

    plan = build_merged_plan(args.project_root, args.change, args.allow_task_only)
    if args.dry_run:
        print(json.dumps(plan, indent=2) if args.json else human_plan_summary(plan))
        return 0
    execute_reconcile(args.project_root, plan)
    save_plan(args.project_root, plan, annotate_tasks=args.annotate_tasks)
    print(json.dumps(plan, indent=2) if args.json else f"Handoff complete. Wrote {handoff_path(args.project_root, args.change)}")
    return 0


def do_reconcile(args: argparse.Namespace) -> int:
    existing = load_existing_handoff(args.project_root, args.change)
    if not existing:
        raise Ops2BeadsError(
            f"No existing handoff file at {handoff_path(args.project_root, args.change)}; run 'plan' or 'handoff' first"
        )
    plan = build_merged_plan(args.project_root, args.change, args.allow_task_only)
    if args.dry_run:
        print(json.dumps(plan, indent=2) if args.json else human_plan_summary(plan))
        return 0
    execute_reconcile(args.project_root, plan)
    save_plan(args.project_root, plan, annotate_tasks=args.annotate_tasks)
    print(json.dumps(plan, indent=2) if args.json else f"Reconciled {handoff_path(args.project_root, args.change)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translate OpenSpec change artifacts into a Beads handoff plan")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--change", required=True, help="OpenSpec change name")
        subparser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Target project root (default: cwd)")
        subparser.add_argument("--allow-task-only", action="store_true", help="Allow planning without specs/")
        subparser.add_argument("--json", action="store_true", help="Emit JSON to stdout")

    inspect_parser = subparsers.add_parser("inspect", help="Read artifacts and print the inferred work graph")
    add_common(inspect_parser)
    inspect_parser.set_defaults(func=do_inspect)

    plan_parser = subparsers.add_parser("plan", help="Write beads-handoff.json and beads-summary.md")
    add_common(plan_parser)
    plan_parser.add_argument("--annotate-tasks", action="store_true", help="Update tasks.md with [beads: ...] tags")
    plan_parser.set_defaults(func=do_plan)

    handoff_parser = subparsers.add_parser("handoff", help="First run: create Beads issues. Later runs: mirror Beads status into the saved handoff and optionally tasks.md")
    add_common(handoff_parser)
    handoff_parser.add_argument("--dry-run", action="store_true", help="Do not mutate Beads or write mirrored output")
    handoff_parser.add_argument("--annotate-tasks", action="store_true", help="Update tasks.md with [beads: ...] tags")
    handoff_parser.add_argument("--yes", action="store_true", help="Accepted for compatibility; handoff is non-interactive")
    handoff_parser.set_defaults(func=do_handoff)

    reconcile_parser = subparsers.add_parser("reconcile", help="Rebuild plan and reconcile an existing handoff with Beads")
    add_common(reconcile_parser)
    reconcile_parser.add_argument("--dry-run", action="store_true", help="Do not mutate Beads")
    reconcile_parser.add_argument("--annotate-tasks", action="store_true", help="Update tasks.md with [beads: ...] tags")
    reconcile_parser.set_defaults(func=do_reconcile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.project_root = args.project_root.resolve()
    try:
        return args.func(args)
    except Ops2BeadsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
