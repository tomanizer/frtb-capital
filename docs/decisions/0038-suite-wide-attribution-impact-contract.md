# 38. Suite-wide attribution and impact contract

Date: 2026-06-03

## Status

Proposed

## Context

ADR 0012 established attribution-readiness design hooks, ADR 0031 defined the
DRC attribution method contract, and ADR 0037 defined a unified
`CapitalContribution` dataclass in `frtb-common`. Several gaps remain before
package-specific attribution work in SBM, CVA, and orchestration can proceed:

1. **No shared impact contract.** `CvaCapitalImpact` in `frtb-cva` and the
   SBM impact placeholder each define their own baseline-vs-candidate delta
   type. There is no package-neutral contract for cross-run capital impact.

2. **Incomplete contribution record fields.** The shared `CapitalContribution`
   lacks `citations`, `input_hash`, `profile_hash`, and
   `reconciliation_status`, all required for full audit traceability.

3. **Implicit method-selection rules.** The conditions under which a package
   must use `ANALYTICAL_EULER`, may use `FINITE_DIFFERENCE` impact, or must
   emit `RESIDUAL` / `UNSUPPORTED` records are not formally defined.

4. **No orchestration aggregation contract.** The suite lacks a definition of
   how `frtb-orchestration` re-exposes component contribution records at the
   top-of-house level without altering the underlying capital numbers.

5. **No package-neutral contract tests.** There are no tests in `frtb-common`
   that verify a component contribution projection satisfies the shared shape,
   independent of any capital-component import.

