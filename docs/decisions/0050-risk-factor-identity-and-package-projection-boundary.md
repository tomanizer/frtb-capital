# 50. Risk-factor identity and package projection boundary

Date: 2026-07-01

## Status

Proposed

## Context

[ADR 0049](0049-result-evidence-and-market-data-platform-boundary.md) separates
run-scoped FRTB evidence from enterprise market/scenario-data infrastructure.
That boundary is necessary but not sufficient for time-series, shocks,
scenario vectors, and surfaces, because all four are joined through risk-factor
identity.

The repository already contains several risk-factor concepts:

- `frtb-ima` has `RiskFactorDefinition` and an IMA risk-factor master mapping
  adapter for RFET, liquidity horizon, scenario-cube, and modellability use
  cases.
- `frtb-sbm` stores package-local sensitivity `risk_factor` strings plus
  curvature shock and surface references.
- `frtb-cva` stores SA-CVA `risk_factor_key` values plus volatility surface and
  shock references.
- `frtb-result-store` capital nodes and artifact schemas already expose
  `risk_factor_id` and `risk_factor_set_id` as read-model dimensions.

Without a suite-wide identity boundary, future work can drift into incompatible
strings, duplicated package-specific masters, hidden UI joins, or a generic
risk-factor ontology inside `frtb-common`.

This ADR defines the boundary. It does not introduce a full enterprise
risk-factor master in this repository.

RFET vendor and internal observation mapping is a specialized risk-factor
identity consumer. [ADR 0051](0051-rfet-observation-and-vendor-mapping-evidence-boundary.md)
defines the RFET observation and mapping evidence boundary.

## Decision

Enterprise reference-data or market-data platforms own the enterprise
risk-factor master. `frtb-capital` owns only:

1. lightweight, package-neutral risk-factor identity primitives;
2. immutable run-scoped risk-factor catalog evidence or references;
3. package-owned projections from that catalog into IMA, SBM, CVA, DRC, and
   RRAO input/result contracts;
4. result-store referential checks and read-only catalog exposure for committed
   runs.

`frtb-common` may define `RiskFactorId` and `RiskFactorSetId` value objects.
They are opaque, stable identifiers. They must not encode regulatory class,
currency, tenor, bucket, modellability, liquidity horizon, or surface
coordinates in shared logic.

The boundary rule is:

```text
Risk-factor identity is shared enough to join run evidence.
Risk-factor interpretation remains package-owned or externally mastered.
```

## Terminology

| Term | Meaning |
| --- | --- |
| `risk_factor_id` | Opaque stable identifier for one run-visible risk factor |
| `risk_factor_set_id` | Opaque stable identifier for a declared set of risk factors |
| Risk-factor master | External source-of-record taxonomy and lifecycle |
| Run-scoped catalog | Immutable snapshot or reference to the risk-factor identifiers used by one run |
| Package projection | Package-owned typed view of the catalog, with FRTB semantics and citations |
| Package factor key | Package-local aggregation key, such as SBM `risk_factor` or CVA `risk_factor_key` |

Package factor keys may be derived from, or linked to, `risk_factor_id`, but
they are not automatically the same object. A GIRR tenor key, an SBM FX
currency key, an IMA RFET risk-factor name, and a CVA SA-CVA risk-factor key
can have different package semantics even when they reference the same
enterprise risk factor.

## Scope owned by `frtb-capital`

### 1. Package-neutral identity primitives

`frtb-common` may define:

- `RiskFactorId`;
- `RiskFactorSetId`;
- small validation helpers for non-empty, normalized, audit-stable text.

These primitives are identity only. They must not contain:

- risk class;
- bucket;
- tenor;
- currency;
- liquidity horizon;
- modellability status;
- quote convention;
- surface axis coordinates;
- regulatory citations;
- package-specific validation rules.

### 2. Run-scoped risk-factor catalog evidence

