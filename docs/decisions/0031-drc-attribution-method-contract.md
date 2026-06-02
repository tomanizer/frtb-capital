# ADR 0031: DRC attribution method contract

## Status

Accepted.

## Context

ADR 0012 requires capital components to preserve attribution-ready branch
metadata, stable ids, deterministic grouping, and explicit fallback behavior.
The DRC row and batch paths now support U.S. NPR 2.0 non-securitisation,
securitisation non-CTP, and CTP capital calculations. Those paths include
branch-sensitive mechanics: HBR, bucket floors, CTP positive/negative bucket
recognition, rejected offsets, profile-controlled fair-value caps, and
run-supplied securitisation/CTP risk-weight evidence.

Attribution must not change the capital number, and it must not imply exact
Euler decomposition where the active branch is non-differentiable or lacks
lineage.

## Decision

`frtb-drc` will emit deterministic `DrcCapitalContribution` records in
`DrcCapitalResult.attribution_records` for supported row and batch results.

The method labels are:

- `ANALYTICAL_EULER`: used for stable, differentiable active branches where
  net JTD risk-weight lineage is unique.
- `RESIDUAL`: used to reconcile remaining category capital when exact
  analytical allocation is not the selected branch for that amount.
- `UNSUPPORTED`: used when exact Euler attribution is not valid for the active
  branch, including floors, zero HBR denominators, and missing or non-unique
  net risk-weight lineage.

Non-securitisation and securitisation non-CTP attribution use bucket-local HBR.
CTP attribution uses the CTP-wide HBR carried on CTP buckets and applies the
active category recognition factor for positive bucket capital and negative
bucket capital before reconciling to CTP category capital.

Attribution records are explain artifacts. They are calculated after the
capital result is built and validated, and they must reconcile to total DRC
within tolerance. Baseline-vs-candidate impact analysis remains a separate
future `impact.py` concern and must be labelled separately from marginal
contribution.

## Consequences

Row and batch results carry a richer serialized output, so committed fixture
hashes include `attribution_records`. Public capital totals, input hashes, and
profile hashes remain unchanged.

Future impact work can consume the same stable ids and branch metadata without
changing DRC capital formulas. Future branch-specific attribution extensions
must either preserve total reconciliation or emit explicit residual or
unsupported records.
