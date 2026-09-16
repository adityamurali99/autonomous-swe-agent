from pathlib import Path

from swe_agent.context import ContextConfig, ContextSelector
from swe_agent.models import AgentState, Event, Observation, ToolCall


def event(name: str, output: str, **arguments: object) -> Event:
    return Event(ToolCall(name, arguments), Observation(True, output))


def test_context_selector_keeps_full_trace_untouched_and_latest_file_read() -> None:
    state = AgentState(Path("/repo"), "fix bug")
    state.events = [
        event("read_file", "old contents", path="module.py"),
        event("list_files", "large listing " * 100),
        event("read_file", "current contents", path="module.py"),
        event("search_code", "relevant match", query="target"),
    ]
    selector = ContextSelector(ContextConfig(max_characters=300, recent_events=2))

    selected = selector.select(state)

    assert len(state.events) == 4
    assert state.events[0].observation.output == "old contents"
    assert selected[-2:] == state.events[-2:]
    assert state.events[0] not in selected


def test_context_selector_preserves_important_old_failure_and_edit() -> None:
    failure = Event(
        ToolCall("run_tests", {"command": "pytest test_bug.py"}),
        Observation(False, "assertion failed"),
    )
    edit = event("edit_file", "edited module.py", path="module.py")
    state = AgentState(Path("/repo"), "fix bug")
    state.events = [failure, edit, *(event("list_files", f"listing {index}") for index in range(8))]

    selected = ContextSelector(ContextConfig(max_characters=2_000, recent_events=2)).select(state)

    assert failure in selected
    assert edit in selected
    assert state.events[-1] in selected


def test_context_selector_elides_large_observations_for_model_only() -> None:
    original = "x" * 5_000
    state = AgentState(Path("/repo"), "fix bug", events=[event("read_file", original, path="huge.py")])

    selected = ContextSelector(
        ContextConfig(max_characters=2_000, max_observation_characters=500)
    ).select(state)

    assert len(selected[0].observation.output) < 600
    assert "elided for model context" in selected[0].observation.output
    assert state.events[0].observation.output == original
