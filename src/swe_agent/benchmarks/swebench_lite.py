from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DATASET_NAME = "SWE-bench/SWE-bench_Lite"
DATASET_SPLIT = "test"
EXPECTED_TASKS = 300
DATASET_SERVER = "https://datasets-server.huggingface.co/rows"
AGENT_FIELDS = ("instance_id", "repo", "base_commit", "problem_statement", "version")
REQUIRED_EVALUATOR_FIELDS = (
    *AGENT_FIELDS,
    "patch",
    "test_patch",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
)


@dataclass(frozen=True)
class AgentTask:
    """The only SWE-bench fields permitted to reach the agent."""

    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    version: str


def fetch_official_tasks(page_size: int = 100) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for offset in range(0, EXPECTED_TASKS, page_size):
        query = urllib.parse.urlencode(
            {
                "dataset": DATASET_NAME,
                "config": "default",
                "split": DATASET_SPLIT,
                "offset": offset,
                "length": min(page_size, EXPECTED_TASKS - offset),
            }
        )
        with urllib.request.urlopen(f"{DATASET_SERVER}?{query}", timeout=60) as response:
            payload = json.load(response)
        tasks.extend(item["row"] for item in payload["rows"])
    validate_tasks(tasks)
    return tasks


def validate_tasks(tasks: list[dict[str, Any]]) -> None:
    if len(tasks) != EXPECTED_TASKS:
        raise ValueError(f"Expected {EXPECTED_TASKS} tasks, received {len(tasks)}")
    identifiers: set[str] = set()
    for task in tasks:
        missing = [field for field in REQUIRED_EVALUATOR_FIELDS if field not in task]
        if missing:
            raise ValueError(f"Task is missing evaluator fields: {', '.join(missing)}")
        identifier = str(task["instance_id"])
        if identifier in identifiers:
            raise ValueError(f"Duplicate task: {identifier}")
        identifiers.add(identifier)


def agent_view(task: dict[str, Any]) -> AgentTask:
    """Project evaluator data through an explicit allowlist."""
    return AgentTask(**{field: str(task[field]) for field in AGENT_FIELDS})


def diagnostic_tags(task: dict[str, Any]) -> list[str]:
    patch = str(task["patch"])
    changed_files = sum(line.startswith("diff --git ") for line in patch.splitlines())
    changed_lines = sum(
        line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        for line in patch.splitlines()
    )
    issue_chars = len(str(task["problem_statement"]))
    fail_to_pass = _test_count(task["FAIL_TO_PASS"])
    pass_to_pass = _test_count(task["PASS_TO_PASS"])
    return [
        "multi_file" if changed_files > 1 else "single_file",
        "large_patch" if changed_lines > 50 else "medium_patch" if changed_lines > 10 else "small_patch",
        "long_issue" if issue_chars > 4_000 else "short_issue" if issue_chars < 1_000 else "medium_issue",
        "weak_failure_signal" if fail_to_pass <= 1 else "multiple_failing_tests",
        "broad_regression" if pass_to_pass >= 20 else "focused_regression",
    ]


def select_diagnostic_tasks(tasks: list[dict[str, Any]], count: int, seed: str) -> list[dict[str, Any]]:
    """Greedily balance repositories and structural challenge tags."""
    if count > len(tasks):
        raise ValueError("Selection cannot be larger than the dataset")
    candidates = list(tasks)
    selected: list[dict[str, Any]] = []
    repo_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    while len(selected) < count:
        def score(task: dict[str, Any]) -> tuple[float, str]:
            tags = diagnostic_tags(task)
            diversity = sum(1 / (1 + tag_counts[tag]) for tag in tags)
            repository = 3 / (1 + repo_counts[str(task["repo"])])
            tie_breaker = hashlib.sha256(f"{seed}:{task['instance_id']}".encode()).hexdigest()
            return diversity + repository, tie_breaker

        chosen = max(candidates, key=score)
        candidates.remove(chosen)
        selected.append(chosen)
        repo_counts[str(chosen["repo"])] += 1
        tag_counts.update(diagnostic_tags(chosen))
    return selected


def build_manifest(tasks: Iterable[dict[str, Any]], name: str) -> dict[str, Any]:
    entries = [
        {
            "instance_id": task["instance_id"],
            "repo": task["repo"],
            "diagnostic_tags": diagnostic_tags(task),
        }
        for task in tasks
    ]
    return {
        "schema_version": 1,
        "name": name,
        "dataset": DATASET_NAME,
        "split": DATASET_SPLIT,
        "task_count": len(entries),
        "tasks": entries,
    }


def selection_summary(tasks: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = list(tasks)
    repositories = Counter(str(task["repo"]) for task in values)
    tags = Counter(tag for task in values for tag in diagnostic_tags(task))
    return {
        "task_count": len(values),
        "repository_count": len(repositories),
        "repositories": dict(sorted(repositories.items())),
        "diagnostic_tags": dict(sorted(tags.items())),
    }


def write_mirror(tasks: list[dict[str, Any]], root: Path) -> None:
    evaluator = root / "evaluator"
    agent = root / "agent"
    manifests = root / "manifests"
    for directory in (evaluator, agent, manifests):
        directory.mkdir(parents=True, exist_ok=True)
    _write_jsonl(evaluator / "tasks.jsonl", tasks)
    _write_jsonl(agent / "tasks.jsonl", (asdict(agent_view(task)) for task in tasks))
    diagnostic = select_diagnostic_tasks(tasks, 50, "diagnostic-50-v1")
    diagnostic_ids = {str(task["instance_id"]) for task in diagnostic}
    smoke_candidates = [task for task in tasks if str(task["instance_id"]) in diagnostic_ids]
    smoke = select_diagnostic_tasks(smoke_candidates, 10, "smoke-10-v1")
    _write_json(manifests / "diagnostic-50.json", build_manifest(diagnostic, "diagnostic-50"))
    _write_json(manifests / "smoke-10.json", build_manifest(smoke, "smoke-10"))
    _write_json(
        root / "selection-report.json",
        {
            "schema_version": 1,
            "full_mirror": selection_summary(tasks),
            "diagnostic_50": selection_summary(diagnostic),
            "smoke_10": selection_summary(smoke),
            "limitations": [
                "All SWE-bench Lite gold patches modify one production file.",
                "Structural tags describe gold patch and test shape, not semantic bug categories.",
            ],
        },
    )
    digest = hashlib.sha256((evaluator / "tasks.jsonl").read_bytes()).hexdigest()
    _write_json(
        root / "mirror-metadata.json",
        {
            "schema_version": 1,
            "dataset": DATASET_NAME,
            "split": DATASET_SPLIT,
            "task_count": len(tasks),
            "evaluator_tasks_sha256": digest,
            "agent_fields": list(AGENT_FIELDS),
        },
    )


def load_agent_tasks(path: Path) -> dict[str, AgentTask]:
    tasks: dict[str, AgentTask] = {}
    for line in path.read_text().splitlines():
        task = AgentTask(**json.loads(line))
        tasks[task.instance_id] = task
    return tasks


def _test_count(value: Any) -> int:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return 0 if not value else 1
    return len(value) if isinstance(value, list) else 0


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
