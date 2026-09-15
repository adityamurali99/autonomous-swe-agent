# SWE-bench Lite evaluation runbook

This directory is a reproducible local mirror of the official 300-task SWE-bench Lite test split.
The benchmark consists of real Python repository issues. It is the primary real-world evaluation
set for this project; the small `phase1` and `phase2` fixtures are development diagnostics only.

Official references:

- Dataset: <https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite>
- Dataset fields: <https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/datasets.md>
- Evaluation harness: <https://github.com/SWE-bench/SWE-bench>

## Data isolation

The mirror deliberately has two views:

```text
agent/tasks.jsonl       # only task ID, repository, base commit, issue, and version
evaluator/tasks.jsonl   # official full records, including gold and test patches
manifests/smoke-10.json
manifests/diagnostic-50.json
mirror-metadata.json    # provenance, allowlist, and full-mirror checksum
selection-report.json   # auditable repository and structural-tag distributions
```

`scripts/run_swebench_generation.py` reads only `agent/tasks.jsonl`. Never include
`evaluator/tasks.jsonl`, `patch`, `test_patch`, `FAIL_TO_PASS`, or `PASS_TO_PASS` in an agent prompt.
The evaluator mirror is committed so evaluation is reproducible, but it must be treated as secret
from the solving agent.

The allowlist is enforced by the frozen `AgentTask` type and covered by an automated leakage test.

## Fixed subsets

`smoke-10` is a pipeline check across ten repositories. `diagnostic-50` is the first meaningful
baseline and contains the smoke tasks. Both are deterministic and fixed in source control.

The 50-task subset covers all 12 Lite repositories and balances:

- small, medium, and large gold patch sizes;
- short, medium, and long issue reports;
- one versus multiple fail-to-pass tests;
- focused versus broad pass-to-pass regression suites.

Important limitation: every SWE-bench Lite gold solution changes exactly one production file.
Lite can expose failures in large-repository localization, issue interpretation, reproduction,
implementation, test selection, recovery, and completion. It cannot measure multi-file patch
coordination. Do not report it as a comprehensive test of that ability.

The structural tags in manifests are evaluator-side selection metadata. They are not passed to the
agent and are not semantic labels for the issue.

## Rebuild and verify the mirror

From the repository root:

```bash
.venv/bin/python scripts/mirror_swebench_lite.py
.venv/bin/pytest -q tests/test_swebench_lite.py
git diff -- evals/swebench_lite
```

No diff means the upstream records and deterministic selection are unchanged. A changed checksum in
`mirror-metadata.json` requires review before committing because it changes benchmark comparability.

## Generate patches

Start with one smoke run:

```bash
.venv/bin/python scripts/run_swebench_generation.py \
  --manifest evals/swebench_lite/manifests/smoke-10.json \
  --output evals/runs/smoke-10-baseline
```

The runner caches one clone per upstream repository under ignored `work/swebench/repositories` and
creates a temporary detached worktree at each task's required base commit. Runs resume by default;
complete task artifacts are skipped. Use `--redo-existing` only when intentionally replacing a run.

For the 50-task baseline:

```bash
.venv/bin/python scripts/run_swebench_generation.py \
  --manifest evals/swebench_lite/manifests/diagnostic-50.json \
  --output evals/runs/diagnostic-50-baseline \
  --max-runtime-seconds 1800
```

Gemini usage limits are optional: `--max-total-tokens`, `--max-cost-usd`, and the agent's existing
step limit can bound each task. Langfuse is enabled automatically when its keys are present in the
ignored `.env` file.

## Inspect every model run

Each task directory contains:

```text
<instance-id>/trace.json   # exact model-visible history, tool calls, observations, usage
<instance-id>/patch.diff   # patch produced from the final validated working tree
<instance-id>/result.json  # status, runtime, tokens, cost, and grading status
```

The run root also contains:

```text
summary.json       # aggregate generation status and every per-task result
predictions.jsonl  # official SWE-bench prediction format
```

Inspect a task in this order:

1. Read `result.json` for terminal status, resources, and infrastructure errors.
2. Read `patch.diff` and compare it to the issue—not to the hidden gold patch.
3. Read `trace.json` chronologically to see every model decision and tool observation.
4. Confirm that the model reproduced the problem, localized relevant code, reacted to failures,
   ran meaningful tests after its final edit, and inspected the final patch.
5. Use the official evaluation result as the only solve decision.
6. Assign one primary failure code from `FAILURE_TAXONOMY.md` when unresolved.

`agent_completed: true` means only that the harness completion gate passed. It does **not** mean the
SWE-bench task was solved. Before official evaluation, `benchmark_resolved` is deliberately `null`.

## Official grading

The generated `predictions.jsonl` is compatible with the official SWE-bench harness. Official
grading requires Docker and task-specific images; this is the storage-intensive phase and is not
performed by the generation script.

Using a separate environment containing the official SWE-bench package, run:

```bash
python -m swebench.harness.run_evaluation \
  --dataset_name SWE-bench/SWE-bench_Lite \
  --split test \
  --predictions_path /absolute/path/to/evals/runs/smoke-10-baseline/predictions.jsonl \
  --max_workers 1 \
  --run_id smoke-10-baseline
```

Keep `--max_workers 1` initially to control disk pressure. Docker storage—not the 4.8 MB metadata
mirror—is responsible for the large storage estimate. A future harness milestone will import the
official report into each `result.json`; until then, retain the official report beside the run and
do not infer solve rate from agent completion.

## Comparing agent versions

Never mutate a baseline directory. Use a new run name for each material agent change, keep the model
and limits fixed, and compare the same manifest. Run the smoke set first, then the full 50. Two full
repetitions are useful only after the pipeline and quota are stable.

The evaluation loop is:

1. Establish the baseline.
2. Officially grade it.
3. Manually classify unresolved traces.
4. Count recurring primary failure modes.
5. Implement one targeted agent change.
6. Rerun the same fixed set and compare solve rate, failure counts, runtime, tokens, and cost.
