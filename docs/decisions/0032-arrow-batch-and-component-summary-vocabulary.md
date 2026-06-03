# 32. Arrow/batch and component-summary public vocabulary

Date: 2026-06-03

## Status

Proposed

## Context

ADR 0023 established the Arrow tabular ingest boundary and ADR 0029 unified the
Standardised Approach (SA) orchestration contract. Both ADRs used **handoff** as
the umbrella term for two different concepts:

1. **Tabular ingest** — `pyarrow` tables normalized to accepted/rejected column
   partitions, then converted to package-owned NumPy batches (ADR 0023).
2. **Composition** — a thin projection of a package `*CapitalResult` for suite
   aggregation, without importing sibling package internals (ADR 0029).

Library users and reviewers routinely conflate these paths because the same word
appears in module names (`arrow_handoff.py`), types (`NormalizedTabularHandoff`),
builders (`build_rrao_batch_from_handoff`), orchestration parameters
(`sbm_handoff`), and documentation. **Handoff** does not tell a caller whether
they need a columnar table, a batch object, or a capital summary.

The suite already documents the correct runtime split in ADR 0023 (Arrow → batch
→ kernels) and ADR 0029 (`to_orchestration_handoff` → `ComponentResultHandoff`).
What is missing is a **single public vocabulary** that matches those pipelines and
can be applied consistently across `frtb-common`, SBM, DRC, RRAO, CVA, IMA, and
orchestration.

An audit in 2026-06-03 also found **surface inconsistencies** that this ADR
clarifies but does not require fixing in one step:

- SBM exposes many tabular APIs on `frtb_sbm.arrow_handoff` while some siblings
  also re-export tabular symbols from the package root.
- SBM adds `calculate_sbm_capital_from_*_handoff` shortcuts; other components use
  normalize → batch → `calculate_*_from_batch` only.
- Test and benchmark filenames mix `arrow_handoff`, `arrow_batch`, and
  `test_arrow_handoff` without a single pattern.

Issue **#401** is reducing bloated top-level `__init__.py` exports. This ADR must
not fight that work by mandating broad root re-exports of every tabular symbol.

This ADR records a **naming policy** and target public names. It does not change
numerical outputs, Arrow policies, orchestration validation rules, or
`frtb_common.batch_arrays` (see Non-goals).

## Decision

Adopt two explicit vocabulary families. **Do not use "handoff" in new public
APIs** after the migration window closes. During migration, **handoff** may appear
only as a documented deprecated alias in docstrings and changelog fragments.

### 1. Arrow path (columnar ingest and batches)

Use **arrow** and **batch** for anything that touches `pyarrow`, normalized
tabular partitions, or package-owned NumPy batch construction.

**Canonical pipeline:**

```text
pa.Table
  -> normalize_*_arrow_table(...)     -> NormalizedArrowTable
  -> build_*_batch_from_arrow(...)    -> *Batch
  -> calculate_*_from_batch(...)      -> *CapitalResult | *BatchCapitalCalculation
```

#### Normalized container name

**`NormalizedArrowTable`** is the target public name for today's
`NormalizedTabularHandoff`.

It is **not** a bare `pa.Table`. It is a frozen record of **normalized Arrow
table partitions** plus ingest metadata:

- `accepted` and optional `rejected` as `pyarrow.Table` column subsets;
- adapter `diagnostics`;
- `source_hash`, `metadata`, and `row_id_column`.

Alternatives considered (`NormalizedArrowIngest`, `NormalizedArrowDataset`,
`NormalizedArrowPartition`) were rejected for public API stability: **table**
matches how callers already reason about `accepted`/`rejected`, as long as docs
state that the type wraps partitioned Arrow tables, not a single unvalidated
input table.

#### Naming rules