`frtb-result-store` may persist or reference a run-scoped risk-factor catalog.
The catalog records what the run consumed, not the enterprise source of record.

When the catalog is persisted directly, each catalog row must include:

- `run_id`;
- `risk_factor_id`;
- source system, source file, source row, source hash, and mapping version;
- effective date or snapshot timestamp;
- optional `risk_factor_set_id` membership;
- optional display label and description;
- optional projection references to package-owned records.

The catalog can be stored directly as an artifact or referenced through an
immutable URI and hash. Either way, the committed run must preserve enough
evidence to reproduce joins from time-series, shocks, scenario vectors,
surfaces, and capital-node lineage.

For a committed run, `risk_factor_set_id` must resolve to fixed membership.
Membership changes require a new set id, version, or `membership_hash`. Where a
set drives regulatory behavior, stress analysis, scenario vectors, or shock-set
applicability, the committed run must preserve enough evidence to reconstruct
the exact members.

### 3. Package-owned projections

Each capital package owns the regulatory interpretation of risk factors it
needs.

| Package | Projection responsibility |
| --- | --- |
| `frtb-ima` | RFET mapping, liquidity horizon, modellability/NMRF status, scenario-cube axes, ES/SES risk-factor sets |
| `frtb-sbm` | SBM risk class, risk measure, bucket, tenor/qualifier/factor key, curvature shock applicability, surface linkage |
| `frtb-cva` | SA-CVA risk class, bucket, sensitivity tag, hedge treatment, volatility surface and shock references |
| `frtb-drc` | no general risk-factor projection required; add catalog linkage only for an explicit DRC artifact or semantic profile |
| `frtb-rrao` | no general risk-factor projection required; add catalog linkage only for an explicit RRAO artifact or semantic profile |
| `frtb-orchestration` | top-of-house propagation of component references without changing package interpretation |
| `frtb-result-store` | storage, availability, referential checks, lineage, and read-only retrieval |
| FRTB Navigator | display, filtering, and drill-down only |

Package projections may be implemented as package-local dataclasses, Arrow
adapter outputs, or result records. They must not require sibling imports
between capital packages.

### 4. Artifact reference validation

When a run provides a risk-factor catalog, `frtb-result-store` should validate
that artifact rows and capital nodes using `risk_factor_id` or
`risk_factor_set_id` reference declared catalog entries.

This validation is referential only. If a catalog is declared, unresolved
required references must fail commit. Unresolved optional references may be
persisted only with explicit diagnostics. The result store may reject blank,
malformed, or undeclared references. It must not decide whether a risk factor is
modellable, which liquidity horizon applies, which SBM bucket applies, or which
CVA risk class applies.

### 5. Navigator read model

The FRTB Navigator may use catalog labels, package projections, and lineage
links to display:

- which risk factors are attached to a selected capital row;
- which time series, shocks, scenario vectors, or surfaces reference those
  risk factors;
- whether the run exposes available, no-data, unsupported, provisional, stale,
  or failed-validation evidence.

The Navigator must not infer risk-factor classifications from names, labels,
or artifact row patterns. It must not join unvalidated strings client-side when
the result store does not expose the relationship.

## Scope explicitly outside `frtb-capital`

The following remain outside this repository:

- enterprise risk-factor taxonomy design;
- vendor symbology normalization;
- golden-source lifecycle and approval workflow;
- curve, surface, and instrument mapping governance;
- cross-asset risk-factor ontology management;
- live risk-factor distribution services;
- long-history market-data storage;
- intraday refresh and subscription handling.

External platforms may provide catalog snapshots, mapping tables, Arrow
handoffs, object-store references, hashes, and source-row identifiers. The
suite records and validates the run-scoped view it consumed.

## Design rules

### Rule 1: identity is opaque

Code must not parse `risk_factor_id` strings to derive regulatory meaning.
Regulatory meaning comes from package projections or external catalog metadata
captured as run evidence.

