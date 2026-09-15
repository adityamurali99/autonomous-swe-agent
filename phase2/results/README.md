# Initial realistic-case results

The four cases were frozen in commit `c819060` before running the unchanged agent with
`gemini-3.1-flash-lite`. Results are manually adjudicated from traces, patches, final working-tree
checks, and independent validation. Raw machine labels are retained only as run artifacts.

| Case | Result | Steps | Manual finding |
| --- | --- | ---: | --- |
| `python-config-precedence` | Functional, stale patch | 17 | Correct final source and passing behavioral probe, but returned patch still contains a temporary test deleted after `inspect_diff`. |
| `typescript-barrel-migration` | Clean success | 18 | Updated four production files, found the JS consumer outside `tsconfig`, preserved `normalizeUserId`, and passed full validation. |
| `typescript-manifest-trap` | Inconclusive | 0 | Isolated retry immediately hit the 500-request free-tier quota; no behavioral result. |
| `typescript-monorepo-validation` | Inconclusive | 3 | Inspected core source and tests, then hit the same provider quota before acting. |

## New failure exposed: stale final diff

In `python-config-precedence`, the agent:

1. observed that public tests passed;
2. created `reproduce_issue.py` through `run_command`;
3. reproduced the precedence failure;
4. fixed `app/config.py` and passed both test paths;
5. called `inspect_diff`, which included the temporary test;
6. deleted the temporary test with `run_command`; and
7. finished without another `inspect_diff`.

The final working tree correctly contains only `app/config.py`, so independent validation and
changed-file checks passed. However, the agent returns the most recent `inspect_diff` observation,
which still includes `reproduce_issue.py`. The completion gate invalidates diff state after
`edit_file`, but cannot detect filesystem mutations performed through `run_command`.

This is more serious than cosmetic inefficiency: the returned patch can disagree with the validated
working tree. The core should derive the final patch directly after the loop or require a fresh diff
after any potentially mutating command.

## Confirmed strength: broader repository search

The barrel migration was a strong result. The agent searched all `normalizeUser` references, updated
the implementation, barrel, TypeScript service, and CommonJS CLI, recovered from two rejected exact
edits, ran `npm test`, inspected the final four-file diff, and left the similarly named
`normalizeUserId` unchanged.

## Provider limitation

The free project reported `generate_content_free_tier_requests` with a limit of 500. Both remaining
cases ended in `model_error` after bounded retries. They must not be counted as agent failures. They
should be run after the quota resets, using the same frozen fixtures and model.
