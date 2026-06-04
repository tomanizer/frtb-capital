# 42. DRC CRIF/vendor ingress adapter boundary

Date: 2026-06-04

## Status

Accepted

## Context

`frtb-drc` previously required clients to map CRIF or vendor-shaped default-risk
feeds directly into either canonical `DrcPosition` records or the class-specific
DRC Arrow table contracts. Issue #584 adds a package-owned ingress helper for
that mapping.

The change is material under ADR 0005 because it adds documented public API
semantics and a new adapter boundary. It does not change DRC capital formulas,
profile support, or risk-weight evidence requirements.

## Decision

Expose a DRC-owned CRIF/vendor ingress adapter that maps mapping rows into:

- canonical `DrcPosition` rows with `DrcSourceLineage.source_column_map`;
- deterministic `DrcRejectedCrifRow` diagnostics for missing identities,
  unsupported risk classes, ambiguous direction, invalid numbers, and incomplete
  class-specific identities;
- class-specific `NormalizedArrowTable` handoffs for accepted
  non-securitisation, securitisation non-CTP, and CTP rows.

The adapter must require an explicit source sign convention. It may read an
explicit long/short source field or derive direction from signed notional or
signed market value. Zero or ambiguous signs fail deterministically.

The adapter remains an ingress helper. It must not import sibling capital
packages or dataframe libraries, and it must not supply missing securitisation
or CTP risk-weight overlays. Capital calculation continues to use canonical
row APIs, DRC Arrow batch APIs, and typed context/evidence contracts.

## Consequences

- Public docs describe vendor/CRIF input as a Tier 2 adapter path rather than a
  capital kernel.
- DRC clients can keep source-column lineage and rejected-row evidence before
  calculation.
- Securitisation non-CTP and CTP adapter rows can become canonical positions or
  Arrow handoffs, but profile-specific risk-weight evidence remains a separate
  required input for capital where the selected profile requires it.
- The package changelog fragment records the public adapter expansion; version
  bumping remains deferred to the release PR under ADR 0015.

## References

- ADR 0005: material change policy and ADR-driven change control.
- ADR 0015: deferred versioning and changelog fragments.
- ADR 0023: Arrow tabular handoff boundary.
- GitHub issue #584.
