import json

from swe_agent.discovery import discover_test_commands


def test_prefers_repository_wrapper(tmp_path):
    (tmp_path / "pom.xml").write_text("<project />")
    (tmp_path / "mvnw").write_text("#!/bin/sh")
    candidates = discover_test_commands(tmp_path)
    assert candidates[0].command == "./mvnw test"


def test_discovers_package_manager_from_lockfile(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}}))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    candidates = discover_test_commands(tmp_path)
    assert candidates[0].command == "pnpm test"
