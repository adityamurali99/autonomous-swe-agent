from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from swe_agent.models import Event, ToolCall


@dataclass(frozen=True)
class Progress:
    repository_inspected: bool = False
    reproduction_attempted: bool = False
    reproduction_succeeded: bool = False
    source_localized: bool = False
    code_modified: bool = False
    post_edit_validation_succeeded: bool = False
    final_diff_reviewed: bool = False
    guidance: str | None = None

    def as_dict(self) -> dict[str, bool | str | None]:
        return {
            "repository_inspected": self.repository_inspected,
            "reproduction_attempted": self.reproduction_attempted,
            "reproduction_succeeded": self.reproduction_succeeded,
            "source_localized": self.source_localized,
            "code_modified": self.code_modified,
            "post_edit_validation_succeeded": self.post_edit_validation_succeeded,
            "final_diff_reviewed": self.final_diff_reviewed,
            "guidance": self.guidance,
        }


class ProgressTracker:
    """Derive engineering progress and targeted anti-stagnation guidance from events."""

    def evaluate(self, events: list[Event]) -> Progress:
        inspected = False
        reproduction_attempts = 0
        reproduction_succeeded = False
        localized = False
        modified = False
        validated_after_edit = False
        diff_reviewed = False
        last_edit = -1
        last_validation = -1

        for index, event in enumerate(events):
            if not isinstance(event.action, ToolCall):
                continue
            name = event.action.name
            if name in {"list_files", "search_code", "read_file"}:
                inspected = True
            if name == "search_code" and int(event.observation.metadata.get("matches", 0)) > 0:
                localized = True
            if name == "read_file" and event.observation.success:
                path = str(event.action.arguments.get("path", ""))
                localized = localized or not self._is_test_or_reproduction_path(path)
            if name == "edit_file" and event.observation.success:
                path = str(event.action.arguments.get("path", ""))
                if self._is_test_or_reproduction_path(path):
                    reproduction_attempts += 1
                else:
                    modified = True
                    last_edit = index
                    validated_after_edit = False
                    diff_reviewed = False
            if name == "run_tests" or (name == "run_command" and self._looks_like_test_command(event)):
                last_validation = index
                if not modified:
                    reproduction_attempts += 1
                    reproduction_succeeded = reproduction_succeeded or not event.observation.success
                elif event.observation.success and index > last_edit:
                    validated_after_edit = True
            if name == "inspect_diff" and event.observation.success and index > last_edit:
                diff_reviewed = True

        guidance = None
        if reproduction_attempts >= 2 and not modified:
            guidance = (
                "The issue has already been exercised multiple times. Stop creating or varying "
                "reproductions; inspect the production implementation, form a causal hypothesis, "
                "and make the smallest relevant code change."
            )
        elif inspected and not localized:
            guidance = "Narrow the search to the symbols and implementation path implicated by the task."
        elif modified and last_validation <= last_edit:
            guidance = "Validate the latest edit with the narrowest relevant test or reproduction."

        return Progress(
            repository_inspected=inspected,
            reproduction_attempted=reproduction_attempts > 0,
            reproduction_succeeded=reproduction_succeeded,
            source_localized=localized,
            code_modified=modified,
            post_edit_validation_succeeded=validated_after_edit,
            final_diff_reviewed=diff_reviewed,
            guidance=guidance,
        )

    @staticmethod
    def _looks_like_test_command(event: Event) -> bool:
        if not isinstance(event.action, ToolCall):
            return False
        command = str(event.action.arguments.get("command", "")).lower()
        indicators = ("pytest", "unittest", "tox", "nox", " test", "test_", "repro")
        return any(indicator in command for indicator in indicators)

    @staticmethod
    def _is_test_or_reproduction_path(raw_path: str) -> bool:
        path = PurePosixPath(raw_path.replace("\\", "/"))
        name = path.name.lower()
        return (
            any(part.lower() in {"test", "tests", "testing"} for part in path.parts[:-1])
            or name.startswith(("test_", "repro", "tmp_", "temporary_"))
            or name.endswith(("_test.py", "_tests.py"))
        )
