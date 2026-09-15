from pathlib import Path

from swe_agent.execution import LocalCommandExecutor


def test_local_executor_times_out_process_group(tmp_path: Path):
    result = LocalCommandExecutor().run("sleep 10 & wait", tmp_path, 1)

    assert result.timed_out
    assert result.returncode is not None
    assert result.duration_seconds < 3
