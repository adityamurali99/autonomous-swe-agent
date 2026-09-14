from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from swe_agent.agent import Agent
from swe_agent.models import AgentState, Finish, JsonObject, ToolCall
from swe_agent.trace import state_to_trace, write_trace


def init_clean_repository(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    (path / "README.md").write_text("fixture\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        cwd=path,
        check=True,
    )


class RepeatingModel:
    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> ToolCall:
        del state, tool_schemas
        return ToolCall("read_file", {"path": "README.md"})


class FailingModel:
    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> Finish:
        del state, tool_schemas
        raise RuntimeError("provider unavailable")


class PrematureFinishModel:
    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> Finish:
        del tool_schemas
        return Finish("done")


def test_rejects_non_git_repository(tmp_path: Path):
    with pytest.raises(ValueError, match="Not a Git repository"):
        Agent(RepeatingModel(), tmp_path)


def test_rejects_dirty_repository_by_default(tmp_path: Path):
    init_clean_repository(tmp_path)
    (tmp_path / "README.md").write_text("changed\n")
    with pytest.raises(ValueError, match="uncommitted changes"):
        Agent(RepeatingModel(), tmp_path)


def test_stops_repeated_identical_actions(tmp_path: Path):
    init_clean_repository(tmp_path)
    state = Agent(RepeatingModel(), tmp_path, max_repeated_actions=3).run("Read forever")
    assert state.status == "no_progress"
    assert state.step == 3


def test_model_exception_becomes_terminal_state(tmp_path: Path):
    init_clean_repository(tmp_path)
    state = Agent(FailingModel(), tmp_path).run("Trigger provider failure")
    assert state.status == "model_error"
    assert state.error == "RuntimeError: provider unavailable"


def test_premature_finish_reaches_step_limit_and_trace_is_written(tmp_path: Path):
    init_clean_repository(tmp_path)
    state = Agent(PrematureFinishModel(), tmp_path, max_steps=2).run("Finish too early")
    trace_path = tmp_path / "trace.json"
    write_trace(state, trace_path)
    trace = state_to_trace(state)

    assert state.status == "step_limit"
    assert len(state.events) == 2
    assert trace["schema_version"] == 1
    assert trace["events"][0]["observation"]["success"] is False
    assert '"status": "step_limit"' in trace_path.read_text()
