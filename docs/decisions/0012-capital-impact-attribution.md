# 12. Capital impact and attribution readiness

Date: 2026-05-29

## Status

Accepted

## Context

The suite will need to explain how changes in positions, model inputs, rule
profiles, and aggregation choices affect capital. This is useful for portfolio
control, regression review, validation, and future notebooks. The external DRC
reference implementation includes an analytical Euler decomposition, which is a
useful design signal, but it is not a regulatory source for this suite.

The first capital implementations must stay focused on correct, cited capital
mechanics. At the same time, adding attribution later will be expensive if
capital kernels discard lineage, branch choices, or intermediate aggregation
state.

## Decision

Capital packages must be designed to be attribution-ready from their first
capital-producing slice. Attribution and impact assessment are first-class
application capabilities, but they remain separate from the capital calculation
kernels.

Each package owns package-specific attribution methods for its capital formulae.
Where a capital measure is differentiable and positively homogeneous over a
stable branch, analytical Euler contribution is the preferred method:

```text
contribution_i = exposure_i * dK / dexposure_i
```

Where floors, caps, max/min branches, bucket moves, eligibility switches, or
unsupported paths make analytical Euler inappropriate, the package must expose
the method as unsupported for that branch or use an explicitly labelled
fallback such as finite-difference impact.

The intended layering is:

```text
canonical inputs and rule profile
    -> capital kernels
    -> deterministic capital result and audit graph
    -> attribution module: analytical Euler, finite-difference, or unsupported
    -> impact module: baseline-vs-candidate capital deltas
    -> orchestration and reporting
```

Core capital APIs do not need to return attribution records in the first slice,
but they must preserve enough deterministic audit data to add them without
changing the capital number or reworking the public result graph.

## Required Design Hooks

Capital-producing packages must preserve:

- stable source ids from input records through intermediate and final results;
- deterministic group ids for netting sets, buckets, categories, desks, legal
  entities, and other aggregation levels;
- intermediate totals needed to recompute local derivatives;
- branch metadata for floors, caps, max/min choices, zero denominators, and
  unsupported features;
- explicit method labels for future attribution outputs, such as
  `analytical_euler`, `finite_difference`, and `unsupported`;
- reconciliation fields that show whether contributions sum to capital and, if
  not, the residual and reason.

Suite-level shared abstractions may move into `frtb-common` later under a
separate ADR once at least two capital packages have implemented compatible
records.

## Consequences

**Positive:**

- Future impact analysis can be added without redesigning calculation results.
- Reviewers can trace a contribution back to the exact capital branch and input
  lineage that produced it.
- Packages can choose the right attribution method for their own formulae while
  exposing a consistent suite-level shape.
- Finite-difference impact and analytical attribution are kept distinct, which
  avoids presenting scenario deltas as marginal decomposition.

**Negative:**

- First-pass capital records need more ids and intermediate audit fields.
- Some formula branches will require explicit unsupported attribution states
  until tested.
- Exact Euler reconciliation will not be possible for every branch, especially
  where a change moves an exposure across buckets or eligibility states.

## Guidance

Do not mix attribution math into the capital kernel. The kernel should compute
the capital result and audit graph. Attribution modules should consume that
graph and produce contribution records.

For every package, test attribution separately from capital. Attribution tests
must include reconciliation, zero-exposure behavior, branch changes, and
unsupported-method reporting. Capital tests remain authoritative for the
capital number itself.

Regulatory citations still attach to the capital mechanics. Attribution method
documentation should cite methodology sources or internal ADRs where needed,
but should not be used as a substitute for paragraph-level regulatory
citations on the underlying capital formula.

## References

- [ADR 0001](0001-record-architecture-decisions.md): record architecture
  decisions.
- [ADR 0011](0011-core-runtime-dependency-policy.md): runtime dependency
  policy for capital kernels and optional analysis layers.
- `docs/modules/frtb-drc/ARCHITECTURE_AND_DATA_DESIGN.md`: DRC lineage,
  impact, and attribution hooks.
