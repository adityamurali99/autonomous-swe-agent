from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    output: str
    duration_seconds: float
    timed_out: bool = False


class CommandExecutor(Protocol):
    """Execution boundary for repository commands."""

    def run(self, command: str, cwd: Path, timeout_seconds: int) -> CommandResult: ...


class LocalCommandExecutor:
    """Execute commands locally and terminate their process group on timeout."""

    def run(self, command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            output, _ = process.communicate(timeout=timeout_seconds)
            return CommandResult(
                process.returncode,
                output,
                round(time.monotonic() - started, 3),
            )
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            output, _ = process.communicate()
            return CommandResult(
                process.returncode,
                output,
                round(time.monotonic() - started, 3),
                timed_out=True,
            )
