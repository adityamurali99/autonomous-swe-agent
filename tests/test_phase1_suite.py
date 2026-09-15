from pathlib import Path

from swe_agent.evaluation import artifacts_complete


def test_artifacts_are_complete_only_when_every_required_file_exists(tmp_path: Path):
    assert not artifacts_complete(tmp_path)

    (tmp_path / "assessment.json").write_text("{}")
    (tmp_path / "trace.json").write_text("{}")
    (tmp_path / "actual.patch").write_text("")

    assert artifacts_complete(tmp_path)


def test_invalid_json_is_not_a_resumable_result(tmp_path: Path):
    (tmp_path / "assessment.json").write_text("not json")
    (tmp_path / "trace.json").write_text("{}")
    (tmp_path / "actual.patch").write_text("")

    assert not artifacts_complete(tmp_path)