### Rule 2: package projections are the semantic boundary

IMA, SBM, CVA, DRC, and RRAO may interpret the same `risk_factor_id`
differently for their own regulatory calculations. That interpretation lives
in package-owned contracts, validators, profiles, and cited tests.

### Rule 3: common code must stay semantic-light

`frtb-common` may provide identity value objects and deterministic hashing or
normalization helpers. It must not define an FRTB-wide `RiskFactorDefinition`
with liquidity horizon, bucket, modellability, surface, or regulatory-rule
fields.

### Rule 3.1: `RiskFactorId` is additive

Introducing `RiskFactorId` must not rename or replace existing package-local
calculation keys such as SBM `risk_factor`, IMA `risk_factor_name`, or CVA
`risk_factor_key`. Those fields remain package-owned calculation and
aggregation keys unless a package-specific ADR changes them.

Shared work should add optional lineage/reference fields, package bridges, and
result-store catalog links first. Existing package behavior must not be
rewritten merely to adopt the common identifier.

### Rule 4: result-store joins are explicit

Artifact schemas that include `risk_factor_id` or `risk_factor_set_id` must
state whether those fields are required, optional, or unavailable for the
semantic profile. If present, references should resolve to the run-scoped
catalog when a catalog is supplied.

### Rule 5: shock sets require risk-factor membership

A shock workflow may use single `shock_id` rows for simple evidence display.
Before a shock set drives regulatory behavior, stress analysis, or
multi-factor audit, its semantic profile must declare either:

- explicit affected `risk_factor_id` members; or
- a `risk_factor_set_id` resolving to a run-scoped catalog.

The suite must not infer shock applicability from shock names or UI filters.

### Rule 6: time-series profiles declare risk-factor grain

Every time-series semantic profile must declare its risk-factor grain:

- single `risk_factor_id`;
- `risk_factor_set_id`;
- desk-level aggregate;
- portfolio-level aggregate;
- no risk-factor dimension.

The profile must also declare ordering, frequency or event grain, required
value names, units, missing-date policy, observation-window rules where
applicable, and which package owns any derived status.

### Rule 7: surfaces distinguish identity from coordinates

`surface_id` and `surface_point_id` identify persisted surface evidence.
`risk_factor_id` links that evidence to the run-scoped risk-factor catalog
when available. Surface axis names, axis values, interpolation policy, and
quote convention are metadata, not substitutes for risk-factor identity.

## Semantic profile minimums

Any risk-factor-aware semantic profile must declare:

| Required item | Purpose |
| --- | --- |
| Owner package | Identifies where regulatory interpretation lives |
| Artifact family and schema | Identifies the storage/read model |
| Risk-factor grain | Identifies single factor, set, desk, portfolio, or none |
| Required reference fields | Identifies required IDs and nullable IDs |
| Projection source | Identifies package projection or external catalog reference |
| Validation rules | Defines referential and package-specific checks |
| Regulatory citations | Required when status or classification affects capital explanation |
| Navigator behavior | Defines what the UI may display and what it must not infer |

## Examples

### In scope

- An IMA RFET profile maps external risk-factor rows into package-local
  `RiskFactorDefinition` records with liquidity horizon and RFET observation
  time-series references.
- An SBM curvature profile records that `shock-sbm-curvature-up` applies to a
  declared `risk_factor_set_id` and package-local curvature factor keys.
- A CVA sensitivity record stores a package-local `risk_factor_key` plus
  `volatility_surface_id`, `volatility_surface_point_id`, and optional
  `risk_factor_id` lineage.
- A result-store artifact row with `risk_factor_id=rf-girr-usd-5y` validates
  against the run-scoped catalog and can be joined to RFET, shock, and surface
  evidence.
- The Navigator displays the package-provided label, risk class, and status for
  a selected row without deriving them from the identifier string.

### Out of scope

