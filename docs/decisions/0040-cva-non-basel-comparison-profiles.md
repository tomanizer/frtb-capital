# 40. CVA non-Basel comparison profiles

Date: 2026-06-04

## Status

Accepted

## Context

`frtb-cva` originally exposed `US_NPR20_VB`, `EU_CRR3_CVA`, and
`UK_PRA_CVA` as regulatory-profile enum values, but only
`BASEL_MAR50_2020` was capital-producing. The non-Basel profiles failed closed
because they did not have profile-owned citation maps, reference-data payloads,
support-matrix rows, deterministic hashes, or synthetic runtime fixtures.

Issue #568 tracks adding U.S. NPR 2.0, EU CRR3, and UK PRA CVA profile support.
The user shorthand "ECB" is treated as the EU CRR3 CVA profile because ECB
supervision does not by itself define a separate CVA calculation profile in this
package.

## Decision

Support `US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA` as
capital-producing comparison profiles under audit for the CVA methods and
SA-CVA risk-class paths already implemented by the Basel MAR50 runtime.

Each non-Basel profile must have:

- profile-owned citation ids and source metadata;
- a deterministic profile reference payload and content hash;
- support-matrix rows for supported and unsupported cells;
- public API and batch tests proving successful BA-CVA, SA-CVA, hedge, and
  mixed carve-out paths where applicable;
- explicit fail-closed behavior for unsupported profile/method/risk-class cells.

The numeric calibration may match the Basel MAR50 implementation where the
delivered comparison-profile slice has no cited divergence, but the runtime must
not silently emit Basel citation ids or Basel profile hashes for non-Basel
profiles.

Keep MAR50.9 materiality-threshold substitution and analogous simplified
CCR-substitution alternatives fail-closed until a separate ADR defines the
required upstream CCR/orchestration input contract.

## Consequences

- `frtb-cva` remains `partial_runtime` because unsupported CCR-substitution and
  regulatory-approval boundary paths still fail closed.
- Successful non-Basel CVA results now carry profile-specific citation ids and
  profile hashes, even when capital numbers match the Basel-aligned comparison
  calibration.
- The package changelog fragment records the material profile-support expansion;
  the package version bump is deferred to the release PR in accordance with ADR
  0015.
- Model documentation, package requirements, and regulatory source manifests
  must distinguish comparison evidence from final U.S., EU, or UK regulatory
  capital.

## References

- ADR 0005: material change policy and ADR-driven change control.
- ADR 0015: deferred versioning and changelog fragments.
- GitHub issue #568.
- U.S. NPR 2.0, 91 FR 14952 section V.B.
- Regulation (EU) 2024/1623 Articles 381-386 and inserted Articles 383a-383z.
- PRA PS1/26 and PRA Rulebook CVA Risk Part.
