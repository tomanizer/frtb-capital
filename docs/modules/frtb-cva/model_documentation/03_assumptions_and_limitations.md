# Assumptions And Limitations

## Implemented Scope

The package-owned CVA calculation scope is implemented for `BASEL_MAR50_2020`,
`US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA`. It supports reduced and full
BA-CVA, supported SA-CVA delta/vega risk classes, mixed carve-out,
qualified-index routing where metadata is supplied, and package-owned batch,
Arrow, audit, replay, attribution, and impact helpers. Non-Basel profiles are
comparison profiles with profile-owned citations and hashes; U.S. NPR 2.0
remains proposed-rule material, and ECB shorthand routes to `EU_CRR3_CVA`.

The validation status is available for package-owned CVA capital mechanics and
handoff/audit helpers. It excludes CCR-substitution alternatives, supervisory
approval workflow, legal interpretation, production source-data controls, and
final regulatory capital reporting.

## Fail-Closed Unsupported Scope

The following paths fail closed:

- MAR50.9 materiality-threshold 100% CCR alternative;
- analogous simplified CCR-substitution alternatives in non-Basel profiles;
- CCS vega capital, because MAR50.45 and MAR50.63 define CCS delta but no CCS
  vega capital path.

The implemented status does not include MAR50.9 or analogous CCR-substitution
alternatives. Those paths remain explicit `unsupported_fail_closed`
support-matrix rows. Implementing them later requires a separate ADR for the
upstream CCR capital input contract and orchestration method election.

## Out-Of-Scope Boundaries

The support matrix marks the following package-boundary items as `out_of_scope`,
not as capital-producing methods:

- regulatory approval or governance workflow for SA-CVA use;
- exposure simulation and sensitivity generation under MAR50.31-MAR50.36.

## Input Boundaries

BA-CVA inputs must identify exposure-at-default or a supported exposure measure,
effective maturity, sector, credit quality, and netting-set identity. SA-CVA
inputs must identify risk class, risk measure, bucket, risk-factor key, CVA or
hedge tag, amount, and required volatility or tenor metadata.

The package does not infer missing counterparty classifications, volatility
inputs, hedge eligibility, or qualified-index metadata.

## Validation Limits

The evidence is deterministic and synthetic. It demonstrates reproducible
package-owned calculation mechanics for supported inputs, but not production
source-data quality, legal interpretation, supervisory approval, production
monitoring, or final regulatory capital.
