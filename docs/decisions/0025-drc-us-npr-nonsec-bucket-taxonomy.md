# 25. DRC U.S. NPR non-securitisation bucket taxonomy

Date: 2026-06-02

## Status

Accepted

## Context

Issue #339 asked whether the `US_NPR_2_0` DRC profile was missing a U.S.
sovereign bucket, municipal/local-government bucket, or separate PSE/GSE
buckets.

The primary U.S. NPR 2.0 source defines four non-securitisation default-risk
buckets in proposed section `__.210(b)(3)(i)`, 91 FR 15237:

- non-U.S. sovereign exposures;
- PSE and GSE debt positions;
- corporate positions;
- defaulted positions.

Table 1 to proposed section `__.210`, 91 FR 15237, then provides risk weights
for non-U.S. sovereign, PSE/GSE debt, corporate, and defaulted rows. It does not
provide U.S.-sovereign, specified-supranational, MDB, municipal, or
local-government DRC rows for this U.S. NPR profile.

This diverges from Basel MAR22.22-MAR22.24, which defines non-securitisation
DRC buckets for corporates, sovereigns, and local governments/municipalities,
and from Basel MAR22.7, which allows national discretion for zero default-risk
weights on claims on sovereigns, PSEs, and MDBs. The package does not yet
implement a generic Basel MAR22 profile; it implements the proposed U.S. NPR 2.0
profile.

## Decision

Keep the `US_NPR_2_0` non-securitisation DRC bucket taxonomy to the four buckets
listed in proposed section `__.210(b)(3)(i)`: `NON_US_SOVEREIGN`, `PSE_GSE`,
`CORPORATE`, and `DEFAULTED`.

Do not add a U.S.-sovereign or municipal/local-government zero-risk-weight
bucket to the U.S. NPR profile without a future cited rule-profile change.

Treat `US_SOVEREIGN`, `SPECIFIED_SUPRANATIONAL`,
`MULTILATERAL_DEVELOPMENT_BANK`, `MDB`, `MUNICIPAL`, and `LOCAL_GOVERNMENT` as
non-chargeable input classification labels for the U.S. NPR profile. Reject them
at row and columnar batch validation before risk-weight lookup. Municipal or
local-government debt may be processed only after upstream mapping to `PSE_GSE`
when the source classification validly supports PSE/GSE debt treatment.

Keep PSE and GSE combined in the `PSE_GSE` bucket because the U.S. NPR bucket
label and Table 1 row combine PSE and GSE debt positions.

## Consequences

This is a validation and governance correction, not a numeric-capital
expansion. Existing valid U.S. NPR capital numbers do not change. Inputs that
previously failed later through strict bucket/risk-weight lookup now fail
earlier with a precise citation and without row materialisation in the Arrow
batch path.

A future Basel MAR22 profile may add sovereign and local-government/
municipality bucket support, including MAR22.7 national-discretion behavior, but
that must be implemented as a separate cited rule profile rather than by adding
Basel buckets to the U.S. NPR 2.0 profile.

Feature PRs must not bump package versions directly under ADR 0015. This PR
therefore carries a `frtb-drc` changelog fragment and leaves the version bump
to the next release PR.

## References

- [U.S. NPR 2.0, 91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959).
- Proposed section `__.210(b)(3)(i)`, 91 FR 15237.
- Table 1 to proposed section `__.210`, 91 FR 15237.
- [Basel MAR22.7 and MAR22.22-MAR22.24](https://www.bis.org/basel_framework/chapter/MAR/22.htm).
- #339.
