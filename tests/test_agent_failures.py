from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from swe_agent.agent import Agent
from swe_agent.models import AgentState, Finish, JsonObject, ModelUsage, ResourceLimits, ToolCall
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


class StaleDiffModel:
    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> ToolCall | Finish:
        del tool_schemas
        actions = [
            ToolCall("edit_file", {"path": "README.md", "old_text": "fixture\n", "new_text": "fixed\n"}),
            ToolCall("edit_file", {"path": "temporary.txt", "old_text": "", "new_text": "temporary\n"}),
            ToolCall("run_tests", {"command": "true"}),
            ToolCall("inspect_diff", {}),
            ToolCall("run_command", {"command": "rm temporary.txt"}),
            ToolCall("run_tests", {"command": "true"}),
            Finish("fixed and cleaned up"),
        ]
        return actions[state.step]


class MutatingValidationModel:
    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> ToolCall | Finish:
        del tool_schemas
        actions = [
            ToolCall("run_tests", {"command": "printf x >> README.md"}),
            ToolCall("inspect_diff", {}),
            Finish("validation passed"),
        ]
        return actions[state.step]


class TokenLimitedModel:
    def __init__(self) -> None:
        self.usage = ModelUsage()

    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> ToolCall:
        del state, tool_schemas
        self.usage = ModelUsage(requests=1, input_tokens=80, output_tokens=20, total_tokens=100)
        return ToolCall("read_file", {"path": "README.md"})


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
    assert trace["schema_version"] == 4
    assert trace["usage"]["requests"] == 2
    assert trace["runtime_seconds"] >= 0
    assert trace["events"][0]["observation"]["success"] is False
    assert '"status": "step_limit"' in trace_path.read_text()


def test_final_patch_is_captured_after_temporary_file_cleanup(tmp_path: Path):
    init_clean_repository(tmp_path)

    state = Agent(StaleDiffModel(), tmp_path).run("Fix README without returning temporary files")

    assert state.status == "completed"
    assert state.final_validation is not None and state.final_validation.success
    assert state.final_patch is not None
    assert "+fixed" in state.final_patch
    assert "temporary.txt" not in state.final_patch
    assert "temporary.txt" in state.events[3].observation.output


def test_completion_is_rejected_when_final_validation_mutates_repository(tmp_path: Path):
    init_clean_repository(tmp_path)

    state = Agent(MutatingValidationModel(), tmp_path, max_steps=3).run("Detect mutating validation")

    assert state.status == "step_limit"
    assert state.final_patch is None
    assert state.final_validation is not None and state.final_validation.success
    assert not state.validation_succeeded
    assert "final validation modified the working tree" in state.events[-1].observation.output.lower()


def test_stops_before_next_decision_when_token_limit_is_reached(tmp_path: Path):
    init_clean_repository(tmp_path)

    state = Agent(
        TokenLimitedModel(),
        tmp_path,
        limits=ResourceLimits(max_total_tokens=100),
    ).run("Respect the token budget")

    assert state.status == "resource_limit"
    assert state.step == 1
    assert state.usage.total_tokens == 100
    assert state.error == "Resource limit reached: total tokens 100 >= 100"