- Building an enterprise risk-factor taxonomy service.
- Normalizing vendor symbology across all asset classes.
- Inferring SBM buckets by parsing `risk_factor_id`.
- Inferring IMA liquidity horizons in the result store.
- Letting the UI decide RFET/modellability status from raw observations.
- Treating package factor keys as globally stable enterprise identifiers.

## Enforcement

| Rule | Enforcement |
| --- | --- |
| Common IDs remain semantic-light | `frtb-common` tests and review for absence of package-specific fields |
| Package projections own interpretation | Package-local tests, citations, and no sibling imports |
| Artifact references resolve to declared catalogs when supplied | Result-store schema/API tests |
| Shock sets declare affected risk factors before driving behavior | Semantic-profile tests for shock-set contracts |
| Time-series profiles declare grain and status owner | Semantic-profile documentation and package tests |
| Navigator does not infer classifications | Frontend tests and review against result-store payloads |

Changes that add risk-factor-aware behavior without a profile, owner, tests,
and citations should be rejected or moved behind a new ADR-backed boundary.

## Consequences

**Positive:**

- Time-series, shocks, scenario vectors, and surfaces can join consistently
  through stable run-scoped risk-factor identity.
- Packages keep their regulatory semantics and citations instead of sharing a
  brittle generic risk-factor model.
- Result-store can validate references and serve audit evidence without
  becoming a master-data system.
- Navigator behavior becomes display-driven and auditable rather than
  inference-driven.

**Negative:**

- There is one more explicit contract to maintain when adding artifact
  families.
- Some integration workflows require both an external risk-factor master and a
  package-local projection.
- Existing package-local names and keys may need gradual linkage to
  `risk_factor_id` rather than wholesale replacement.

**Risks to guard against:**

- Treating `risk_factor_id` text as parseable business logic.
- Creating a component-specific risk-factor ontology in `frtb-common`.
- Letting result-store invent package classifications.
- Letting package-local factor keys masquerade as enterprise identifiers.
- Joining artifacts in the UI when the result-store has not exposed a validated
  relationship.

## Follow-up work

- Add `RiskFactorId` and `RiskFactorSetId` value objects to `frtb-common`.
- Add a result-store risk-factor catalog artifact or immutable catalog-reference
  contract.
- Add result-store referential checks for `risk_factor_id` and
  `risk_factor_set_id` when a run-scoped catalog is present.
- Define semantic profiles for RFET observations, PLAT vectors, SBM shock
  sets, scenario vectors, and surface grids.
- Link IMA risk-factor master mapping outputs to the run-scoped catalog.
- Add optional package-local references from SBM and CVA factor keys to
  `risk_factor_id` without changing their regulatory aggregation keys.
- Update the FRTB Navigator metadata contract to display risk-factor catalog
  labels and package projections without client-side inference.

## References

- [ADR 0011](0011-core-runtime-dependency-policy.md): core runtime dependency
  policy.
- [ADR 0012](0012-capital-impact-attribution.md): attribution-ready audit and
  branch metadata.
- [ADR 0023](0023-arrow-tabular-handoff-boundary.md): Arrow tabular handoff
  boundary.
- [ADR 0045](0045-canonical-batch-pipeline-with-adapter-ingress.md): canonical
  batch pipeline with adapter ingress.
- [ADR 0049](0049-result-evidence-and-market-data-platform-boundary.md): result
  evidence and market data platform boundary.
- [ADR 0051](0051-rfet-observation-and-vendor-mapping-evidence-boundary.md):
  RFET observation and vendor mapping evidence boundary.
- [`docs/modules/frtb-result-store/FRTB_NAVIGATOR_METADATA_CONTRACT.md`](../modules/frtb-result-store/FRTB_NAVIGATOR_METADATA_CONTRACT.md):
  FRTB Navigator metadata read-model contract.
- #1072: time-series, shocks, and surface metadata architecture.
