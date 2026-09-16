from swe_agent.models import Event, Observation, ToolCall
from swe_agent.progress import ProgressTracker


def event(name: str, success: bool = True, output: str = "", **arguments: object) -> Event:
    return Event(ToolCall(name, arguments), Observation(success, output))


def test_repeated_reproduction_files_trigger_localization_guidance() -> None:
    progress = ProgressTracker().evaluate(
        [
            event("edit_file", path="repro_bug.py", old_text="", new_text="..."),
            event("run_command", False, "failed", command="python repro_bug.py"),
            event("edit_file", path="test_repro_bug.py", old_text="", new_text="..."),
        ]
    )

    assert progress.reproduction_attempted
    assert progress.reproduction_succeeded
    assert not progress.code_modified
    assert progress.guidance is not None
    assert "inspect the production implementation" in progress.guidance


def test_progress_tracks_localization_edit_validation_and_diff() -> None:
    search = Event(
        ToolCall("search_code", {"query": "broken"}),
        Observation(True, "module.py:2:broken", {"matches": 1}),
    )
    progress = ProgressTracker().evaluate(
        [
            event("list_files", output="module.py"),
            search,
            event("edit_file", path="module.py", old_text="broken", new_text="fixed"),
            event("run_tests", command="pytest tests/test_module.py"),
            event("inspect_diff", output="diff"),
        ]
    )

    assert progress.repository_inspected
    assert progress.source_localized
    assert progress.code_modified
    assert progress.post_edit_validation_succeeded
    assert progress.final_diff_reviewed
    assert progress.guidance is None


def test_latest_edit_requires_new_validation_and_diff_review() -> None:
    progress = ProgressTracker().evaluate(
        [
            event("edit_file", path="module.py", old_text="a", new_text="b"),
            event("run_tests", command="pytest"),
            event("inspect_diff"),
            event("edit_file", path="module.py", old_text="b", new_text="c"),
        ]
    )

    assert not progress.post_edit_validation_succeeded
    assert not progress.final_diff_reviewed
    assert progress.guidance == "Validate the latest edit with the narrowest relevant test or reproduction."
