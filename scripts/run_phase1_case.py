from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from swe_agent.agent import Agent
from swe_agent.gemini_model import GeminiModel
from swe_agent.models import ToolCall
from swe_agent.trace import state_to_trace


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def changed_files(repository: Path) -> list[str]:
    tracked = run(["git", "diff", "--name-only"], repository).stdout.splitlines()
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"], repository).stdout.splitlines()
    return sorted(set(tracked + untracked))


def final_patch(state: Any) -> str:
    for event in reversed(state.events):
        if isinstance(event.action, ToolCall) and event.action.name == "inspect_diff":
            return cast(str, event.observation.output)
    return ""


def normalized_patch(patch: str) -> str:
    meaningful_lines = [
        line
        for line in patch.splitlines()
        if line.startswith("diff --git ")
        or (line.startswith(("+", "-")) and not line.startswith(("+++", "---")))
    ]
    return "\n".join(meaningful_lines)


def sanitized_json(value: Any, repository: Path) -> str:
    rendered = json.dumps(value, indent=2, ensure_ascii=False)
    return rendered.replace(str(repository), "<temporary-repository>") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one documented Phase 1 Gemini case")
    parser.add_argument("case_directory", type=Path)
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--output-root", type=Path, default=Path("phase1/results"))
    args = parser.parse_args()

    case_directory = args.case_directory.resolve()
    case = json.loads((case_directory / "case.json").read_text())
    output = args.output_root / case["id"]
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"swe-agent-{case['id']}-") as temporary:
        repository = Path(temporary) / "repository"
        shutil.copytree(case_directory / "repository", repository)
        if setup_command := case.get("setup_command"):
            setup = subprocess.run(
                setup_command,
                cwd=repository,
                shell=True,
                text=True,
                capture_output=True,
                check=False,
            )
            if setup.returncode != 0:
                raise RuntimeError(f"Case setup failed:\n{setup.stdout}{setup.stderr}")
        run(["git", "init", "-q", "-b", "main"], repository)
        run(["git", "add", "."], repository)
        run(
            [
                "git", "-c", "user.name=Phase 1", "-c", "user.email=phase1@example.com",
                "commit", "-qm", "fixture",
            ],
            repository,
        )

        state = Agent(GeminiModel(args.model), repository, max_steps=args.max_steps).run(case["task"])
        patch = final_patch(state)
        validation = subprocess.run(
            case["validation_command"],
            cwd=repository,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        actual_files = changed_files(repository)
        content_checks = {
            path: all(expected in (repository / path).read_text() for expected in expected_values)
            for path, expected_values in case["expected_content"].items()
        }
        checks = {
            "agent_completed": state.status == "completed",
            "agent_validation_succeeded": state.validation_succeeded,
            "independent_validation_passed": validation.returncode == 0,
            "changed_files_match": actual_files == sorted(case["expected_changed_files"]),
            "expected_content_present": all(content_checks.values()),
        }
        reference_patch = (case_directory / "expected.patch").read_text()
        assessment = {
            "case_id": case["id"],
            "model": args.model,
            "expected_behavior": case["expected_behavior"],
            "passed": all(checks.values()),
            "checks": checks,
            "expected_changed_files": case["expected_changed_files"],
            "actual_changed_files": actual_files,
            "content_checks": content_checks,
            "patch_comparison": {
                "normalized_reference_matches": normalized_patch(reference_patch) == normalized_patch(patch)
            },
            "validation": {
                "command": case["validation_command"],
                "exit_code": validation.returncode,
                "stdout": validation.stdout,
                "stderr": validation.stderr,
            },
        }
        trace = state_to_trace(state)
        trace["repository"] = "<temporary-repository>"
        trace["model"] = args.model
        (output / "trace.json").write_text(sanitized_json(trace, repository))
        (output / "actual.patch").write_text(patch)
        (output / "assessment.json").write_text(sanitized_json(assessment, repository))
        print(json.dumps(assessment, indent=2))
        if not assessment["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