| Role | Convention | Notes |
|------|------------|--------|
| Normalize | `normalize_<domain>_arrow_table` | Keep existing domain segments (`girr_delta`, `drc_nonsec`, `rrao`, `ima_scenario_metadata`, …). Optional `sbm_` prefix is **not** required when risk class and measure are already in the name. |
| Normalized container | `NormalizedArrowTable` | See above. |
| Batch build | `build_<entity>_batch_from_arrow` | Replaces `build_*_batch_from_handoff`. |
| Row/dict build | `build_<entity>_batch_from_<rows>` | Unchanged (`from_positions`, `from_sensitivities`, `from_columns`, …). |
| Column contract | `<DOMAIN>_ARROW_COLUMN_SPECS` | New specs use this form; `*_HANDOFF_COLUMN_SPECS` become deprecated aliases. |
| Hash helper | `normalized_arrow_table_hash` | Replaces `normalized_handoff_hash` (same digest semantics). |
| Shared errors | `NormalizedTableError` | Replaces `TabularHandoffError`. Raised for shared **normalization and tabular invariant** failures (schema, null policy, partitioning), not only raw Arrow IO. `ArrowTableError` is reserved for a future narrower class if a distinct Arrow-only error family is needed. |
| Adapter modules | `arrow_batch.py` or `arrow_adapter.py` | Optional **late** rename from `arrow_handoff.py` (see Implementation sequencing). |
| CRIF shim | `normalize_<slice>_crif_arrow_table` | Unchanged pattern (e.g. SBM `normalize_girr_delta_crif_arrow_table`); CRIF is a source format, not a synonym for Arrow. |

**Prohibited on the Arrow path:** names that suggest orchestration or suite
composition (`orchestration`, `summary`, `component_summary`) on functions or
types that accept `pa.Table` or `NormalizedArrowTable`.

**Kernels:** unchanged from ADR 0023 — no `pyarrow` in hot calculation modules.

### 2. Composition path (SA and CVA suite aggregation)

Use **summary**, **result**, and **composition** for projections consumed by
`frtb-orchestration`. **Never use arrow** in these symbols.

**Meaning of summary:** a **frozen, package-neutral projection for suite
aggregation** — identity, `total_capital`, lineage hashes, counts, citations, and
warnings sufficient for orchestration to compose SA or recognise CVA totals. It
is **not** a full audit report, **not** a desk-level breakdown, and **not** a
substitute for the owning package's `*CapitalResult`.

**Canonical pipeline:**

```text
*CapitalResult
  -> to_component_summary(...)         -> ComponentCapitalSummary
  -> compose_standardised_approach_capital(sbm_summary=..., drc_summary=..., rrao_summary=...)
```

**Naming rules:**

| Role | Convention | Notes |
|------|------------|--------|
| SA summary type | `ComponentCapitalSummary` | Replaces `ComponentResultHandoff`. |
| SA summary error | `ComponentSummaryError` | Replaces `ComponentHandoffError`. |
| SA projection | `to_component_summary(result)` | Replaces `to_orchestration_handoff`. |
| Orchestration parameters | `sbm_summary`, `drc_summary`, `rrao_summary` | Replaces `sbm_handoff`, `drc_handoff`, `rrao_handoff`. |
| CVA suite contract | `CvaCapitalSummary` | Replaces `CvaResultHandoff` in orchestration. |
| CVA recognition | `to_cva_summary(result)` or `recognise_cva_summary` | Replaces `recognise_cva_result` when a typed adapter lands in `frtb-cva`; until then, orchestration may keep one recognise helper with a deprecated alias. |

**Prohibited on the composition path:** `arrow`, `batch`, `normalize_*_arrow_table`,
and `pyarrow` in orchestration-facing public names.

### 3. Deprecated "handoff" alias policy

| Phase | Public code | Documentation |
|-------|-------------|---------------|
| **M1 — aliases** | New symbols are **canonical**; old names are thin deprecated aliases (see Class and function aliases below). `__all__` lists new names first. | New examples use Arrow/summary vocabulary only; old names documented as deprecated. |
| **M2 — warnings** | In-repo call sites updated to new names. `DeprecationWarning` on old public symbols. | ADR 0023/0029 cross-links updated; prose uses "Arrow ingest" and "component summary" where describing behavior. |
| **M3 — removal** | Old public names removed in a `release/*` PR per ADR 0015. | "Handoff" removed from public API docs except historical ADR titles and changelog entries. |
| **M4 — module paths (optional)** | File renames (`arrow_handoff.py`, `handoff.py`, `frtb_common.handoff`) after symbols and docs stabilize. | Crosswalk YAML and import-boundary allowlists updated in the same PR as renames. |

