# 45. Canonical batch pipeline with adapter ingress

Date: 2026-05-30

## Status

Accepted

## Context

Suite simplification audits (2026-06-02, 2026-06-04) and duplication/readability
reviews (#705–#724) found that capital packages repeat the same mechanical
pipeline many times:

```text
ingress → coerce → validate → hash → kernel → assemble → audit
```

The repetition appears as:

- parallel row, batch, Arrow, and CRIF stacks carrying the same business rules;
- risk-class × measure wrapper matrices (for example ~75 near-identical SBM
  functions across `batch.py`, `arrow_batch.py`, and `capital.py`);
- god-module `batch.py` files mixing adapters, validation, hashing, kernels, and
  result assembly;
- partially migrated handoff mechanics in `frtb-common` while packages still
  carry local copies.

Much of this is **accidental complexity**. Regulatory complexity — profile
matrices, unsupported-feature gates, citation traceability, frozen audit
records — is legitimate and must remain explicit.

The suite is a **non-live prototype**. Backwards compatibility, deprecated public
aliases, and hash-preservation constraints are not binding constraints for
structural refactors unless a change intentionally alters a cited regulatory
formula or audit contract under [ADR 0005](0005-material-change-policy.md).

[ADR 0023](0023-arrow-tabular-handoff-boundary.md) already defines Arrow as an
ingress/interchange layer. [ADR 0029](0029-unified-standardised-component-handoff-contract.md)
already defines orchestration egress. This ADR closes the gap for **in-package
runtime shape**: one canonical internal representation and one pipeline per
capital component.

## Decision

Adopt a **canonical batch pipeline with adapter ingress** as the required
internal architecture for every capital-producing package (`frtb-sbm`,
`frtb-drc`, `frtb-rrao`, `frtb-cva`, and `frtb-ima` where batch ingress
applies).

### 1. One canonical internal model per package

Each capital package must treat its **package-owned regulatory batch** (or
equivalent typed batch record) as the single internal representation entering
the calculation kernel.

Ingress shapes are adapters only:

| Ingress | Role |
| --- | --- |
| Arrow / normalized table | Adapter → canonical batch |
| Column dict / NumPy columns | Adapter → canonical batch |
| CRIF records | Adapter → canonical batch |
| Row-wise dataclasses / positions | Adapter → canonical batch |

Row-wise calculation paths must not maintain a parallel kernel. They must
compile into the canonical batch (or call the same kernel on a batch of size
one) unless an ADR documents a temporary exception.

### 2. Five internal pipeline stages

Capital package runtime code must be organized by stage, not by risk class:

| Stage | Module responsibility | May import |
| --- | --- | --- |
| **Contracts** | Frozen dataclasses, enums, profiles, citation types | `frtb-common` primitives only |
| **Adapters** | CRIF / Arrow / columns / rows → canonical batch | `frtb-common` handoff helpers, `pyarrow` at boundary |
| **Validation** | Package-local input rules and public error types | contracts, adapters output |
| **Kernel** | Regulatory math only; NumPy arrays in, frozen results out | contracts; **no** Arrow, CRIF, or adapter imports |
| **Assembly** | Results, citations, warnings, hashes, audit payloads | contracts, kernel output |

Monolithic `batch.py` files that mix all five stages are **non-compliant** with
this ADR once the consolidation roadmap phase for that package completes.

### 3. Table-driven dispatch instead of wrapper matrices

Mechanical variation across risk class, measure, entity type, or profile slot
must be expressed as **registry tables** or small strategy maps:

```python
# Illustrative pattern — not a mandated API name
REGISTRY[(risk_class, measure)] = BatchSpec(
    validate=...,
    kernel=...,
    citation_defaults=...,
)
```

Public functions may remain as thin named exports, but they must delegate to the
registry. Copy-pasted 15-line wrappers differing only by enum literals are not
an acceptable end state.

### 4. Finish the handoff platform in `frtb-common`

Package adapters must delegate mechanical work to shared helpers where behavior
is package-neutral:

- `frtb_common.stable_json_hash` / `stable_json_dumps` for deterministic digests;
- `frtb_common.batch_arrays` for NumPy coercion mechanics;
- `frtb_common.arrow_conversion` and `frtb_common.arrow_table` for Arrow ingress.

Packages retain:

- schemas and required/optional column rules;
- regulatory interpretation of fields;
- package-local exception types and messages;
- kernel formulae and unsupported-feature policy.

### 5. Delete accidental surface area

The following patterns should be removed rather than deprecated:

- duplicate row and batch kernels implementing the same validation rules;
- storage-only metrics that are always zero (for example
  `accepted_row_dataclasses_materialized` where no path materializes rows);
- placeholder attribution/impact modules that only exist to mirror other
  packages without contributing capital logic;
- test and fixture helpers copied across files when a package-local shared test
  module suffices.

Breaking public API renames and entrypoint consolidation are allowed. Update
tests, examples, notebooks, and maturity registry references in the same change.

### 6. Implementation policy

- **One package per PR** remains the default.
- Cross-package common extraction lands in `frtb-common` first, then package
  migrations follow.
- `frtb-common` must not absorb component-specific regulatory semantics.
- Kernel import boundaries from ADR 0023 remain in force.
- Attribution and audit record compatibility from [ADR 0012](0012-capital-impact-attribution.md)
  remain design goals, but may be refactored structurally while the suite is
  non-live.

### 7. Relationship to ADR 0019

[ADR 0019](0019-reconciliation-helper-extraction-assessment.md) assessed
reconciliation helper extraction and deferred common extraction. That deferral
concerns **numeric tolerance helpers and audit-stage naming**, not the batch
pipeline shape decided here.

Package-local `validate_*_result_reconciliation` functions stay package-local,
but should be split into named audit stages. Shared `isclose` tolerances may
still move to `frtb-common` when convenient; that is orthogonal to this ADR.

## Consequences

**Positive:**

- New risk classes and ingress shapes add registry rows and adapter modules,
  not parallel pipeline copies.
- Reviewers can navigate packages by pipeline stage instead of hunting through
  multi-thousand-line monoliths.
- `frtb-common` becomes a real handoff platform instead of a partial copy
  source.
- Non-live status allows aggressive deletion of wrapper APIs and dual kernels.

**Negative:**

- Large, behavior-preserving refactors across SBM, CVA, and DRC will touch many
  files before the suite stabilizes.
- Short-term churn in public import paths until package layouts settle.
- Registry indirection can hide regulatory branches if tables are not documented
  and cited next to kernel modules.

**Risks to guard against:**

- Hiding regulatory formulae inside opaque generic frameworks — tables must point
  to explicit, cited kernel functions.
- Moving profile semantics or risk weights into `frtb-common` — still forbidden.
- Reintroducing dataframe kernels through the back door — ADR 0023 import gate
  remains mandatory.

## Follow-up work

Phased execution is documented in
[`docs/quality/CONSOLIDATION_ROADMAP.md`](../quality/CONSOLIDATION_ROADMAP.md).

GitHub tracking:

- Epic: [#725](https://github.com/tomanizer/frtb-capital/issues/725)
- Phase slices: see issue map in
  [`CONSOLIDATION_ROADMAP.md`](../quality/CONSOLIDATION_ROADMAP.md#github-issue-map-adr-0045)

## References

- [ADR 0002](0002-monorepo-structure.md): monorepo structure and package boundaries.
- [ADR 0005](0005-material-change-policy.md): material numerical and regulatory
  changes still require ADRs and tests.
- [ADR 0012](0012-capital-impact-attribution.md): attribution-ready results.
- [ADR 0019](0019-reconciliation-helper-extraction-assessment.md): reconciliation
  helper deferral (orthogonal).
- [ADR 0023](0023-arrow-tabular-handoff-boundary.md): Arrow ingress boundary.
- [ADR 0029](0029-unified-standardised-component-handoff-contract.md): orchestration
  egress handoff.
- [ADR 0033](0033-arrow-batch-and-component-summary-vocabulary.md): Arrow ingress
  vocabulary.
- [`docs/quality/simplification/2026-06-04/README.md`](../quality/simplification/2026-06-04/README.md)
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
