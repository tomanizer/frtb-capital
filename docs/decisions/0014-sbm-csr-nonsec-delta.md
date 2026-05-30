# 14. SBM CSR non-securitisation delta path

Date: 2026-05-30

## Status

Accepted

## Context

Epic #160 requires cited CSR non-securitisation delta capital under Basel MAR21.51–57
(SBM-FUNC-014). GIRR, FX, equity, and commodity delta slices already exercise the
shared weighting, intra-bucket, inter-bucket, and MAR21.7 portfolio scenario
primitives. CSR securitisation (CTP and non-CTP) remains explicitly out of scope
for this change.

## Decision

Implement CSR non-securitisation delta as a profile-owned reference-data module plus
`risk_classes/csr_nonsec.py` assembly:

- Buckets 1–18 with Table 4 risk weights (MAR21.53).
- Prescribed tenors `{6m, 1y, 3y, 5y, 10y}` and BOND/CDS risk factors only (MAR21.9).
- Intra-bucket correlations for name, tenor, and basis (MAR21.54–55); bucket 16
  other-sector uses absolute-weight intra aggregation (MAR21.56).
- Inter-bucket gamma from Table 5 (MAR21.57).
- Caller-supplied bucket and issuer `qualifier`; deterministic validation at the
  weighting boundary rejects unknown buckets, tenors, basis, or risk factors.
- CSR_SEC_CTP and CSR_SEC_NONCTP remain fail-closed.

## Consequences

- `frtb-sbm` 0.7.0 expands the BASEL_MAR21 profile hash; existing fixture packs
  update expected `profile_hash` only.
- `calculate_sbm_capital` routes homogeneous CSR_NONSEC/DELTA inputs.
- Synthetic `csr_nonsec_delta_v1` fixture reconciles total capital 212,390.50 under
  the HIGH correlation scenario (0.7.1 fixes MAR21.57 Table 5 lookup indexing).
- No sibling capital-package imports; numpy-only kernels.

## References

- Basel Framework MAR21.9, MAR21.51–MAR21.57.
- `packages/frtb-sbm/tests/fixtures/csr_nonsec_delta_v1/`.
- GitHub issue #164.