**Internal** private names, benchmark JSON keys, and git branch names may lag M2;
they must be gone before M3. Module renames are **M4**, not mixed into M1/M2.

#### Class and function aliases (required pattern)

Aliases must not make the **old** name the runtime canonical type.

**Correct:** define `NormalizedArrowTable` (subclass or renamed implementation),
then `NormalizedTabularHandoff = NormalizedArrowTable` with a deprecation
docstring so `type(obj).__name__` is `NormalizedArrowTable` for instances created
through the canonical constructor path.

**Incorrect:** `NormalizedArrowTable = NormalizedTabularHandoff` as the only
definition — that leaves `type(obj).__name__` as `NormalizedTabularHandoff` and
undermines migration.

The same rule applies to `ComponentCapitalSummary` vs `ComponentResultHandoff`
and to function aliases (`build_rrao_batch_from_arrow` as the real function;
`build_rrao_batch_from_handoff` as `warnings.deprecated` wrapper or assigned alias
that points to it).

### 4. Public discoverability vs root re-exports

Aligned with **#401** (narrower top-level surfaces):

- Packages **must** document **discoverable public module paths** for the Arrow
  path (e.g. `frtb_rrao.arrow_handoff` today; `frtb_rrao.arrow_batch` after M4)
  in README / PUBLIC_API / package `AGENTS.md`.
- Packages **may** re-export stable tabular or summary entrypoints from
  `__init__.py` **only when those symbols are already part of the package's
  public contract** and #401 keeps them on the curated export list.
- This ADR **does not** require expanding root `__all__` to match every sibling's
  export set. **SBM** is not required to mirror DRC/RRAO root tabular exports in
  the first migration tranche; the pilot validates ergonomics first.

SBM may retain `calculate_sbm_capital_from_*_arrow` as **optional convenience**
wrappers (batch + calculate in one call) when renamed from `*_handoff`, provided
each wrapper documents that it is sugar over `build_*_batch_from_arrow` +
`calculate_sbm_capital_from_*_batch`. New code should prefer the two-step
pipeline.

### 5. Future CI guard (migration-lintable)

After M1 lands in `frtb-common`, add a quality-control check (exact script TBD)
that **fails on new public symbols** matching `handoff` / `Handoff` outside:

- deprecated alias definitions explicitly listed in an allowlist file;
- `docs/decisions/` historical ADR filenames and titles;
- changelog fragments describing deprecation.

The check does not rewrite existing symbols until M3; it prevents new drift.

### 6. Relationship to prior ADRs

- **ADR 0023** — unchanged boundary (Arrow adapters vs NumPy kernels). This ADR
  only renames the tabular layer; import-boundary allowlists gain new module
  basenames only when **M4** renames land.
- **ADR 0029** — unchanged composition semantics and `StandardisedComponent`
  slot validation. This ADR renames types and parameters only.
- **ADR 0015** — breaking renames ship via `release/*` after deprecation; feature
  PRs add aliases and changelog fragments, not version bumps.
- **#401** — root export curation takes precedence over blanket re-export parity
  mandated by this ADR.

## Symbol mapping (reference)

### `frtb-common` (tabular)

| Current | Target |
|---------|--------|
| `NormalizedTabularHandoff` | `NormalizedArrowTable` (canonical class) |
| `TabularHandoffError` | `NormalizedTableError` |
| `normalized_handoff_hash` | `normalized_arrow_table_hash` |
| `normalize_arrow_table` | unchanged |
| `validate_arrow_table` | unchanged |
| `frtb_common.handoff` | optional M4: `frtb_common.arrow_table` or `arrow_ingest` |

### `frtb-common` (composition)

| Current | Target |
|---------|--------|
| `ComponentResultHandoff` | `ComponentCapitalSummary` (canonical class) |
| `ComponentHandoffError` | `ComponentSummaryError` |
| `frtb_common.component_handoff` | optional M4: `frtb_common.component_summary` |

