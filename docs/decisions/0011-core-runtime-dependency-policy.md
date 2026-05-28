# 11. Core runtime dependency policy

Date: 2026-05-28

## Status

Accepted

## Context

The suite needs a dependency policy that supports audit-grade regulatory capital
calculation without making implementation and validation unnecessarily hard.
The current implementation uses `numpy` as the only runtime numerical
dependency for capital kernels. `scipy` is already used as a development/test
dependency for independent reference-vector checks.

Future modules will ingest tabular sensitivities, default-risk exposures,
residual-risk records, CVA exposures, rule profiles, and audit outputs. Tools
such as `pandas`, `polars`, `scipy`, and `statsmodels` could make exploratory
analysis, notebooks, validation, reconciliation, and adapter code easier to
write and debug. They also introduce runtime surface area, data-alignment
semantics, dependency churn, and security/SBOM obligations.

The decision is therefore not whether those libraries are useful. They are. The
decision is which layer is allowed to depend on them.

## Decision

Capital calculation kernels must remain `numpy`-native at runtime. Runtime
capital packages may depend on `numpy` and on shared suite packages such as
`frtb-common`. Adding `pandas`, `polars`, `scipy`, `statsmodels`, or another
third-party runtime dependency to a capital package requires a new ADR.

Richer libraries are allowed outside the core runtime path:

- `scipy` may be used in development and tests for independent statistical or
  numerical reference checks.
- `pandas` may be used in notebooks, validation workbooks, exploratory
  analysis, and optional ingestion/reconciliation adapters.
- `polars` may be used in notebooks, validation workbooks, exploratory
  analysis, and optional high-volume tabular adapters.
- `statsmodels` may be used in validation, research, and notebook workflows
  where statistical diagnostics are useful.

These libraries must not be imported by capital calculation kernels unless a
future ADR promotes the dependency into the runtime layer. Optional adapters
must normalize external or dataframe-shaped data into canonical typed package
inputs before calculation starts.

The intended layering is:

```text
notebooks / validation / optional adapters  ->  pandas, polars, scipy, statsmodels allowed
canonical package inputs and audit records  ->  frozen dataclasses, enums, hashes
capital calculation kernels                 ->  numpy arrays and pure functions
shared suite primitives                     ->  frtb-common
```

## Consequences

**Positive:**

- Core capital numbers remain traceable to explicit arrays, axes, typed inputs,
  and pure functions.
- The runtime SBOM and vulnerability surface stay small.
- Reproducibility is easier to audit across Python versions and CI matrices.
- Dataframe index alignment, nullable dtypes, implicit sorting, grouping
  semantics, and timezone handling cannot silently affect capital kernels.
- Notebooks, validation, tests, and adapters can still use the right tool for
  human inspection, reconciliation, and independent checks.

**Negative:**

- Kernel implementations may need more explicit axis metadata and validation
  than a labelled dataframe implementation would require.
- Developers must write adapter code between labelled tabular inputs and
  canonical typed inputs.
- Some algorithms available in `scipy` or `statsmodels` cannot be used in
  runtime kernels without an ADR.
- Optional adapter dependencies need packaging discipline so they do not leak
  into the core runtime installation.

## Guidance

Use `numpy` arrays for hot numerical paths and attach meaning through typed
containers, enums, axis labels, validation, and audit records. Use labelled
dataframes where they improve human debugging or ingestion, but convert them at
the package boundary.

If a future module cannot reasonably implement a required calculation without a
non-`numpy` runtime dependency, open a focused ADR that explains:

- the required calculation or adapter use case;
- why `numpy` plus local code is inferior;
- whether the dependency is runtime, optional extra, development, or notebook
  only;
- reproducibility and security impact;
- how canonical inputs, audit records, and deterministic tests remain intact.

## References

- [ADR 0001](0001-record-architecture-decisions.md): record architecture
  decisions.
- [ADR 0005](0005-material-change-policy.md): material change policy.
- Root `AGENTS.md` and `CLAUDE.md` workspace dependency guidance.
- `packages/frtb-ima` test suite reference-vector checks using `scipy` as a
  development dependency.
