# 28. DRC securitisation non-CTP row path

Date: 2026-06-02

## Status

Accepted

## Context

`frtb-drc` previously supported non-securitisation and CTP DRC but continued to
fail closed for securitisation positions outside the correlation trading
portfolio. Issue #335 had been closed, but the current main branch still listed
`DrcRiskClass.SECURITISATION_NON_CTP` as unsupported and the public API rejected
those rows.

Basel MAR22.27-MAR22.35 and proposed U.S. section `__.210(c)` define a path that
differs from both non-securitisation and CTP:

- gross default exposure for a securitisation non-CTP position equals market
  value, because LGD is embedded in the securitisation risk weight;
- ordinary offsetting is limited to rows with the same underlying asset pool and
  the same tranche, with broader replication or decomposition allowed only when
  that evidence exists;
- buckets follow the cited corporate or asset-class/region taxonomy;
- bucket capital uses the standard HBR and floor formula;
- category capital is the simple sum of securitisation non-CTP buckets;
- risk weights are tranche-specific and based on banking-book securitisation
  treatment.

The package does not contain the banking-book securitisation hierarchy,
including SEC-SA, SEC-ERBA, SEC-IRBA, STC alternatives, or U.S. standardized and
expanded total risk-weighted asset variants. Reusing non-securitisation credit
quality weights would understate or misstate the rule. Treating missing weights
as zero would be worse because it would silently emit placeholder capital.

## Decision

Implement a securitisation non-CTP row path with explicit run-scoped evidence:

- Position rows use `DrcRiskClass.SECURITISATION_NON_CTP` and the existing
  `DrcPosition` contract.
- `issuer_id` carries the underlying asset pool identity for ordinary
  same-pool/same-tranche offsetting; `tranche_id` carries tranche identity.
- Gross default exposure is calculated from absolute market value and rejects
  missing market value or LGD overrides.
- Bucket keys are validated against the cited U.S. NPR 2.0 securitisation
  non-CTP taxonomy.
- Tranche risk weights are supplied through
  `DrcCalculationContext.securitisation_non_ctp_risk_weights[position_id]`.
- Replication or decomposition offsets outside exact same-pool/same-tranche
  identity require
  `DrcCalculationContext.securitisation_non_ctp_offset_groups[position_id]`.
- Missing risk weights, unused securitisation evidence, mixed risk weights
  inside a net group, missing pool identity without explicit offset evidence,
  invalid buckets, and unsupported optional cap behavior fail closed.
- Disallowed long/short offsets inside the same bucket are retained as
  `RejectedOffset` audit records.

The profile now treats non-securitisation, securitisation non-CTP, and CTP as
supported row paths, with no diversification benefit across categories.

## Consequences

The public DRC API can calculate mixed non-securitisation, securitisation
non-CTP, and CTP books while preserving separate category totals and branch
metadata. The path is transparent because upstream banking-book securitisation
risk weights are visible in the context, included in the deterministic input
hash, and rejected when missing.

ADR 0029 supersedes the raw-map-only wording here by adding typed
`DrcRiskWeightEvidence` records as the production audit contract while
preserving the raw map as a low-level compatibility input.

This is not an internal banking-book securitisation risk-weight engine. A future
PR may derive risk weights from SEC-SA/SEC-ERBA/SEC-IRBA or jurisdictional
equivalents and add a controlled fair-value cap option. Until then, callers must
provide cited, upstream-derived securitisation non-CTP risk weights and explicit
replication evidence where they want non-exact offsetting recognition.

## Validation

- `tests/test_securitisation.py` covers unhedged capital, exact
  same-pool/same-tranche offsetting, rejected different-tranche offsets,
  explicit replication groups, bucket floors, missing market values, missing
  risk weights, mixed risk weights in a net group, invalid buckets, profile
  support, and fixture replay.
- `tests/fixtures/drc_sec_nonctp_v1` provides a hand-checked fixture with one
  same-pool/same-tranche CLO offset and one RMBS bucket with rejected
  cross-pool offsetting.
