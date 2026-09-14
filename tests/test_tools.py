from pathlib import Path

from swe_agent.tools import RepositoryTools


def test_rejects_paths_outside_repository(tmp_path: Path):
    tools = RepositoryTools(tmp_path)
    result = tools.execute("read_file", {"path": "../secret.txt"})
    assert not result.success
    assert "escapes repository" in result.output


def test_exact_edit_refuses_ambiguous_replacement(tmp_path: Path):
    (tmp_path / "value.txt").write_text("x x")
    tools = RepositoryTools(tmp_path)
    result = tools.execute("edit_file", {"path": "value.txt", "old_text": "x", "new_text": "y"})
    assert not result.success
    assert (tmp_path / "value.txt").read_text() == "x x"


def test_create_file_is_included_in_diff(tmp_path: Path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    tools = RepositoryTools(tmp_path)

    edit = tools.execute(
        "edit_file",
        {"path": "src/new_module.py", "old_text": "", "new_text": "VALUE = 1\n"},
    )
    diff = tools.execute("inspect_diff", {})

    assert edit.success
    assert diff.success
    assert "--- /dev/null" in diff.output
    assert "+++ b/src/new_module.py" in diff.output
    assert "+VALUE = 1" in diff.output
    assert diff.metadata["untracked_files"] == ["src/new_module.py"]
