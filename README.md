# Autonomous SWE Agent

Autonomous SWE Agent is a deliberately small autonomous software-engineering agent. Given a local Git
repository and a task, it lets a model inspect files, search code, edit files, run commands and
tests, inspect failures, and finish only after validation and diff inspection.

The first version optimizes for a legible agent loop and replaceable boundaries, not framework
features. See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and milestone definition.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export GEMINI_API_KEY=...
autonomous-swe-agent /path/to/git/repository "Fix the off-by-one error in pagination"
```

For local development, the CLI also reads `GEMINI_API_KEY` from an ignored `.env` file in the
current working directory. The default model is `gemini-3.1-flash-lite`, selected for its free-tier
throughput and agentic tool-use focus.

## Inspect runs in Langfuse

Langfuse tracing is optional. Add the following credentials to the same ignored `.env` file:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Use `https://us.cloud.langfuse.com` instead when the Langfuse project is in the US region. With
both keys present, each CLI run records a parent agent trace and a nested generation for every
Gemini decision. The generation includes the selected model context, tool schemas, selected tool,
arguments, latency, and provider errors. The CLI reports `"langfuse_tracing": true` when enabled
and flushes pending events before exiting.

Tracing intentionally includes repository paths, task text, selected file contents, command
outputs, and diffs because those values are part of the model context. Do not enable it for a
repository whose contents must not be sent to your configured Langfuse service.

The local JSON trace always retains the complete action/observation trajectory. The model receives
a separate bounded view that prioritizes recent work, failures, edits, diffs, and the newest window
read from each file. A derived progress summary redirects the model after repeated reproduction
work without a production-code change.

The agent operates directly on the supplied working tree. Use a disposable branch or worktree.
Commands execute locally with the same permissions as the CLI process.

When the model requests completion, the system reruns the last successful test command, rejects
validation that changes the working tree, and generates the returned patch fresh from the final Git
state. The final patch includes staged, unstaged, and untracked changes.

Commands also protect dependency manifests and lockfiles from incidental mutation. If a task
explicitly requires dependency changes, the model must opt in through `run_command` and record its
reason; otherwise those file changes are restored and the command returns a failed observation.

Each run reports wall-clock runtime, model request count, token usage, and estimated cost in both
the CLI result and JSON trace. Cost rates default to zero for the free-tier setup; pass
`--input-cost-per-million` and `--output-cost-per-million` when using paid pricing. Optional
`--max-runtime-seconds`, `--max-total-tokens`, and `--max-cost-usd` limits stop a run before its next
model decision once a budget is reached.

Repository commands run through a small execution interface. The default local executor kills the
whole spawned process group on timeout; a later isolated executor can replace it without changing
the agent or tools. Documented evaluation suites resume by default from complete per-case artifacts.
Use `python scripts/run_phase1_suite.py --redo-existing` to intentionally rerun every case.

## Real-world Python evaluation

The repository includes a reproducible mirror of all 300 SWE-bench Lite tasks, strict separation
between agent-visible issues and evaluator-only gold data, and fixed 10- and 50-task subsets. See
[`evals/swebench_lite/README.md`](evals/swebench_lite/README.md) for the complete generation,
inspection, official grading, and comparison workflow.

## Validate this project

```bash
pytest
ruff check .
mypy src
```
