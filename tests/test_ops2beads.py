from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "openspec2beads" / "scripts" / "ops2beads.py"


class Ops2BeadsCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name)
        self.change_dir = self.project_root / "openspec" / "changes" / "add-dark-mode"
        (self.change_dir / "specs" / "ui").mkdir(parents=True)

        (self.change_dir / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
        (self.change_dir / "proposal.md").write_text(
            textwrap.dedent(
                """\
                # Proposal

                ## Why
                Users need dark mode.

                ## New Capabilities
                - ui
                """
            ),
            encoding="utf-8",
        )
        (self.change_dir / "design.md").write_text(
            textwrap.dedent(
                """\
                # Design

                ## Technical Approach
                Introduce a ThemeContext provider, then connect settings and header toggles to it.
                """
            ),
            encoding="utf-8",
        )
        self.write_tasks(
            """\
            # Tasks

            ## 1. Theme Infrastructure
            - [ ] 1.1 Create ThemeContext with light/dark state
            - [ ] 1.2 Implement localStorage persistence after 1.1
            - [ ] 1.3 Define CSS custom properties for the dark palette

            ## 2. UI Components
            - [ ] 2.1 Create ThemeToggle component
            - [ ] 2.2 Add theme toggle to settings page
            - [ ] 2.3 Add quick toggle to header
            - [ ] 2.4 Update existing components to use CSS variables
            """
        )
        (self.change_dir / "specs" / "ui" / "spec.md").write_text(
            textwrap.dedent(
                """\
                # UI Spec

                ## ADDED Requirements

                ### Requirement: Theme Selection
                The system MUST support light and dark themes.

                #### Scenario: User switches theme from settings
                - **WHEN** the user toggles the theme in settings
                - **THEN** the selected theme is applied immediately

                #### Scenario: Theme persists across sessions
                - **WHEN** a user has previously selected a theme
                - **THEN** the same theme is restored on next launch
                """
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_tasks(self, content: str) -> None:
        (self.change_dir / "tasks.md").write_text(textwrap.dedent(content), encoding="utf-8")

    def run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            self.fail(f"command failed: {' '.join(args)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
        return proc

    def handoff_file(self) -> Path:
        return self.change_dir / "beads-handoff.json"

    def read_handoff(self) -> dict:
        return json.loads(self.handoff_file().read_text(encoding="utf-8"))

    def init_beads(self) -> None:
        subprocess.run(["br", "init"], cwd=self.project_root, check=True, capture_output=True, text=True)

    def list_issues(self) -> list[dict]:
        return json.loads(
            subprocess.run(
                ["br", "list", "--json", "--all"],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )

    def test_running_without_command_shows_help(self) -> None:
        proc = self.run_cli(check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage:", proc.stdout)

    def test_inspect_infers_dependencies(self) -> None:
        proc = self.run_cli("inspect", "add-dark-mode", "--json")
        payload = json.loads(proc.stdout)

        self.assertEqual(payload["changeName"], "add-dark-mode")
        self.assertEqual(payload["epic"]["type"], "epic")
        self.assertEqual(len(payload["workItems"]), 7)

        by_number = {item["taskNumber"]: item for item in payload["workItems"]}
        self.assertEqual(by_number["1.2"]["dependsOn"], ["1.1"])
        self.assertIn("1.1", by_number["2.2"]["dependsOn"])
        self.assertIn("2.1", by_number["2.2"]["dependsOn"])
        self.assertIn("1.3", by_number["2.4"]["dependsOn"])
        self.assertTrue(by_number["2.2"]["dependencyReasons"])

        self.assertIn("analysisWarnings", payload)
        self.assertIn("suggestedGaps", payload)
        self.assertIn("readiness", payload)
        self.assertTrue(payload["readiness"]["readyToSync"])
        self.assertEqual(payload["summary"]["suggestedGapCount"], 1)
        self.assertEqual(payload["summary"]["analysisWarningCount"], 0)
        self.assertEqual(by_number["1.1"]["suggestedType"], "feature")
        self.assertEqual(by_number["1.1"]["priority"], 1)
        self.assertEqual(by_number["1.1"]["complexity"], "medium")
        self.assertEqual(by_number["1.1"]["origin"], "openspec-task")
        self.assertIn("complexity:medium", by_number["1.1"]["labels"])
        self.assertEqual(payload["suggestedGaps"][0]["kind"], "missing-tests")

        self.assertFalse(self.handoff_file().exists())

    def test_inspect_infers_priority_type_complexity_across_task_shapes(self) -> None:
        self.write_tasks(
            """\
            # Tasks

            ## 1. Backend
            - [ ] 1.1 Create users table migration
            - [ ] 1.2 Implement registration endpoint after 1.1
            - [ ] 1.3 Write integration tests for registration endpoint
            - [ ] 1.4 Document auth API flow
            """
        )

        proc = self.run_cli("inspect", "add-dark-mode", "--json")
        payload = json.loads(proc.stdout)
        by_number = {item["taskNumber"]: item for item in payload["workItems"]}

        self.assertEqual(by_number["1.1"]["priority"], 0)
        self.assertEqual(by_number["1.1"]["complexity"], "high")
        self.assertEqual(by_number["1.1"]["suggestedType"], "task")
        self.assertEqual(by_number["1.2"]["priority"], 1)
        self.assertEqual(by_number["1.2"]["suggestedType"], "feature")
        self.assertEqual(by_number["1.2"]["complexity"], "medium")
        self.assertEqual(by_number["1.3"]["priority"], 1)
        self.assertEqual(by_number["1.3"]["suggestedType"], "task")
        self.assertEqual(by_number["1.4"]["priority"], 1)
        self.assertEqual(by_number["1.4"]["suggestedType"], "chore")

    def test_inspect_reports_broad_task_and_missing_rollback_gaps(self) -> None:
        self.write_tasks(
            """\
            # Tasks

            ## 1. Auth
            - [ ] 1.1 Implement complete authentication system with login, refresh, logout, roles, and permissions
            - [ ] 1.2 Create users table migration
            - [ ] 1.3 Implement registration endpoint after 1.2
            """
        )

        proc = self.run_cli("inspect", "add-dark-mode", "--json")
        payload = json.loads(proc.stdout)

        self.assertTrue(payload["analysisWarnings"])
        self.assertTrue(any("Task 1.1 looks broad" in warning for warning in payload["analysisWarnings"]))
        gap_kinds = {item["kind"] for item in payload["suggestedGaps"]}
        self.assertIn("missing-tests", gap_kinds)
        self.assertIn("missing-rollback", gap_kinds)
        self.assertIn("missing-monitoring", gap_kinds)
        self.assertIn("missing-rate-limiting", gap_kinds)

    def test_sync_bootstraps_once_then_mirrors_without_duplicates(self) -> None:
        self.init_beads()

        self.run_cli("sync", "add-dark-mode")
        handoff = self.read_handoff()
        target = next(item for item in handoff["workItems"] if item["taskNumber"] == "1.1")
        subprocess.run(
            ["br", "close", target["beadsId"], "--json", "-r", "done"],
            cwd=self.project_root,
            check=True,
            capture_output=True,
            text=True,
        )

        self.run_cli("sync", "add-dark-mode")

        issues = self.list_issues()
        self.assertEqual(len(issues), 8)
        labels = {label for issue in issues for label in issue.get("labels", [])}
        self.assertIn("change:add-dark-mode", labels)

        handoff_after = self.read_handoff()
        self.assertTrue(handoff_after["epic"]["beadsId"])
        self.assertTrue(all(item["beadsId"] for item in handoff_after["workItems"]))
        mirrored = next(item for item in handoff_after["workItems"] if item["taskNumber"] == "1.1")
        self.assertEqual(mirrored["beadsStatus"], "closed")
        tasks_text = (self.change_dir / "tasks.md").read_text(encoding="utf-8")
        self.assertIn(f"- [x] 1.1 Create ThemeContext with light/dark state [beads: {target['beadsId']} status: closed]", tasks_text)

    def test_sync_reports_stale_items_after_task_removal(self) -> None:
        self.init_beads()
        self.run_cli("sync", "add-dark-mode")

        self.write_tasks(
            """\
            # Tasks

            ## 1. Theme Infrastructure
            - [ ] 1.1 Create ThemeContext with light/dark state
            - [ ] 1.2 Implement localStorage persistence after 1.1

            ## 2. UI Components
            - [ ] 2.2 Add theme toggle to settings page
            - [ ] 2.4 Update existing components to use CSS variables
            """
        )

        proc = self.run_cli("sync", "add-dark-mode", "--json")
        payload = json.loads(proc.stdout)

        self.assertIn("staleItems", payload)
        stale_keys = {item["key"] for item in payload["staleItems"]}
        self.assertIn("1.3", stale_keys)
        self.assertIn("2.1", stale_keys)
        self.assertIn("2.3", stale_keys)

    def test_sync_writes_status_aware_tags_and_beads_status_wins_over_checkbox(self) -> None:
        self.init_beads()
        self.run_cli("sync", "add-dark-mode")

        tasks_text = (self.change_dir / "tasks.md").read_text(encoding="utf-8")
        self.assertIn("[beads:", tasks_text)
        self.assertIn("status: open", tasks_text)
        self.assertEqual(tasks_text.count("[beads:"), 7)

        self.write_tasks(
            """\
            # Tasks

            ## 1. Theme Infrastructure
            - [x] 1.1 Create ThemeContext with light/dark state
            - [ ] 1.2 Implement localStorage persistence after 1.1
            - [ ] 1.3 Define CSS custom properties for the dark palette

            ## 2. UI Components
            - [ ] 2.1 Create ThemeToggle component
            - [ ] 2.2 Add theme toggle to settings page
            - [ ] 2.3 Add quick toggle to header
            - [ ] 2.4 Update existing components to use CSS variables
            """
        )
        self.run_cli("sync", "add-dark-mode")
        tasks_text = (self.change_dir / "tasks.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] 1.1 Create ThemeContext with light/dark state", tasks_text)

    def test_sync_accepts_change_directory_path(self) -> None:
        self.init_beads()
        proc = self.run_cli("sync", str(self.change_dir), "--json")
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["changeName"], "add-dark-mode")
        self.assertTrue(self.handoff_file().exists())

    def test_sync_does_not_create_beads_issues_from_suggested_gaps(self) -> None:
        self.write_tasks(
            """\
            # Tasks

            ## 1. Auth
            - [ ] 1.1 Create users table migration
            - [ ] 1.2 Implement registration endpoint after 1.1
            """
        )
        inspect_payload = json.loads(self.run_cli("inspect", "add-dark-mode", "--json").stdout)
        self.assertGreaterEqual(len(inspect_payload["suggestedGaps"]), 1)

        self.init_beads()
        self.run_cli("sync", "add-dark-mode")

        issues = self.list_issues()
        self.assertEqual(len(issues), 3)
        issue_titles = {issue["title"] for issue in issues}
        self.assertIn("Implement OpenSpec change add-dark-mode", issue_titles)
        self.assertIn("Create users table migration", issue_titles)
        self.assertIn("Implement registration endpoint after 1.1", issue_titles)
        self.assertFalse(any("Add explicit tests" in title for title in issue_titles))
        self.assertFalse(any("rollback" in title.lower() for title in issue_titles))


if __name__ == "__main__":
    unittest.main()
