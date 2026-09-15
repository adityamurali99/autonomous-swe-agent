from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
CASES = [
    case
    for cases_root in (ROOT / "phase1" / "cases", ROOT / "phase2" / "cases")
    for case in cases_root.iterdir()
]


@pytest.mark.parametrize("case_directory", sorted(CASES), ids=lambda path: path.name)
def test_phase1_case_contract_and_reference_patch(case_directory: Path, tmp_path: Path):
    case = json.loads((case_directory / "case.json").read_text())
    repository = tmp_path / "repository"
    import shutil

    shutil.copytree(case_directory / "repository", repository)
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
        cwd=repository,
        check=True,
    )

    applied = subprocess.run(
        ["git", "apply", "--unidiff-zero", str(case_directory / "expected.patch")],
        cwd=repository,
        text=True,
        capture_output=True,
        check=False,
    )

    assert applied.returncode == 0, applied.stderr
    changed = subprocess.run(
        ["git", "diff", "--name-only"], cwd=repository, text=True, capture_output=True, check=True
    ).stdout.splitlines()
    assert sorted(changed) == sorted(case["expected_changed_files"])
    for relative, expected_values in case["expected_content"].items():
        content = (repository / relative).read_text()
        assert all(value in content for value in expected_values)
