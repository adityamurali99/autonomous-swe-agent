from pathlib import Path

from swe_agent.tools import RepositoryTools


def init_repository(path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def test_rejects_paths_outside_repository(tmp_path: Path):
    init_repository(tmp_path)
    tools = RepositoryTools(tmp_path)
    result = tools.execute("read_file", {"path": "../secret.txt"})
    assert not result.success
    assert "escapes repository" in result.output


def test_exact_edit_refuses_ambiguous_replacement(tmp_path: Path):
    init_repository(tmp_path)
    (tmp_path / "value.txt").write_text("x x")
    tools = RepositoryTools(tmp_path)
    result = tools.execute("edit_file", {"path": "value.txt", "old_text": "x", "new_text": "y"})
    assert not result.success
    assert (tmp_path / "value.txt").read_text() == "x x"


def test_create_file_is_included_in_diff(tmp_path: Path):
    init_repository(tmp_path)
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


def test_inspect_diff_finds_untracked_files_created_by_commands(tmp_path: Path):
    init_repository(tmp_path)
    tools = RepositoryTools(tmp_path)

    created = tools.execute("run_command", {"command": "printf 'from command\\n' > command-created.txt"})
    diff = tools.execute("inspect_diff", {})

    assert created.success
    assert diff.success
    assert "command-created.txt" in diff.output
    assert "+from command" in diff.output


def test_inspect_diff_includes_staged_changes(tmp_path: Path):
    init_repository(tmp_path)
    (tmp_path / "tracked.txt").write_text("before\n")
    import subprocess

    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.txt").write_text("after\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)

    diff = RepositoryTools(tmp_path).execute("inspect_diff", {})

    assert diff.success
    assert "-before" in diff.output
    assert "+after" in diff.output
