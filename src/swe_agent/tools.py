from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from swe_agent.discovery import discover_test_commands
from swe_agent.models import JsonObject, Observation

MAX_OUTPUT = 30_000


def _bounded(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT:
        return text, False
    half = MAX_OUTPUT // 2
    return text[:half] + "\n... output truncated ...\n" + text[-half:], True


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: JsonObject
    handler: Callable[[JsonObject], Observation]

    def schema(self) -> JsonObject:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": False,
        }


class RepositoryTools:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ValueError(f"Repository does not exist: {root}")
        self._tools = {tool.name: tool for tool in self._build_tools()}

    @property
    def schemas(self) -> list[JsonObject]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: JsonObject) -> Observation:
        tool = self._tools.get(name)
        if tool is None:
            return Observation(False, f"Unknown tool: {name}")
        try:
            return tool.handler(arguments)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            return Observation(False, f"{type(exc).__name__}: {exc}")

    def _path(self, raw: str = ".") -> Path:
        candidate = (self.root / raw).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"Path escapes repository: {raw}")
        return candidate

    def _build_tools(self) -> list[Tool]:
        obj = {"type": "object", "additionalProperties": False}
        return [
            Tool("list_files", "List repository files recursively.", obj | {"properties": {
                "path": {"type": "string", "default": "."},
                "max_depth": {"type": "integer", "default": 4}}, "required": []}, self._list_files),
            Tool("read_file", "Read a UTF-8 text file with line numbers.", obj | {"properties": {
                "path": {"type": "string"}, "start_line": {"type": "integer", "default": 1},
                "end_line": {"type": "integer"}}, "required": ["path"]}, self._read_file),
            Tool("search_code", "Search repository text using a literal query.", obj | {"properties": {
                "query": {"type": "string"}, "path": {"type": "string", "default": "."},
                "glob": {"type": "string"}}, "required": ["query"]}, self._search_code),
            Tool("edit_file", "Replace exact text in a repository file.", obj | {"properties": {
                "path": {"type": "string"}, "old_text": {"type": "string"},
                "new_text": {"type": "string"},
                "expected_replacements": {"type": "integer", "default": 1}},
                "required": ["path", "old_text", "new_text"]}, self._edit_file),
            Tool("run_command", "Run a build, diagnostic, or focused command in the repository.", obj | {
                "properties": {"command": {"type": "string"}, "timeout_seconds": {
                    "type": "integer", "default": 120}}, "required": ["command"]}, self._run_command),
            Tool("run_tests", "Run an explicit test command or the best conventionally discovered one.", obj | {
                "properties": {"command": {"type": "string"}, "timeout_seconds": {
                    "type": "integer", "default": 300}}, "required": []}, self._run_tests),
            Tool("inspect_diff", "Inspect the current Git working-tree diff.", obj | {
                "properties": {}, "required": []}, self._inspect_diff),
        ]

    def _list_files(self, args: JsonObject) -> Observation:
        base = self._path(str(args.get("path", ".")))
        max_depth = int(args.get("max_depth", 4))
        if max_depth < 0 or max_depth > 20:
            raise ValueError("max_depth must be between 0 and 20")
        ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
        files: list[str] = []
        for current, dirs, names in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in ignored)
            relative = Path(current).relative_to(base)
            if len(relative.parts) >= max_depth:
                dirs[:] = []
            files.extend(str((Path(current) / name).relative_to(self.root)) for name in sorted(names))
        output, truncated = _bounded("\n".join(files))
        return Observation(True, output, {"count": len(files)}, truncated)

    def _read_file(self, args: JsonObject) -> Observation:
        path = self._path(str(args["path"]))
        start = max(1, int(args.get("start_line", 1)))
        lines = path.read_text().splitlines()
        end = min(len(lines), int(args.get("end_line", start + 399)))
        rendered = "\n".join(f"{number:>6} | {lines[number - 1]}" for number in range(start, end + 1))
        output, truncated = _bounded(rendered)
        return Observation(True, output, {"path": str(path.relative_to(self.root)), "lines": [start, end]}, truncated)

    def _search_code(self, args: JsonObject) -> Observation:
        query = str(args["query"])
        base = self._path(str(args.get("path", ".")))
        command = ["rg", "--line-number", "--color", "never", "--fixed-strings", query, str(base)]
        if glob := args.get("glob"):
            command[1:1] = ["--glob", str(glob)]
        completed = subprocess.run(command, cwd=self.root, text=True, capture_output=True, check=False)
        text = completed.stdout or completed.stderr
        output, truncated = _bounded(text)
        return Observation(completed.returncode in (0, 1), output, {"matches": completed.returncode == 0}, truncated)

    def _edit_file(self, args: JsonObject) -> Observation:
        path = self._path(str(args["path"]))
        old = str(args["old_text"])
        new = str(args["new_text"])
        expected = int(args.get("expected_replacements", 1))
        content = path.read_text()
        actual = content.count(old)
        if actual != expected:
            return Observation(False, f"Expected {expected} replacements but found {actual}; file unchanged")
        path.write_text(content.replace(old, new))
        return Observation(
            True,
            f"Replaced {actual} occurrence(s) in {path.relative_to(self.root)}",
            {"path": str(path.relative_to(self.root))},
        )

    def _process(self, command: str, timeout: int) -> Observation:
        if timeout < 1 or timeout > 1800:
            raise ValueError("timeout_seconds must be between 1 and 1800")
        started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=self.root, shell=True, text=True,
                                       capture_output=True, timeout=timeout, check=False)
            combined = completed.stdout + completed.stderr
            output, truncated = _bounded(combined)
            return Observation(completed.returncode == 0, output, {
                "command": command, "exit_code": completed.returncode,
                "duration_seconds": round(time.monotonic() - started, 3)}, truncated)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            partial = stdout + stderr
            return Observation(False, str(partial), {"command": command, "timed_out": True})

    def _run_command(self, args: JsonObject) -> Observation:
        return self._process(str(args["command"]), int(args.get("timeout_seconds", 120)))

    def _run_tests(self, args: JsonObject) -> Observation:
        candidates = discover_test_commands(self.root)
        command = args.get("command")
        if command is None:
            if not candidates:
                return Observation(
                    False,
                    "No test command discovered; inspect repository documentation and provide command explicitly",
                    {"candidates": []},
                )
            command = candidates[0].command
        result = self._process(str(command), int(args.get("timeout_seconds", 300)))
        metadata = dict(result.metadata)
        metadata["candidates"] = [candidate.__dict__ for candidate in candidates]
        return Observation(result.success, result.output, metadata, result.truncated)

    def _inspect_diff(self, args: JsonObject) -> Observation:
        del args
        return self._process("git diff --no-ext-diff --", 60)