Issue AUDIT-IMP-002 (issue #503) requires all five gaps to be resolved before
package-specific attribution work proceeds.

## Decision

### 1. Extend `CapitalContribution` with audit fields

Four fields with defaults are added to
`frtb_common.attribution.CapitalContribution`. All defaults are empty / unknown
so existing callers are unaffected:

```python
@dataclass(frozen=True)
class CapitalContribution:
    # --- existing fields (unchanged) ---
    contribution_id: str
    source_id: str
    source_level: str
    bucket_key: str | None
    category: str
    base_amount: float
    marginal_multiplier: float | None
    contribution: float | None
    method: AttributionMethod | str
    residual: float = 0.0
    reason: str = ""
    # --- new audit fields ---
    citations: tuple[str, ...] = ()
    input_hash: str = ""
    profile_hash: str = ""
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.UNKNOWN
```

A new `ReconciliationStatus` `StrEnum` is added to the same module:

```python
class ReconciliationStatus(StrEnum):
    RECONCILED       = "RECONCILED"        # sum of contributions == capital ± ε
    PARTIAL_RESIDUAL = "PARTIAL_RESIDUAL"  # residual > 0 but explicitly labelled
    UNRECONCILED     = "UNRECONCILED"      # contributions do not sum; needs investigation
    UNKNOWN          = "UNKNOWN"           # not yet evaluated
```

The reconciliation tolerance is `ε = 1e-6` (relative to the total capital
charge). This matches the tolerance used in existing DRC and CVA reconciliation
validators.

### 2. Shared `CapitalImpact` dataclass

A new `frtb_common.impact` module defines the package-neutral impact type:

```python
class ImpactMethod(StrEnum):
    FINITE_DIFFERENCE = "FINITE_DIFFERENCE"
    ANALYTICAL        = "ANALYTICAL"

@dataclass(frozen=True)
class CapitalImpact:
    """Baseline-vs-candidate capital delta. Package-neutral."""

    baseline_run_id:       str
    candidate_run_id:      str
    component:             str   # package label, e.g. "frtb_sbm", "frtb_cva"
    baseline_total:        float
    candidate_total:       float
    delta:                 float  # always candidate_total - baseline_total
    method:                ImpactMethod | str
    baseline_input_hash:   str
    candidate_input_hash:  str
    baseline_profile_hash: str = ""
    candidate_profile_hash: str = ""
    notes: tuple[str, ...] = ()
```

`CvaCapitalImpact` in `frtb-cva` is superseded; the CVA impact module will
migrate to `CapitalImpact` in a follow-up issue (see §6 below).

### 3. Orchestration aggregation wrapper

A new `frtb_common.contribution_bundle` module defines the top-of-house
container:

```python
@dataclass(frozen=True)
class ComponentContributionBundle:
    """Orchestration wrapper that preserves component identity without altering contribution records."""

    component:             str   # "frtb_ima", "frtb_sbm", "frtb_drc", etc.
    contributions:         tuple[CapitalContribution, ...]
    component_total:       float  # must equal sum of contribution + residual across all records
    component_input_hash:  str
    component_profile_hash: str
```

Orchestration rules:
- **MUST NOT** alter `contribution`, `base_amount`, `method`, `source_id`, or
  `citations` of any incoming `CapitalContribution` record.
- **MUST** verify `component_total` equals `sum(r.contribution or 0 for r in
  contributions) + sum(r.residual for r in contributions)` within `ε = 1e-6`.
- **MAY** emit a suite-level `RESIDUAL` `CapitalContribution` for any
  non-linear cross-component interaction (IMA + SA + CVA aggregation is not
  Euler-decomposable across components).
- **MUST** propagate `input_hash` and `profile_hash` unchanged from component
  records to any suite-level report.

### 4. Method-selection rules

These rules are binding on all capital packages in the suite. They supplement
the method categorisation established in ADR 0037.

| Condition | Required method |
|---|---|
| Capital function positively homogeneous degree 1 in the source-level input; branch uniquely identified; no active floor or cap; denominator non-zero | `ANALYTICAL_EULER` |
| Additive or standalone line charge already explains the selected capital amount without differentiating through a nonlinear aggregation | `STANDALONE` |
| Active floor, cap, or min/max branch alters the effective derivative of the input dimension | `UNSUPPORTED` with signed `residual` carrying the unattributed amount |
| Zero denominator prevents the Euler derivative | `UNSUPPORTED` with reason |
| Input dimension crosses a bucket boundary or eligibility threshold between scenarios | `UNSUPPORTED` with reason |
| Contributions do not sum exactly due to non-linearity or rounding | One explicit `RESIDUAL` record per affected aggregation level; `reconciliation_status = PARTIAL_RESIDUAL` |
| Baseline-vs-candidate capital delta between two reconciled runs | `CapitalImpact` with `method = FINITE_DIFFERENCE`; never presented as marginal contribution |
| No attribution method is available; partial silent allocation would be misleading | `UNSUPPORTED` at the record level; residual carries the full unattributed amount |

### 4.1. Alternative method rationale

The FRTB IMCC literature also describes constrained Aumann-Shapley style
allocations (for example in arXiv:1801.07358v2). Those methods preserve
attribution axioms and can reduce instability for some portfolio geometries,
but they remain permutation-based and materially more expensive than standard
Euler for large attribution sets.

A useful complementary result is in Christoph Frei, "A New Approach to Risk
Attribution and Its Application in Credit Risk Analysis" (2020, *Risks*): for
nonlinear loss structures, a time-grid linearization of risk-driver slides can be
combined with Euler allocation, and the approximation converges as the number of
time steps grows. The paper also reports that Shapley-style methods become
computationally expensive as factor count grows, and that simple approximations
can miss the exact sum in strongly nonlinear settings.

For this suite:

- `ANALYTICAL_EULER` remains the default production method where the branch is
  differentiable and stable.
- Constrained Aumann-Shapley style methods are not default in the contract
  layer and may be introduced only as optional, bounded diagnostics when input
  scale is small and audit value is high.
- Frei-style time-grid linearized Euler diagnostics are also non-default and may be
  used only for explicit research or debug workflows when a controlled
  approximation error is acceptable and reconciliation residuals are explicitly
  retained.
- `FINITE_DIFFERENCE` remains an impact method only, and must not be presented
  as marginal attribution.
- Explicit `UNSUPPORTED` and `RESIDUAL` reporting is preferred over hidden
  approximations where branches switch, denominators collapse, or non-linear
  floors/caps dominate.

**Mandatory reconciliation invariant:** for any set of contribution records
covering one aggregation level, the following must hold within `ε = 1e-6`:

```
sum(r.contribution for r in records if r.contribution is not None)
+ sum(r.residual for r in records)
== capital_total_for_that_level
```

A package that cannot satisfy this invariant must emit `UNRECONCILED` status
and document the cause in `reason`.

### 5. Contract tests

`packages/frtb-common/tests/test_attribution_contract.py` verifies the
invariants above using only synthetic data and imports from `frtb-common`:

1. `ANALYTICAL_EULER` record requires non-None `marginal_multiplier` and `contribution`.
2. A mock package-local structure can be projected to `CapitalContribution` preserving all fields.
3. Reconciliation invariant: `contributions + residuals == capital_total` within `ε = 1e-6`.
4. `CapitalImpact.delta == candidate_total - baseline_total` exactly.
5. `ReconciliationStatus.RECONCILED` cannot be set when the sum check fails.
6. `ComponentContributionBundle` raises if `component_total` is inconsistent.

## Consequences

**Positive:**
- Orchestration has a formal, testable contract for ingesting and re-exposing
  component attribution records without coupling to component internals.
- Package-specific attribution work (SBM, CVA, orchestration) can proceed
  against a stable shared interface.
- Audit reviewers can verify reconciliation status from any contribution record
  without knowing package internals.
- `CvaCapitalImpact` migration is a mechanical rename; no capital arithmetic
  changes.

**Negative:**
- `CapitalContribution` gains four fields; code that hard-codes positional
  construction will need updating (low risk — all known callers use keyword
  arguments).
- `CvaCapitalImpact` must be deprecated and migrated in a follow-up PR.
- DRC's package-local `DrcCapitalContribution` must migrate to the shared type,
  completing the ADR 0037 follow-up.

## Package-specific follow-up issues

After this ADR is accepted, the following implementation issues are required:

- **frtb-common** (this PR): `ReconciliationStatus`, new `CapitalContribution`
  fields, `CapitalImpact`, `ComponentContributionBundle`, contract tests.
- **frtb-sbm**: Replace `SbmAttributionPlaceholder` and `SbmImpactPlaceholder`
  with `CapitalContribution` projection and `CapitalImpact`; re-scope
  SBM-FUNC-022.
- **frtb-cva**: Migrate `CvaCapitalImpact` to `CapitalImpact`; populate
  `citations` and `profile_hash` on `CvaAttributionContribution` projections.
- **frtb-drc**: Migrate `DrcCapitalContribution` to `frtb_common.CapitalContribution`;
  populate `citations`, `input_hash`, `profile_hash`, `reconciliation_status`.
- **frtb-ima**: Expose `CapitalContribution` projections from
  `DeskAuditRecord.capital`; confirm `input_hash` matches
  `DeskAuditRecord.inputs_hash`.
- **frtb-orchestration**: Implement `ComponentContributionBundle` aggregation
  and suite-level residual record for cross-component capital.

## References

- [ADR 0012](0012-capital-impact-attribution.md): Capital impact and attribution readiness.
- [ADR 0031](0031-drc-attribution-method-contract.md): DRC attribution method contract.
- [ADR 0037](0037-analytical-euler-decomposition-framework.md): Analytical Euler decomposition framework.
- [Issue #503](https://github.com/tomanizer/frtb-capital/issues/503): AUDIT-IMP-002 Define suite-wide attribution and impact contract.
- ArXiv:1801.07358v2 (Luting Li and Hao Xing): constrained Aumann-Shapley and
  FRTB IMCC allocation derivations under risk-factor/liquidity-bucket constraints.
- [Risks 8(2):65](https://doi.org/10.3390/risks8020065): Christoph Frei,
  "A New Approach to Risk Attribution and Its Application in Credit Risk
  Analysis" (2020).
