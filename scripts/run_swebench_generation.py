from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from swe_agent.agent import Agent
from swe_agent.benchmarks.swebench_lite import AgentTask, load_agent_tasks
from swe_agent.gemini_model import GeminiModel
from swe_agent.models import ResourceLimits
from swe_agent.observability import create_tracer
from swe_agent.trace import state_to_trace


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def ensure_repository(task: AgentTask, cache_root: Path) -> Path:
    repository = cache_root / task.repo.replace("/", "__")
    if not repository.is_dir():
        repository.parent.mkdir(parents=True, exist_ok=True)
        cloned = run(["git", "clone", "--filter=blob:none", f"https://github.com/{task.repo}.git", str(repository)])
        if cloned.returncode:
            raise RuntimeError(f"Clone failed for {task.repo}:\n{cloned.stderr}")
    present = run(["git", "cat-file", "-e", f"{task.base_commit}^{{commit}}"], repository)
    if present.returncode:
        fetched = run(["git", "fetch", "origin", task.base_commit], repository)
        if fetched.returncode:
            raise RuntimeError(f"Fetch failed for {task.instance_id}:\n{fetched.stderr}")
    return repository


def complete_result(output: Path) -> bool:
    required = (output / "trace.json", output / "patch.diff", output / "result.json")
    if not all(path.is_file() for path in required):
        return False
    try:
        json.loads((output / "trace.json").read_text())
        json.loads((output / "result.json").read_text())
    except json.JSONDecodeError:
        return False
    return True


def generate_task(
    task: AgentTask,
    *,
    repository_cache: Path,
    output: Path,
    model_name: str,
    max_steps: int,
    limits: ResourceLimits,
) -> dict[str, Any]:
    cached_repository = ensure_repository(task, repository_cache)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"swebench-{task.instance_id}-") as temporary:
        worktree = Path(temporary) / "repository"
        added = run(["git", "worktree", "add", "--detach", str(worktree), task.base_commit], cached_repository)
        if added.returncode:
            raise RuntimeError(f"Worktree checkout failed for {task.instance_id}:\n{added.stderr}")
        tracer = create_tracer()
        started = time.monotonic()
        try:
            state = Agent(
                GeminiModel(model_name, tracer=tracer),
                worktree,
                max_steps=max_steps,
                limits=limits,
                tracer=tracer,
            ).run(task.problem_statement)
        finally:
            tracer.flush()
        trace = state_to_trace(state)
        trace["repository"] = f"<worktree:{task.instance_id}>"
        trace["model"] = model_name
        patch = state.final_patch or ""
        result = {
            "schema_version": 1,
            "instance_id": task.instance_id,
            "repo": task.repo,
            "base_commit": task.base_commit,
            "model": model_name,
            "agent_status": state.status,
            "agent_completed": state.status == "completed",
            "benchmark_resolved": None,
            "benchmark_evaluation": "not_run",
            "runtime_seconds": round(time.monotonic() - started, 3),
            "steps": state.step,
            "usage": state.usage.__dict__,
            "patch_bytes": len(patch.encode()),
            "error": state.error,
        }
        (output / "trace.json").write_text(json.dumps(trace, indent=2) + "\n")
        (output / "patch.diff").write_text(patch)
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        removed = run(["git", "worktree", "remove", "--force", str(worktree)], cached_repository)
        if removed.returncode:
            raise RuntimeError(f"Could not remove temporary worktree:\n{removed.stderr}")
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate patches for a fixed SWE-bench Lite manifest")
    parser.add_argument("--manifest", type=Path, default=Path("evals/swebench_lite/manifests/smoke-10.json"))
    parser.add_argument("--agent-tasks", type=Path, default=Path("evals/swebench_lite/agent/tasks.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository-cache", type=Path, default=Path("work/swebench/repositories"))
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--max-runtime-seconds", type=float, default=1800)
    parser.add_argument("--max-total-tokens", type=int)
    parser.add_argument("--max-cost-usd", type=float)
    parser.add_argument("--redo-existing", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    tasks = load_agent_tasks(args.agent_tasks)
    requested_ids = [str(entry["instance_id"]) for entry in manifest["tasks"]]
    missing = [identifier for identifier in requested_ids if identifier not in tasks]
    if missing:
        raise ValueError(f"Manifest tasks missing from agent mirror: {', '.join(missing)}")

    results: list[dict[str, Any]] = []
    for index, identifier in enumerate(requested_ids, start=1):
        output = args.output / identifier
        print(f"[{index}/{len(requested_ids)}] {identifier}", flush=True)
        if complete_result(output) and not args.redo_existing:
            result = json.loads((output / "result.json").read_text())
            print("SKIP", flush=True)
        else:
            try:
                result = generate_task(
                    tasks[identifier],
                    repository_cache=args.repository_cache,
                    output=output,
                    model_name=args.model,
                    max_steps=args.max_steps,
                    limits=ResourceLimits(
                        max_runtime_seconds=args.max_runtime_seconds,
                        max_total_tokens=args.max_total_tokens,
                        max_cost_usd=args.max_cost_usd,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - preserve batch progress
                result = {
                    "schema_version": 1,
                    "instance_id": identifier,
                    "agent_completed": False,
                    "benchmark_resolved": None,
                    "benchmark_evaluation": "not_run",
                    "infrastructure_error": f"{type(exc).__name__}: {exc}",
                }
                output.mkdir(parents=True, exist_ok=True)
                (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print("COMPLETE" if result.get("agent_completed") else "FAILED", flush=True)
        results.append(result)

    predictions = [
        {
            "instance_id": result["instance_id"],
            "model_name_or_path": args.model,
            "model_patch": (args.output / result["instance_id"] / "patch.diff").read_text(),
        }
        for result in results
        if (args.output / result["instance_id"] / "patch.diff").is_file()
    ]
    (args.output / "predictions.jsonl").write_text(
        "".join(json.dumps(prediction) + "\n" for prediction in predictions)
    )
    summary = {
        "schema_version": 1,
        "manifest": str(args.manifest),
        "model": args.model,
        "total": len(results),
        "agent_completed": sum(bool(result.get("agent_completed")) for result in results),
        "officially_evaluated": 0,
        "resolved": None,
        "warning": "Agent completion is not a SWE-bench solve; run the official evaluator.",
        "results": results,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
