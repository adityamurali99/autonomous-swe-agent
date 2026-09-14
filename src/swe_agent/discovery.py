from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class CommandCandidate:
    priority: int
    command: str
    evidence: str


def discover_test_commands(root: Path) -> list[CommandCandidate]:
    candidates: list[CommandCandidate] = []
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            scripts = json.loads(package_json.read_text()).get("scripts", {})
            if "test" in scripts:
                runner = "npm"
                if (root / "pnpm-lock.yaml").exists():
                    runner = "pnpm"
                elif (root / "yarn.lock").exists():
                    runner = "yarn"
                command = f"{runner} test"
                candidates.append(CommandCandidate(10, command, "package.json#scripts.test"))
        except (OSError, json.JSONDecodeError):
            pass

    if any((root / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg")):
        candidates.append(CommandCandidate(20, "python -m pytest", "Python project/test config"))

    makefile = root / "Makefile"
    if makefile.is_file():
        try:
            if any(line.startswith("test:") for line in makefile.read_text().splitlines()):
                candidates.append(CommandCandidate(15, "make test", "Makefile test target"))
        except OSError:
            pass

    if (root / "mvnw").is_file():
        candidates.append(CommandCandidate(10, "./mvnw test", "Maven wrapper"))
    elif (root / "pom.xml").is_file():
        candidates.append(CommandCandidate(20, "mvn test", "pom.xml"))
    if (root / "gradlew").is_file():
        candidates.append(CommandCandidate(10, "./gradlew test", "Gradle wrapper"))
    elif any((root / name).is_file() for name in ("build.gradle", "build.gradle.kts")):
        candidates.append(CommandCandidate(20, "gradle test", "Gradle build file"))
    if (root / "CMakeLists.txt").is_file():
        candidates.append(CommandCandidate(30, "cmake --build build && ctest --test-dir build", "CMakeLists.txt"))

    return sorted(set(candidates))
