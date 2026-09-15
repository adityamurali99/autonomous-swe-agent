# Smoke-10 baseline status

Status: **blocked by provider quota; not an evaluation result**

The run started on 2026-09-14 with:

```bash
.venv/bin/python scripts/run_swebench_generation.py \
  --manifest evals/swebench_lite/manifests/smoke-10.json \
  --output evals/runs/smoke-10-baseline \
  --max-runtime-seconds 1800
```

The first task, `pytest-dev__pytest-7490`, completed one model decision (`list_files`) and then the
Gemini API returned HTTP 429 because the account-wide free-tier allowance of 500 requests was
exhausted. The adapter retried four times, so the recorded usage is five provider requests, 6,034
input tokens, 16 output tokens, and 6,050 total tokens. No patch was produced.

The second task was interrupted once the same account-level quota response appeared. Remaining
tasks were not attempted. Repository checkout succeeded, and cached clones remain under the ignored
`work/swebench/repositories` directory. Temporary worktree metadata was pruned after interruption.

Do not include this run in solve-rate or behavioral analysis. Resume the same command after quota is
available; the completed first task will be skipped unless `--redo-existing` is supplied. Because
its stored result is a provider failure, rerun that task intentionally before treating the directory
as a real baseline.
