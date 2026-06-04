# 43. CVA validation maturity promotion

Date: 2026-06-04

## Status

Accepted

## Context

ADR 0040 added `US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA` as
capital-producing comparison profiles for the CVA methods and SA-CVA risk-class
paths already implemented by the Basel MAR50 runtime, but kept `frtb-cva` at
`partial_runtime` while the package still lacked an implemented-maturity
validation pack.

Issue #630 closes that evidence gap for the package-owned calculation boundary.
The package now has deterministic evidence for supported BA-CVA, SA-CVA, mixed
carve-out, profile, batch, Arrow handoff, audit, replay, and fail-closed
guardrail behavior. The supported runtime remains an ex-post capital layer: it
does not source market data, produce accounting CVA, calculate CCR capital,
approve SA-CVA model use, or perform final firm-level regulatory reporting.

Basel MAR50.9 and analogous CCR-substitution alternatives remain outside this
package because they require an upstream CCR capital contract and orchestration
method-election evidence.

## Decision

Promote `frtb-cva` from `partial_runtime` to `implemented` in the repository
maturity registry and public package metadata for the package-owned calculation
scope.

This promotion covers:

- reduced and full BA-CVA mechanics for supported inputs;
- supported SA-CVA delta and vega risk-class mechanics;
- mixed SA-CVA plus BA-CVA netting-set carve-out assembly;
- Basel, U.S. NPR 2.0, EU CRR3, and UK PRA comparison profile routing and
  profile-owned citations;
- batch and Arrow handoff parity for the supported public workflows;
- audit, replay, and validation guardrails that fail closed for unsupported
  methods, profile cells, malformed inputs, and out-of-scope alternatives.

The promotion does not change CVA formulas, calibration parameters, golden
fixture outputs, public calculation function signatures, or the supported-method
matrix. It changes the declared package maturity and validation status based on
the accumulated implementation and evidence set.

Keep MAR50.9 materiality-threshold substitution and analogous CCR-substitution
alternatives fail-closed until a separate ADR defines the required CCR and
orchestration input contract. Keep supervisory approval, source-data quality,
production monitoring, and final regulatory capital reporting out of the
`frtb-cva` package boundary.

## Consequences

- ADR 0040's consequence that `frtb-cva` remains `partial_runtime` is
  superseded for the package-owned calculation scope.
- `frtb-cva` joins the implemented-package coverage gate, package maturity
  evidence registry, and package status dashboard.
- The package changelog fragment records the material status change; the package
  version bump is deferred to the release PR in accordance with ADR 0015.
- Any future expansion that changes formulas, supported regimes, method routing,
  requirement status, policy hashes, public API semantics, or audit-record
  semantics remains material under ADR 0005 and requires its own ADR.
- Outputs remain synthetic engineering and validation evidence, not final
  regulatory capital or supervisory approval for SA-CVA model use.

## References

- ADR 0005: material change policy and ADR-driven change control.
- ADR 0015: deferred versioning and changelog fragments.
- ADR 0040: CVA non-Basel comparison profiles.
- GitHub issue #630.
- Basel Framework MAR50.8, MAR50.9, MAR50.14-MAR50.26, and
  MAR50.42-MAR50.77.
- Regulation (EU) 2024/1623 Articles 381-386 and inserted Articles 383a-383z.