### Per-package (tabular) — pattern

| Current | Target |
|---------|--------|
| `build_<entity>_batch_from_handoff` | `build_<entity>_batch_from_arrow` |
| `packages/*/src/*_*/arrow_handoff.py` | `arrow_batch.py` (M4 only) |

### Per-package (composition) — pattern

| Current | Target |
|---------|--------|
| `to_orchestration_handoff` | `to_component_summary` |
| `packages/*/src/*_*/handoff.py` | optional M4 rename; not required for M1/M2 |

### Orchestration

| Current | Target |
|---------|--------|
| `sbm_handoff`, `drc_handoff`, `rrao_handoff` | `sbm_summary`, `drc_summary`, `rrao_summary` |
| `CvaResultHandoff` | `CvaCapitalSummary` |
| `frtb_orchestration/cva_handoff.py` | optional M4: `cva_summary.py` |

## Implementation sequencing

**Posture:** accept this ADR as vocabulary/naming policy; keep early PRs small.
Do not commit to root re-export parity or module renames until a pilot proves the
names are ergonomic.

| Step | Scope |
|------|--------|
| **0** | ADR acceptance. |
| **1 — first PR (M1)** | `frtb-common` canonical types/functions with deprecated aliases; one **pilot package** (RRAO or DRC): `build_*_batch_from_arrow`, `to_component_summary`, tests and package docs using new terms only. No file renames. No SBM root export expansion. |
| **2 (M1)** | Remaining packages: function/type aliases and docs; stay within each package's **existing** public export contract and #401 allowlist. |
| **3 (M2)** | In-repo call sites, `DeprecationWarning`, orchestration keyword aliases (`sbm_summary=` with deprecated `sbm_handoff=`), ARCHITECTURE.md, handoff-vocabulary CI guard. |
| **4 (M3)** | `release/*` removal of deprecated public names. |
| **5 (M4, optional)** | Module/file renames, benchmark `schema_version` bumps, crosswalk path updates, kernel import allowlist basenames. |

## Consequences

**Positive:**

- Library users can read a call chain without suite-internal jargon.
- Review and CI can block new `handoff` public symbols during migration.
- Composition vs tabular ingest are lexically separable (`summary` vs `arrow`).
- Compatible with #401: discoverability via documented submodules without
  inflating every `__init__.py`.
- ADR 0023 and 0029 remain behavioral source of truth; no capital number changes.

**Negative:**

- Mechanical churn across aliases, tests, and docs; module renames (M4) remain
  high-touch when undertaken.
- Temporary duplication during M1–M2 increases surface area until M3.
- External consumers of old names need the deprecation window.

**Neutral:**

- Historical ADR titles unchanged; add when 0032 is accepted: "Public names per
  ADR 0032" at the top of ADR 0023 and 0029.
- `frtb_common.batch_arrays` and recent batch-helper public-surface cleanup are
  unchanged (see Non-goals).

## Non-goals

- Changing Arrow null/chunk/dictionary policies or batch validation rules.
- Renaming or reshaping `frtb_common.batch_arrays` (NumPy coercion helpers for
  batches; orthogonal to this vocabulary ADR).
- Merging CVA into `ComponentCapitalSummary` (CVA stays a separate summary type
  outside SA composition).
- Renaming `*Batch`, `calculate_*_from_batch`, or `*CapitalResult` types.
- Renaming `scaffold.py` or `PACKAGE_METADATA`.
- Mandating identical root `__all__` tabular exports across all capital packages.

## References

- [ADR 0023](0023-arrow-tabular-handoff-boundary.md) — Arrow tabular ingest boundary.
- [ADR 0029](0029-unified-standardised-component-handoff-contract.md) — SA
  component summary contract (behavior).
- [ADR 0015](0015-deferred-versioning-and-changelog-fragments.md) — deprecation
  and release assembly.
- [ADR 0011](0011-core-runtime-dependency-policy.md) — `pyarrow` placement.
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) — suite layering (update in M2).
- Issue **#401** — top-level public surface reduction.
