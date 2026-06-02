# 24. DRC U.S. NPR corporate investment-grade risk weight correction

Date: 2026-06-02

## Status

Accepted

## Context

Issue #340 re-audited the `frtb-drc` U.S. NPR 2.0 non-securitisation default
risk reference data against the primary re-proposal source. The source text in
proposed section `__.210(b)(1)(iv)`, 91 FR 15236, confirms that defaulted
non-securitisation positions receive a flat 100% LGD rather than a
seniority-dependent LGD.

The numeric risk-weight table is embedded as an image in the GovInfo PDF:
`EP27MR26.330`, labelled "Table 1 to § __.210--Default Risk Weights for
Non-Securitization Debt or Equity Positions by Credit Quality Category" on
91 FR 15237. That table sets the following investment-grade, speculative-grade,
and sub-speculative-grade risk weights:

- non-U.S. sovereign positions: 0.6%, 22.0%, 50.0%;
- PSE and GSE debt positions: 2.1%, 22.0%, 50.0%;
- corporate positions: 4.1%, 22.0%, 50.0%;
- defaulted positions: 100%.

The package had correctly represented the non-U.S. sovereign, PSE/GSE,
speculative-grade, sub-speculative-grade, and defaulted entries, but had copied
the PSE/GSE investment-grade value into the corporate investment-grade entry:
`2.1%` instead of `4.1%`.

## Decision

Set the U.S. NPR 2.0 non-securitisation `CORPORATE` +
`INVESTMENT_GRADE` default risk weight to `0.041`. Leave the `PSE_GSE` +
`INVESTMENT_GRADE` risk weight at `0.021`, and keep defaulted-position LGD as
the flat `1.00` rule because proposed section `__.210(b)(1)(iv)` states
"defaulted positions" in the 100% LGD clause.

The `US_NPR_2_0` profile id remains unchanged because the implemented rule
profile is still the same regulatory proposal. The profile content hash changes
because the reference-data payload changes, and any golden fixture outputs that
include profile hashes or corporate investment-grade bucket capital must be
regenerated.

## Consequences

DRC capital increases for portfolios with investment-grade corporate
non-securitisation net long exposure, and decreases in absolute hedge-benefit
relief where investment-grade corporate net shorts are present. This is a
material model correction under ADR 0005 because it changes a regulatory
parameter and committed golden outputs.

Feature PRs must not bump package versions directly under ADR 0015. This PR
therefore carries a `frtb-drc` changelog fragment and leaves the version bump
to the next release PR.

Regression tests must assert the full U.S. NPR 2.0 non-securitisation
risk-weight grid so the corporate investment-grade entry cannot silently drift
back to the PSE/GSE value.

## References

- [U.S. NPR 2.0, 91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959).
- Proposed section `__.210(b)(1)(iv)`, 91 FR 15236.
- Table 1 to proposed section `__.210`, 91 FR 15237.
- #340.
