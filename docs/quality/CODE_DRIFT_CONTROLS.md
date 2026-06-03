# Code drift controls

This repository uses a baseline-gated drift guard to keep agent-generated code
growth, duplicate code, duplicate tests, and dead changed code visible in
review.

The guard is intentionally mechanical. It does not prove that a change is bad.
During the initial calibration period, the new drift, test-value, and dead-code
guards run in `quality-control` as report-only artifact producers. Their
individual Make targets remain blocking so maintainers can dry-run them against
recent PRs and promote the low-noise subset later.

The repository also has a changed-code complexity guard. It compares the working
tree to the merge base with `origin/main` and fails only on newly changed Python
files/functions that introduce avoidable complexity.

A changed-test value guard applies the same idea to tests. It checks only
changed and untracked test files and fixture-like files, so existing historical
tests do not block incremental improvement.

A changed-code dead-code guard checks high-confidence unused additions. It
looks only at changed runtime/script files, but counts references from runtime
code and tests.

## What It Checks

`scripts/ci/check_code_drift.py` scans Python files under `packages/`,
`scripts/`, and `tests/` and records:

- logical Python LOC by role (`source`, `test`, `script`, `other`);
- exact duplicate function bodies above the configured line threshold;
- oversized Python files;
- large functions;
- drift markers such as `TODO`, `FIXME`, `placeholder`, `temporary`,
  transitional assumption wording, unsupported-feature placeholders, and
  AI-attribution markers.

The versioned baseline lives at:

```text
docs/quality/code_drift_baseline.json
```

`scripts/ci/check_code_drift.py --changed` checks only changed Python files and
flags:

- changed files whose logical LOC growth exceeds the role-specific budget;
- changed functions that become larger than the configured function-size limit;
- already-large changed functions that grow beyond the changed-function budget.

`scripts/ci/check_test_value.py` checks changed tests and flags:

- changed test functions with no `assert`, `pytest.raises`, or assertion-helper
  call;
- exact duplicate changed test bodies;
- changed test files whose logical LOC growth exceeds the test budget;
- fixture, golden, or snapshot files whose byte growth exceeds the fixture
  budget.

`scripts/ci/check_dead_code.py` checks changed code and flags:

- changed private functions, methods, or classes with no references outside
  their own body;
- new runtime package modules under `packages/*/src` that are not imported or
  exposed by another Python module.

## When It Runs

Local:

```bash
make drift-check
make changed-code-check
make test-value-check
make dead-code-check
make quality-control
```

The repo-managed `pre-commit` and `pre-push` hooks also run drift-control
signals. `pre-commit` is intentionally light: it runs only the
worktree guard and changed-code complexity guard. `pre-push` keeps the same
blocking changed-code complexity guard and runs the broader drift, test-value,
and dead-code checks as report-only warnings during calibration.
Install hooks once per local clone:

```bash
make agent-setup
```

CI:

- `make quality-control` includes `drift-reports`;
- `drift-reports` writes the same JSON artifacts as the blocking checks but
  does not fail the job while these heuristics are being calibrated;
- the `quality-control` GitHub Actions job runs on pull requests, pushes to
  `main`, manual dispatch, and the weekly scheduled CI run;
- CI uploads `dist/quality/code-drift-report.json` and
  `dist/quality/changed-code-report.json`, plus
  `dist/quality/test-value-report.json` and
  `dist/quality/dead-code-report.json`, as the `code-drift` artifact.

## Failure Policy

Prefer simplifying the change over expanding the baseline. A baseline update is
appropriate only when the growth is intentional, reviewable, and consistent with
package boundaries. Baseline entries for large functions are keyed by
`path:name`, not by line number, so unrelated line movement does not create a
new finding.

Run this after simplification and include the baseline diff in the PR:

```bash
make drift-baseline
make drift-check
```

Reviewers should treat a baseline update as a request for a larger code budget,
not as generated evidence to rubber-stamp. In particular, inspect increases in:

- `duplicate_function_groups`;
- `duplicate_function_instances`;
- `large_function_count`;
- `drift_marker_matches`;
- any new path under `oversized_files` or `large_functions`.

## Relationship To Simplification Audits

The drift guard blocks incremental worsening. It does not replace the broader
simplification audit rubric in
[`docs/quality/simplification/rubric.md`](simplification/rubric.md), which is
still the process for deciding whether code should be consolidated inside a
package or moved to `frtb-common`.

`scripts/ci/check_simplification_drift.py` owns wrapper-specific patterns,
including low-value helper layers and stale forwarding adapters. The code-drift
guard owns generic size, duplication, baseline, and changed-code complexity
budgets and intentionally does not re-flag wrapper functions.
