from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from difflib import unified_diff
from fnmatch import fnmatch
from pathlib import Path

from swe_agent.discovery import discover_test_commands
from swe_agent.execution import CommandExecutor, LocalCommandExecutor
from swe_agent.models import JsonObject, Observation

MAX_OUTPUT = 30_000
DEPENDENCY_FILE_PATTERNS = {
    "Cargo.lock", "Cargo.toml", "Gemfile", "Gemfile.lock", "Pipfile", "Pipfile.lock",
    "build.gradle", "build.gradle.kts", "go.mod", "go.sum", "gradle.lockfile", "package-lock.json",
    "package.json", "pnpm-lock.yaml", "poetry.lock", "pom.xml", "pyproject.toml", "uv.lock", "yarn.lock",
}


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
    def __init__(self, root: Path, *, executor: CommandExecutor | None = None) -> None:
        requested_root = root.resolve()
        if not requested_root.is_dir():
            raise ValueError(f"Repository does not exist: {root}")
        git_root = subprocess.run(
            ["git", "-C", str(requested_root), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
        if git_root.returncode != 0:
            raise ValueError(f"Not a Git repository: {root}")
        self.root = Path(git_root.stdout.strip()).resolve()
        self.executor = executor or LocalCommandExecutor()
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
            Tool("edit_file", "Replace exact text, or create a file when old_text is empty.", obj | {"properties": {
                "path": {"type": "string"}, "old_text": {"type": "string"},
                "new_text": {"type": "string"},
                "expected_replacements": {"type": "integer", "default": 1}},
                "required": ["path", "old_text", "new_text"]}, self._edit_file),
            Tool("run_command", "Run a build, diagnostic, or focused command in the repository. "
                 "Dependency files are restored unless changes are explicitly allowed with a reason.", obj | {
                "properties": {"command": {"type": "string"}, "timeout_seconds": {
                    "type": "integer", "default": 120}, "allow_dependency_changes": {
                    "type": "boolean", "default": False}, "dependency_change_reason": {
                    "type": "string"}}, "required": ["command"]}, self._run_command),
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
        if not path.exists():
            if old:
                return Observation(False, "Cannot replace text in a file that does not exist")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new)
            return Observation(
                True,
                f"Created {path.relative_to(self.root)}",
                {"path": str(path.relative_to(self.root)), "created": True},
            )
        content = path.read_text()
        if not old:
            return Observation(False, "old_text must be non-empty when editing an existing file")
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
        completed = self.executor.run(command, self.root, timeout)
        output, truncated = _bounded(completed.output)
        metadata: JsonObject = {
            "command": command,
            "exit_code": completed.returncode,
            "duration_seconds": completed.duration_seconds,
        }
        if completed.timed_out:
            metadata["timed_out"] = True
        return Observation(
            completed.returncode == 0 and not completed.timed_out,
            output,
            metadata,
            truncated,
        )

    def _run_command(self, args: JsonObject) -> Observation:
        allow_changes = bool(args.get("allow_dependency_changes", False))
        reason = str(args.get("dependency_change_reason", "")).strip()
        if allow_changes and not reason:
            return Observation(False, "dependency_change_reason is required when dependency changes are allowed")
        return self._guarded_process(
            str(args["command"]),
            int(args.get("timeout_seconds", 120)),
            allow_dependency_changes=allow_changes,
            dependency_change_reason=reason or None,
        )

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
        result = self._guarded_process(str(command), int(args.get("timeout_seconds", 300)))
        metadata = dict(result.metadata)
        metadata["candidates"] = [candidate.__dict__ for candidate in candidates]
        return Observation(result.success, result.output, metadata, result.truncated)

    def _guarded_process(
        self,
        command: str,
        timeout: int,
        *,
        allow_dependency_changes: bool = False,
        dependency_change_reason: str | None = None,
    ) -> Observation:
        before = self._dependency_snapshot()
        result = self._process(command, timeout)
        after = self._dependency_snapshot()
        changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
        metadata = dict(result.metadata)
        if not changed:
            return result
        metadata["dependency_files_changed"] = changed
        if allow_dependency_changes:
            metadata["dependency_change_reason"] = dependency_change_reason
            return Observation(result.success, result.output, metadata, result.truncated)

        for relative in changed:
            path = self._path(relative)
            if relative in before:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(before[relative])
            elif path.exists():
                path.unlink()
        metadata["dependency_changes_reverted"] = True
        message = result.output + ("\n" if result.output else "") + (
            "Command changed protected dependency files; changes were reverted: " + ", ".join(changed)
        )
        output, truncated = _bounded(message)
        return Observation(False, output, metadata, truncated)

    def _dependency_snapshot(self) -> dict[str, bytes]:
        ignored = {".git", ".venv", "__pycache__", "dist", "build", "node_modules", "venv"}
        snapshot: dict[str, bytes] = {}
        for current, directories, files in os.walk(self.root):
            directories[:] = [directory for directory in directories if directory not in ignored]
            for filename in files:
                if filename not in DEPENDENCY_FILE_PATTERNS and not fnmatch(filename, "requirements*.txt"):
                    continue
                path = Path(current) / filename
                if path.is_symlink():
                    continue
                snapshot[str(path.relative_to(self.root))] = path.read_bytes()
        return snapshot

    def _inspect_diff(self, args: JsonObject) -> Observation:
        del args
        output, untracked_files = self.working_tree_patch()
        output, truncated = _bounded(output)
        return Observation(True, output, {"untracked_files": untracked_files}, truncated)

    def working_tree_patch(self) -> tuple[str, list[str]]:
        """Return an unbounded patch for the repository's current working-tree state."""
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        if head.returncode == 0:
            base = "HEAD"
        else:
            empty_tree = subprocess.run(
                ["git", "mktree"],
                cwd=self.root,
                input="",
                text=True,
                capture_output=True,
                check=True,
            )
            base = empty_tree.stdout.strip()
        tracked = subprocess.run(
            ["git", "diff", base, "--no-ext-diff", "--"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
        )
        patches = [tracked.stdout]
        untracked_files = sorted(untracked.stdout.splitlines())
        for relative in untracked_files:
            path = self._path(relative)
            try:
                lines = path.read_text().splitlines(keepends=True)
            except UnicodeDecodeError:
                patches.append(f"Binary untracked file: {relative}\n")
                continue
            patches.append("".join(unified_diff([], lines, fromfile="/dev/null", tofile=f"b/{relative}")))
        return "".join(patches), untracked_files
