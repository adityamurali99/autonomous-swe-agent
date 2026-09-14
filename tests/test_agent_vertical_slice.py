from __future__ import annotations

import subprocess
from pathlib import Path

from swe_agent.agent import Agent
from swe_agent.models import AgentState, Finish, JsonObject, ToolCall


class ScriptedModel:
    """A deterministic policy that exercises inspection, failure recovery, and completion."""

    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> ToolCall | Finish:
        del tool_schemas
        actions = [
            ToolCall("list_files", {}),
            ToolCall("search_code", {"query": "add_one"}),
            ToolCall("read_file", {"path": "maths.py"}),
            ToolCall(
                "edit_file",
                {"path": "maths.py", "old_text": "return value + 2", "new_text": "return value - 10"},
            ),
            ToolCall("run_tests", {"command": "python -m unittest discover"}),
            ToolCall(
                "edit_file",
                {"path": "maths.py", "old_text": "return value - 10", "new_text": "return value + 1"},
            ),
            ToolCall("run_tests", {"command": "python -m unittest discover"}),
            ToolCall("inspect_diff", {}),
            Finish("Fixed add_one and validated with the unittest suite."),
        ]
        return actions[state.step]


def test_agent_produces_validated_patch_after_recovering_from_failure(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "maths.py").write_text("def add_one(value: int) -> int:\n    return value + 2\n")
    (tmp_path / "test_maths.py").write_text(
        "import unittest\nfrom maths import add_one\n\n"
        "class TestMaths(unittest.TestCase):\n"
        "    def test_add_one(self):\n        self.assertEqual(add_one(2), 3)\n"
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        cwd=tmp_path,
        check=True,
    )

    state = Agent(ScriptedModel(), tmp_path).run("add_one returns the wrong value")

    assert state.status == "completed"
    assert state.validation_succeeded
    assert state.diff_inspected
    assert "return value + 1" in (tmp_path / "maths.py").read_text()
    failures = [
        event
        for event in state.events
        if isinstance(event.action, ToolCall)
        and event.action.name == "run_tests"
        and not event.observation.success
    ]
    assert len(failures) == 1
    diff_event = state.events[-2]
    assert "-    return value + 2" in diff_event.observation.output
    assert "+    return value + 1" in diff_event.observation.output
