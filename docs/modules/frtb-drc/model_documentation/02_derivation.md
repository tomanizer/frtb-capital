# Derivation

## Gross JTD

For supported non-securitisation positions, the package derives gross JTD from
validated position exposure, direction, LGD, and P&L fields before maturity
scaling. Basel non-securitisation LGD and JTD anchors are MAR22.9-MAR22.12.
The U.S. NPR 2.0 non-securitisation row path is anchored to proposed section
`__.210(b)(1)(ii)-(vii)`.

Securitisation non-CTP and CTP rows use market-value gross default exposure and
typed upstream evidence rather than non-securitisation LGD formulas. Those paths
are anchored to MAR22.27-MAR22.35 and MAR22.39-MAR22.47, with U.S. NPR 2.0
anchors in proposed sections `__.210(c)` and `__.210(d)`.

## Maturity Scaling

The non-securitisation path applies a bounded effective-maturity scalar per
position before netting. The Basel anchor is MAR22.15-MAR22.18. The test suite
checks lower-bound, upper-bound, and citation-preserving maturity cases in
`packages/frtb-drc/tests/test_drc_maturity.py`.

## Netting

Non-securitisation rows are grouped by issuer and seniority-sensitive keys.
Long and short scaled JTD amounts remain separated so HBR can be computed from
net long and net short amounts rather than from signed totals. This follows the
MAR22.13-MAR22.18 sequencing.

Securitisation non-CTP rows require identical pool and tranche identity unless
the run supplies explicit replication-group evidence. CTP rows similarly require
exact matching or explicit replication evidence before offsetting. Those gates
avoid silent cross-tranche or cross-index offsets that would not be supported by
MAR22.27-MAR22.35 or MAR22.39-MAR22.47.

## Bucket And Category Capital

For each supported bucket, the package applies profile risk weights to net long
and short JTD, computes the hedge benefit ratio, and assembles bucket capital.
Non-securitisation bucket/category anchors are MAR22.21-MAR22.26. Basel MAR22
non-securitisation risk weights use MAR22.24; U.S. NPR 2.0 risk weights are
supplied through the cited profile data and fixture evidence.

Category totals are deterministic sums over bucket results for the active risk
class. Mixed risk-class aggregation is outside the DRC package; Standardised
Approach composition belongs in `frtb-orchestration`.

## Audit And Reconciliation

The result carries profile hash, input hash, reconciliation metadata, source
lineage, and branch records. Attribution records reconcile to total DRC when
exact analytical allocation is valid; otherwise they state residual or
unsupported method explicitly under DRC-FUNC-017 and ADR 0012.
