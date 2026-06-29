# 47. DRC risk-class maturity policy and recovery-unlinked netting rank

Date: 2026-06-29

## Status

Accepted

## Context

The DRC audit in #971 found two places where implemented policy was too implicit:

- `get_maturity_policy()` selected only by profile, so securitisation non-CTP
  and CTP rows used the non-securitisation maturity ramp even though
  securitisation and CTP gross default exposure rules are stated as market-value
  measures.
- `NOT_RECOVERY_LINKED` was ranked below equity for same-obligor netting without
  a local design citation.

Basel MAR22.15-MAR22.18 and proposed U.S. section `__.210(a)(2)(iii)` define the
non-securitisation maturity floor and ramp used before non-securitisation
netting. Basel MAR22.27 and proposed U.S. section `__.210(c)(1)` define
securitisation non-CTP gross default exposure by market value. Basel
MAR22.36-MAR22.37 and proposed U.S. section `__.210(d)(1)` define CTP gross
default exposure by market value. The current supported securitisation and CTP
profiles do not add a separate maturity ramp after those market-value gross JTD
definitions.

For recovery-unlinked instruments, proposed U.S. section `__.210(b)(1)(iv)` and
Basel MAR22.12 assign a zero LGD treatment where value is not linked to issuer
recovery. The suite's `NOT_RECOVERY_LINKED` seniority is a code category for
that zero-LGD treatment, not a Basel seniority label. When such a position
enters same-obligor non-securitisation netting, placing it below equity keeps
the existing conservative offset ordering explicit and reviewable.

## Decision

DRC maturity policy is selected by `(profile_id, risk_class)`.

- Non-securitisation keeps the maturity floor and ramp:
  - U.S. NPR 2.0: proposed section `__.210(a)(2)(iii)`.
  - Basel MAR22: MAR22.15-MAR22.18.
  - EU CRR3: Article 325x.
- Securitisation non-CTP uses weight `1.0` for supported U.S. NPR 2.0 and Basel
  MAR22 profiles, citing proposed section `__.210(c)(1)` or MAR22.27.
- CTP uses weight `1.0` for supported U.S. NPR 2.0 and Basel MAR22 profiles,
  citing proposed section `__.210(d)(1)` or MAR22.36.

`NOT_RECOVERY_LINKED` remains ranked below equity in the non-securitisation
netting order. Code comments must cite this ADR and the paragraph-level LGD
source (`US_NPR_210_B_1_IV` or `BASEL_MAR22_12`) at the rank table.

## Consequences

Securitisation non-CTP and CTP positions with maturity below one year no longer
inherit the non-securitisation maturity ramp. Their gross JTD remains the cited
market-value measure before netting and capital aggregation.

The recovery-unlinked netting rank is no longer an undocumented implementation
choice. It remains a suite design decision grounded in the zero-LGD regulatory
category and can be revisited if a future rule profile needs different
instrument-specific treatment.

## References

- #971: DRC regulatory compliance audit.
- #973: risk-class maturity dispatch gap.
- #975: recovery-unlinked netting-rank citation gap.
- [ADR 0012](0012-capital-impact-attribution.md): capital impact and
  attribution readiness.
