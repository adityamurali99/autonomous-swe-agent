from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from swe_agent.agent import Agent
from swe_agent.gemini_model import GeminiModel
from swe_agent.models import AgentState
from swe_agent.observability import create_tracer
from swe_agent.trace import write_trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an autonomous coding agent on a local repository")
    parser.add_argument("repository", type=Path)
    parser.add_argument("task")
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--trace-file", type=Path)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")

    tracer = create_tracer()
    try:
        state = Agent(
            GeminiModel(args.model, tracer=tracer),
            args.repository,
            max_steps=args.max_steps,
            allow_dirty=args.allow_dirty,
            tracer=tracer,
        ).run(args.task)
    except ValueError as exc:
        state = AgentState(args.repository.resolve(), args.task, args.max_steps)
        state.status = "setup_error"
        state.error = f"{type(exc).__name__}: {exc}"
    finally:
        tracer.flush()
    if args.trace_file:
        write_trace(state, args.trace_file)
    print(json.dumps({"status": state.status, "steps": state.step, "summary": state.summary,
                      "error": state.error,
                      "validation_succeeded": state.validation_succeeded,
                      "diff_inspected": state.diff_inspected, "diff": state.final_patch or "",
                      "langfuse_tracing": tracer.enabled}, indent=2))
    if state.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
