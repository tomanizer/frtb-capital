# 22. SA composition enforces a consistent regulatory jurisdiction across components

Date: 2026-05-31

## Status

Accepted

The final consequence note about the guard firing before SA arithmetic is
historical. SA arithmetic and fallback route recording are implemented by
[ADR 0032](0032-orchestration-sa-arithmetic-and-fallback-routing.md); the
jurisdiction-family guard remains in force.

## Context

The Standardised Approach capital charge is composed as `SA = SBM + DRC + RRAO`.
Each component is implemented by a separate package that carries its own
`profile_id` string identifying the regulatory jurisdiction and chapter.
Because each component belongs to a different MAR chapter, the profile IDs are
not identical even within the same jurisdiction:

| Component | Basel profile_id | US-NPR profile_id | EU profile_id |
|---|---|---|---|
| SBM (`frtb-sbm`) | `BASEL_MAR21` | `US_NPR_2_0` | `EU_CRR3` |
| DRC (`frtb-drc`) | (not yet implemented) | `US_NPR_2_0` | (not yet implemented) |
| RRAO (`frtb-rrao`) | `BASEL_MAR23` | `US_NPR_2_0` | `EU_CRR3` |

A regulatory-compliance audit (issue #241) found that
`compose_standardised_approach_capital` accepted component results with
different `profile_id` values — for example, SBM with `BASEL_MAR21` and DRC
with `US_NPR_2_0` — without any error. Mixing jurisdictions inside a single SA
capital number is not a valid regulatory result and violates the suite's own
cross-package consistency standard.

## Decision

Introduce a **jurisdiction family map** in `standardised.py`:

```python
_SA_JURISDICTION_FAMILY: dict[str, str] = {
    "BASEL_MAR21": "BASEL",
    "BASEL_MAR22": "BASEL",
    "BASEL_MAR23": "BASEL",
    "US_NPR_2_0": "US_NPR",
    "EU_CRR3": "EU_CRR3",
}
```

All three Basel chapter labels (`BASEL_MAR21`, `BASEL_MAR22`, `BASEL_MAR23`)
map to the same `"BASEL"` family because they are different chapters of the same
jurisdiction. `US_NPR_2_0` and `EU_CRR3` are self-contained families.

`compose_standardised_approach_capital` calls `_assert_consistent_jurisdiction`
on all supplied component handoffs **before** checking for missing components.
The function raises `OrchestrationInputError` in two cases:

1. A supplied `profile_id` is not present in `_SA_JURISDICTION_FAMILY`
   (unrecognised profile, fails closed).
2. The set of jurisdiction families across the supplied components has more than
   one member (mixed-jurisdiction composition).

## Decision: no Basel MAR22 DRC profile in this PR

The existing `frtb-drc` package has no `BASEL_MAR22` profile (it implements
only `US_NPR_2_0`). Adding a Basel DRC profile is a separate workitem and
remains outside the scope of this PR.

As a consequence, a fully-Basel SA composition (`BASEL_MAR21` + `BASEL_MAR22` +
`BASEL_MAR23`) is not yet achievable within this suite. The US-NPR composition
(`US_NPR_2_0` across all three) is the only fully implementable SA jurisdiction
at this stage.

## Consequences

- **Immediate:** any call that mixes, say, a Basel SBM result with a US-NPR DRC
  result now raises `OrchestrationInputError` with a message naming the
  offending profile IDs. This is the correct behaviour — previously such a
  composition would silently reach the "aggregation arithmetic unimplemented"
  error, which masked the jurisdiction mismatch.
- **Future-proofing:** new profile IDs must be added to
  `_SA_JURISDICTION_FAMILY` before they can be used in SA composition; the
  function fails closed on unknown IDs.
- **ADR 0003 / ADR 0010 cross-reference:** ADR 0003 defines the SA component
  scope (SBM + DRC + RRAO); ADR 0010 defines the SA taxonomy. Neither addressed
  cross-component jurisdiction consistency; this ADR fills that gap.
- The guard fires before SA aggregation arithmetic is implemented, so it will
  remain in force when arithmetic lands without any additional work.

## References

- GitHub issue #241.
- ADR 0003 (SA-DRC-CVA scope).
- ADR 0010 (SA component taxonomy).
