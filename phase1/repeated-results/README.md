# Two-repeat reliability check

This directory records two additional runs of each Phase 1 case using
`gemini-3.1-flash-lite`. Combined with the original baseline, this gives three independent
observations per case and 30 observations total.

The raw `passed` fields are retained for reproducibility but are not used as the conclusion. Each
patch and trace was manually inspected because the initial source-string checks reject equivalent
implementations.

| Case | Original | Repeat 1 | Repeat 2 | Manual result |
| --- | --- | --- | --- | --- |
| `python-clamp-boundary` | Clean | Clean | Clean | 3/3 clean |
| `python-csv-whitespace` | Clean | Clean | Clean | 3/3 clean |
| `python-makefile-discovery` | Clean | Clean | Clean | 3/3 clean |
| `python-missing-slugify` | Clean | Clean | Clean | 3/3 clean |
| `python-off-by-one` | Clean | Clean | Clean | 3/3 clean |
| `typescript-api-rename` | Clean | Clean | Clean | 3/3 clean |
| `typescript-async-return` | Extra manifests | Clean | Extra manifests | 1/3 clean; 3/3 functional |
| `typescript-falsy-default` | No edit | Clean | No edit | 1/3 clean |
| `typescript-prefix-check` | Clean | Clean | Clean | 3/3 clean |
| `typescript-signature-update` | No edit | Clean | Clean | 2/3 clean |

Overall, 25/30 observations produced clean task-compliant patches. The requested behavior was
implemented in 27/30 observations. These numbers describe this small sample only; they are not a
general benchmark score.

## Repeated findings

- The async case caused unrelated `package.json` and `package-lock.json` changes in 2/3 runs because
  the agent installed `@types/node` for an ad hoc test. Patch-scope discipline is a repeatable issue.
- Tasks whose existing validation already passed ended without an edit in 3/6 combined observations:
  falsy-default failed twice and signature-update once. This condition deserves targeted testing in
  the realistic set.
- The six straightforward cases were clean in every run. Repository test discovery, ordinary
  one-file fixes, and a coordinated two-file API rename were stable in this sample.
- `run_command` was frequently used for test commands before the completion gate required a later
  `run_tests` call. This consistently adds steps but did not corrupt outcomes.

The incomplete third repetition was stopped at the user's request and is intentionally not included.
