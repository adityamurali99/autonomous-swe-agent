# Phase 1 reliability cases

These cases test the V1 agent on small, fully inspectable repositories. They are intentionally
simple: Phase 1 asks whether the core loop can inspect, edit, recover, validate, and stop—not
whether it can solve benchmark-scale issues.

## What is reliable and what is variable

The model's exact tool sequence is **not** treated as an expected output. A correct agent may read
files in a different order or run a failing test before editing. Each run is instead assessed by
stable outcome criteria in `case.json`:

- terminal status is `completed`;
- an independent validation command passes after the agent stops;
- only the expected files changed; and
- expected content appears in the resulting files.

Every case also includes `expected.patch` as a human-readable reference. Equivalent patches are
allowed when they satisfy the case criteria.

## Inspecting a case

Each case directory contains:

- `case.json`: bug report and machine-checked expected outcome;
- `repository/`: exact clean starting repository;
- `expected.patch`: a minimal reference patch.

After a live run, `phase1/results/<case-id>/` contains:

- `trace.json`: every LLM-selected action and complete tool observation;
- `actual.patch`: the final patch returned by the agent;
- `assessment.json`: expected-versus-actual checks and independent validation output.

The API key is never written to these files.

## Running

From the project root, with `GEMINI_API_KEY` exported or present in the ignored `.env` file:

```bash
.venv/bin/python scripts/run_phase1_case.py phase1/cases/python-off-by-one
.venv/bin/python scripts/run_phase1_case.py phase1/cases/typescript-api-rename
.venv/bin/python scripts/run_phase1_suite.py
```

The suite command runs cases sequentially so free-tier rate limits are easier to diagnose. It does
not stop at the first failure and writes `phase1/results/suite-summary.json` after all cases finish.

Free-tier Gemini runs may pause at rate limits. Bounded retry behavior is expected and is not a
case failure. Each assessment records the exact model used; the default is `gemini-3.1-flash-lite`.
