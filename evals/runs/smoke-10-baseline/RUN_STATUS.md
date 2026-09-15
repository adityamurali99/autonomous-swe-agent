# Smoke-10 baseline status

Status: **blocked by provider availability; not an evaluation result**

The run started on 2026-09-14 with:

```bash
.venv/bin/python scripts/run_swebench_generation.py \
  --manifest evals/swebench_lite/manifests/smoke-10.json \
  --output evals/runs/smoke-10-baseline \
  --max-runtime-seconds 1800
```

The first attempt was blocked by the account-wide free-tier allowance of 500 requests. It was
retried on 2026-09-15 after quota became available. Gemini then intermittently accepted requests but
returned HTTP 500 because `gemini-3.1-flash-lite` was experiencing high demand.

`pytest-dev__pytest-7490` reached six agent steps before the 500 response. It created focused
reproduction files and invoked pytest, but it never localized or edited the implementation and
produced no patch. `sympy__sympy-19254` reached four steps, searched for the relevant polynomial
functions, and read `sympy/polys/factortools.py`; it also produced no patch before the same provider
error. These are provider-blocked partial trajectories, not coding outcomes.

The adapter was updated with bounded retries for transient HTTP 5xx responses. A subsequent retry
still remained blocked inside the provider request for several minutes and was interrupted. The
remaining eight tasks were not attempted. Repository checkout succeeded, cached clones remain under
the ignored `work/swebench/repositories` directory, and temporary worktree metadata was pruned.

Do not include this run in solve-rate or behavioral analysis. Resume the same command after quota is
available. Existing provider-failure artifacts will be skipped unless `--redo-existing` is supplied,
so use that flag before treating this directory as a real baseline.
