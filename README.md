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
export OPENAI_API_KEY=...
autonomous-swe-agent /path/to/git/repository "Fix the off-by-one error in pagination"
```

The agent operates directly on the supplied working tree. Use a disposable branch or worktree.
Commands execute locally with the same permissions as the CLI process.

## Validate this project

```bash
pytest
ruff check .
mypy src
```
