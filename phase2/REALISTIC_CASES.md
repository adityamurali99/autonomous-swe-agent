# Realistic core-agent case design

The next set should test repository reasoning rather than isolated syntax corrections. Each fixture
should contain roughly 8–20 source files, 2–4 relevant files, realistic configuration, and plausible
decoys. The agent receives only the repository and bug report. Results are judged manually from the
trace, patch, and normal repository validation output.

## Case construction rules

- Use normal project layouts and existing build tooling; do not add dependencies during case setup
  unless they are committed in a lockfile.
- Include incomplete public tests in selected cases so passing tests cannot substitute for satisfying
  the task description.
- Include unrelated but similarly named code so search and context selection matter.
- Require the smallest correct patch and identify files that must not change, especially manifests,
  generated output, fixtures, and tests.
- Ensure the requested behavior can be checked manually with a concrete example, even when existing
  tests do not cover it.
- Keep each repository small enough that a human can inspect the complete run in several minutes.

## Proposed cases

### 1. Python configuration precedence

A service loads defaults, a config file, and environment overrides across separate modules. An
environment value is incorrectly overwritten by the file value. Existing tests cover defaults and
file loading but not precedence. The correct patch changes merge order in one implementation module;
tests and sample configuration must remain untouched.

Exposes: task adherence with green tests, multi-file tracing, misleading nearby helpers.

### 2. TypeScript barrel-export API migration

Rename a public function used through an `index.ts` barrel, an internal consumer, and a CLI adapter.
One similarly named legacy function must remain unchanged. Type checking reveals only some missed
references because a JavaScript consumer is outside `tsconfig`.

Exposes: repository-wide search, API boundaries, selective multi-file edits.

### 3. Python cache invalidation

A repository layer updates a record but leaves a service-layer cache stale. Reads, writes, and cache
keys live in different modules. Public tests cover uncached behavior. The patch must invalidate only
the affected key and must not disable caching globally.

Exposes: causal reasoning across modules, incomplete tests, resistance to broad workarounds.

### 4. TypeScript pagination boundary

An API client combines cursor calculation, response parsing, and a paginator. The final full page
causes one unnecessary request because continuation is inferred from item count instead of the
server's nullable cursor. A similarly named offset paginator is unrelated.

Exposes: protocol reasoning, decoy code, boundary behavior across files.

### 5. Python exception translation

A client library should convert one transport timeout into a domain-specific exception while
preserving its cause. Several broad exception handlers exist nearby. Tests cover the domain error
type but not exception chaining or non-timeout propagation.

Exposes: precise error handling, hidden behavioral requirements, avoiding over-catching.

### 6. TypeScript manifest trap

A runtime bug can be reproduced with tools already present in the lockfile, but an obvious online
example suggests installing a new package. The correct implementation is a two-line source change.
`package.json`, the lockfile, tests, and generated directories must not change.

Exposes: the observed dependency-pollution failure and patch-scope review.

### 7. Python generated-client boundary

Generated API models contain the visible symptom, but repository documentation states that generated
files must not be edited. The source schema and a hand-written adapter reveal that only the adapter is
wrong. Regeneration is intentionally expensive and unnecessary.

Exposes: instruction discovery, generated-file avoidance, selecting the correct abstraction layer.

### 8. TypeScript monorepo validation discovery

A small workspace contains `packages/core`, `packages/cli`, and an unrelated web package. The bug
crosses core and CLI, while the root test command is slow and the package scripts provide targeted
validation. The correct patch updates two packages without touching workspace configuration.

Exposes: build discovery, scoped commands, cross-package dependencies, context control.

### 9. Python backward-compatible parser change

A parser must accept a new optional field without changing output for older inputs. Parsing,
normalization, and serialization are separate. A tempting change to the shared normalization helper
would alter unrelated fields.

Exposes: backward compatibility, regression avoidance, choosing a narrow edit location.

### 10. TypeScript stale derived state

A state reducer updates an entity but fails to update a derived lookup map used by another module.
Rebuilding all state would pass tests but violates identity guarantees documented in comments. The
minimal patch updates both structures immutably.

Exposes: invariant reasoning, documentation as evidence, avoiding brute-force fixes.

## Manual review checklist

For every run, inspect whether the agent:

1. Found repository instructions and the relevant build/test entry points.
2. Read enough related code to explain the defect without loading the entire repository.
3. Implemented the behavior described in the bug report, including requirements absent from tests.
4. Avoided unrelated source, test, dependency, lockfile, generated-file, and formatting changes.
5. Used failure output to revise its approach rather than repeating equivalent actions.
6. Ran appropriate validation after the final edit and inspected the final diff.
7. Returned a concise explanation consistent with the actual patch and validation.

The initial implementation should build cases 1, 2, 6, and 8 first. Together they directly exercise
the two repeated weaknesses while covering both languages and realistic multi-file/build discovery.
