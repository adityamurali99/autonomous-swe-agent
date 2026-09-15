from pathlib import Path

from swe_agent.benchmarks.swebench_lite import (
    AGENT_FIELDS,
    AgentTask,
    agent_view,
    diagnostic_tags,
    load_agent_tasks,
    select_diagnostic_tasks,
    write_mirror,
)


def task(identifier: str, repo: str = "owner/repo", patch: str = "diff --git a/a.py b/a.py\n+x") -> dict:
    return {
        "instance_id": identifier,
        "repo": repo,
        "base_commit": "a" * 40,
        "problem_statement": "Fix the behavior",
        "version": "1.0",
        "patch": patch,
        "test_patch": "secret tests",
        "FAIL_TO_PASS": '["one"]',
        "PASS_TO_PASS": '["existing"]',
    }


def test_agent_view_excludes_every_evaluator_only_field():
    projected = agent_view(task("one"))

    assert set(projected.__dict__) == set(AGENT_FIELDS)
    assert "patch" not in projected.__dict__
    assert "test_patch" not in projected.__dict__
    assert "FAIL_TO_PASS" not in projected.__dict__


def test_diagnostic_selection_is_deterministic_and_repository_aware():
    tasks = [task(str(index), f"owner/repo-{index % 3}") for index in range(8)]

    first = select_diagnostic_tasks(tasks, 5, "fixed")
    second = select_diagnostic_tasks(tasks, 5, "fixed")

    assert [item["instance_id"] for item in first] == [item["instance_id"] for item in second]
    assert len({item["repo"] for item in first[:3]}) == 3


def test_tags_capture_patch_scope_and_test_signal():
    multi_file_patch = "diff --git a/a.py b/a.py\n+x\ndiff --git a/b.py b/b.py\n-y"
    value = task("one", patch=multi_file_patch)
    value["problem_statement"] = "x" * 5_000
    value["PASS_TO_PASS"] = str([str(index) for index in range(25)]).replace("'", '"')

    assert diagnostic_tags(value) == [
        "multi_file",
        "small_patch",
        "long_issue",
        "weak_failure_signal",
        "broad_regression",
    ]


def test_mirror_keeps_agent_and_evaluator_files_separate(tmp_path: Path):
    tasks = [task(str(index), f"owner/repo-{index % 4}") for index in range(50)]

    write_mirror(tasks, tmp_path)

    agent_tasks = load_agent_tasks(tmp_path / "agent" / "tasks.jsonl")
    assert agent_tasks["0"] == AgentTask("0", "owner/repo-0", "a" * 40, "Fix the behavior", "1.0")
    assert "secret tests" not in (tmp_path / "agent" / "tasks.jsonl").read_text()
    assert "secret tests" in (tmp_path / "evaluator" / "tasks.jsonl").read_text()
    assert (tmp_path / "manifests" / "smoke-10.json").is_file()
    assert (tmp_path / "manifests" / "diagnostic-50.json").is_file()
