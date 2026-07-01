# Conceptual Soundness

## Model Design

`frtb-drc` separates upstream credit-risk data preparation from the ex-post
Default Risk Charge capital calculation. Upstream systems supply issuer,
tranche, position, risk-weight, fair-value cap, FX, and offset evidence. The
package validates those inputs and applies deterministic DRC mechanics for the
profile/risk-class combinations that have cited rules and package tests.

This boundary is appropriate because MAR22.1 frames DRC as a jump-to-default
capital charge and MAR22.9-MAR22.47 define the calculation mechanics. The
package does not assign ratings, derive banking-book securitisation risk
weights, or infer replication evidence because those decisions require source
systems and controls outside the capital kernel.

## Core Mechanics

| Mechanic | Conceptual basis | Regulatory anchor | Evidence |
| --- | --- | --- | --- |
| Gross JTD | Long and short default exposure are measured before netting so issuer and tranche offsets can be controlled explicitly. | MAR22.9-MAR22.12; proposed U.S. section `__.210(b)(1)(ii)-(vii)`. | `gross_jtd.py`, `securitisation.py`, `ctp.py`, `test_drc_gross_jtd.py`. |
| Maturity scaling | JTD is scaled by bounded effective maturity rather than by portfolio-level averages. | MAR22.15-MAR22.18; proposed U.S. section `__.210(b)(1)(iv)`. | `maturity.py`, `test_drc_maturity.py`. |
| Non-securitisation netting | Long and short net JTD are grouped by issuer and seniority constraints before bucket capital. | MAR22.13-MAR22.18; proposed U.S. section `__.210(b)(1)(viii)`. | `netting.py`, `test_drc_netting.py`. |
| Securitisation non-CTP netting | Offsets require same-pool/same-tranche identity or explicit replication-group evidence. | MAR22.27-MAR22.35; proposed U.S. section `__.210(c)`. | `securitisation.py`, `test_drc_securitisation.py`. |
| CTP netting | CTP offsets use exact matching or explicit replication groups before CTP-wide HBR. | MAR22.39-MAR22.47; proposed U.S. section `__.210(d)`. | `ctp.py`, `test_drc_ctp.py`. |
| Risk weights and buckets | Bucket/category aggregation is profile-bound and rejects missing or unsupported mappings. | MAR22.21-MAR22.26, MAR22.34, MAR22.42; proposed U.S. section `__.210(b)-(d)`. | `reference_data.py`, `regimes.py`, `test_drc_regimes.py`. |
| Attribution readiness | Analytical records are emitted only where the active branch supports exact reconciliation; residual or unsupported records are explicit. | ADR 0012; DRC-FUNC-017. | `attribution.py`, `test_drc_attribution.py`. |

## Suitability

The implementation preserves the calculation drivers that determine DRC for the
supported U.S. NPR 2.0, Basel MAR22, EU CRR3, and PRA UK CRR paths:

- gross default exposure is calculated before netting;
- maturity scaling is applied per position;
- long and short net JTD values are kept separate through HBR;
- category totals are assembled from bucket capital rather than from raw rows;
- unsupported profiles and unsupported risk classes fail before capital is
  emitted.

The strongest evidence is for deterministic mechanics and explicit boundary
handling. Final regulatory capital use would require bank-specific source data,
model validation, legal interpretation, and supervisory review.
