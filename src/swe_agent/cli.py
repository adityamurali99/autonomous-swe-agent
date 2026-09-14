from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from swe_agent.agent import Agent
from swe_agent.gemini_model import GeminiModel
from swe_agent.models import ToolCall


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an autonomous coding agent on a local repository")
    parser.add_argument("repository", type=Path)
    parser.add_argument("task")
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")

    state = Agent(GeminiModel(args.model), args.repository, max_steps=args.max_steps).run(args.task)
    diff = ""
    for event in reversed(state.events):
        if isinstance(event.action, ToolCall) and event.action.name == "inspect_diff":
            diff = event.observation.output
            break
    print(json.dumps({"status": state.status, "steps": state.step, "summary": state.summary,
                      "validation_succeeded": state.validation_succeeded,
                      "diff_inspected": state.diff_inspected, "diff": diff}, indent=2))
    if state.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
