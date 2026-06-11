# Consolidation roadmap

Parent ADR: [`0045-canonical-batch-pipeline-with-adapter-ingress.md`](../decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)

This roadmap executes the canonical batch pipeline architecture. The suite is
**non-live**; breaking API changes, wrapper deletion, and hash fixture updates
are expected rather than avoided.

## North star

Every capital package converges to:

```text
adapters/   → canonical batch
validation/ → package rules
kernel/     → cited regulatory math (NumPy only)
assembly/   → results, hashes, audit
registry.py → risk-class / measure / entity dispatch
```

Ingress:

```text
CRIF / Arrow / columns / rows
        ↓
   adapters.*
        ↓
  CanonicalBatch
        ↓
 validation.*
        ↓
   kernel.*
        ↓
  assembly.*
        ↓
  FrozenCapitalResult
```

Egress to orchestration continues through `frtb_common.ComponentCapitalSummary`
(ADR 0029).

## Principles for this roadmap

1. **Delete duplicates; do not deprecate** — remove wrapper matrices and dual
   kernels in the same PR that introduces the registry.
2. **Mechanics to common, semantics local** — finish `stable_json_hash`,
   `batch_arrays`, and `arrow_conversion` migrations before large package
   reshapes.
3. **Split by stage, not risk class** — stop adding `build_<risk>_<measure>_*
   functions.
4. **One package per PR** — exception: `frtb-common` platform PRs precede
   consumer migrations.
5. **Cited formula changes still need ADRs** — structural refactors do not, unless
   outputs change under ADR 0005.

## Phase overview

| Phase | Goal | Exit criterion |
| --- | --- | --- |
| **0** | Policy and scaffolding | ADR 0045 accepted; target layout documented per package |
| **1** | Common handoff platform | No package-local hash/array/Arrow mechanics duplicated |
| **2** | Stage splits | No capital package `batch.py` > 800 LOC mixing stages |
| **3** | Registry collapse | No risk-class wrapper matrix > 3 functions per ingress type |
| **4** | Single kernel | No parallel row/batch business logic in SBM/DRC/RRAO/CVA |
| **5** | Surface trim | Public API is parameterized core + documented ingress adapters |
| **6** | Baseline reset | `code_drift_baseline.json` refreshed; duplicate groups trend < 20 |

---

## Phase 0 — Policy and scaffolding

**Duration:** 1 PR (docs + empty module skeletons)

**Work:**

- Accept ADR 0045.
- Add per-package target layout notes to package `CLAUDE.md` / `AGENTS.md` where
  missing.
- Create empty stage directories or modules (`adapters`, `validation`, `kernel`,
  `assembly`, `registry`) in packages slated for Phase 2 — imports only, no
  behavior move yet.

**Packages:** all capital packages.

**Tracking:** #725 (Phase 0 checklist); close Phase 0 when skeleton PR merges.

---

## Phase 1 — Common handoff platform completion

**Goal:** Packages contain semantics; `frtb-common` contains mechanics.

| Work item | Packages | Delete/replace |
| --- | --- | --- |
| SBM `audit._hash_payload` / `regimes._hash_payload` | `frtb-sbm` | Raw `hashlib` + `json.dumps` |
| Residual `_batch_columns` duplicates | DRC, RRAO, CVA | AST-identical coercion helpers (#707) |
| Arrow conversion migration | SBM, CVA, IMA, RRAO | Local object/float/bool conversion (#708) |
| `frtb_common.crif` stage split (optional) | `frtb-common` | Monolithic normalize pipeline (#722) |

**Exit criterion:** `rg "_hash_payload|hashlib.sha256" packages/*/src` returns
only IMA-special binary envelopes and file-content helpers documented as
package-local.

**Suggested PR order:**

1. `frtb-common` — any missing `batch_arrays` / `arrow_conversion` tests
2. `frtb-sbm` — hash migration (#706)
3. `frtb-drc` → `frtb-rrao` → `frtb-cva` — batch column helper consolidation
4. `frtb-sbm` → `frtb-cva` → `frtb-ima` → `frtb-rrao` — Arrow adapter migration

---

## Phase 2 — Stage splits (monolith decomposition)

**Goal:** Each package's ingress and assembly code is navigable without reading
3000-line files.

### `frtb-sbm` (largest — do first)

| Current module | Target modules | Notes |
| --- | --- | --- |
| `batch.py` (3013 LOC) | `adapters/columns.py`, `adapters/sensitivities.py`, `validation/batch.py`, `assembly/hashes.py`, `registry.py` | Keep `SbmSensitivityBatch` in contracts |
| `arrow_batch.py` (2302 LOC) | `adapters/arrow.py` + registry | Delete 21× normalize/build/calculate wrappers |
| `capital.py` (2068 LOC) | `kernel/portfolio.py`, `registry.py` | Delete 23× `calculate_*_from_*_batch` wrappers |
| `weighted_sensitivity.py` | `kernel/weighting.py` + delta/vega tables | 7 delta dispatchers → 1 table |
| `validation.py` | `validation/sensitivity.py` | Merge duplicate `_require_text` (#711) |

**Tracking:** #717

### `frtb-cva` (second — partial informal split landed)

`batch.py` is now a ~46-line public compatibility facade. Stage logic lives in
`_batch_*`, `_ba_*`, and `_sa_*` modules (~3.2k LOC total). Remaining work:
rename to ADR 0045 stage directories and add entity registry dispatch.

| Current module | Target modules |
| --- | --- |
| `_batch_*` / `_ba_*` / `_sa_*` (informal stages) | `adapters/`, `validation/`, `kernel/`, `assembly/`, `registry.py` |
| `validation.py` | `validation/entities.py` — shared list validator |
| `weighted_sensitivity.py` | `kernel/sa_weighting.py` — vega table (#712) |
| `_payloads.py` | `assembly/payloads.py` — single hash input source |

**Tracking:** #719

### `frtb-drc`

| Current module | Target modules |
| --- | --- |
| `batch.py` (2392 LOC) | `adapters/columns.py`, `adapters/positions.py`, `validation/batch.py`, `assembly/hashes.py` |
| `scaffold.py` | Thin row adapter → canonical batch; delete parallel logic |
| `ctp.py`, `securitisation.py` | `kernel/ctp.py`, `kernel/securitisation.py` + shared `kernel/net_jtd.py` |
| `data_models.py` | Shared `as_dict` serializer (#710) |

**Tracking:** #718

### `frtb-rrao`

| Current module | Target modules |
| --- | --- |
| `batch.py` + `validation.py` | Unified `validation/position.py` for row and batch |
| `_payloads.py` | `assembly/payloads.py` |
| row `capital.py` path | Adapter → batch → single kernel |

**Tracking:** #720

### `frtb-ima`

| Current module | Target modules |
| --- | --- |
| `rfet_evidence.py` | `validation/rfet_qualitative.py`, `validation/rfet_quantitative.py`, `assembly/rfet.py` |
| `arrow_batch.py` | `adapters/arrow.py` |
| `backtesting.py`, `pla.py`, `stress_periods.py` | Shared `validation/observation_windows.py` |

**Tracking:** #721

### `frtb-orchestration` and `frtb-result-store`

Lower priority; apply same stage thinking:

- orchestration: `_suite_validation.py`, `_attribution.py` (#723)
- result-store: split `store_row_io.py`, `marts.py` (#724)

**Phase 2 exit criterion:** No `batch.py` or `arrow_batch.py` over 800 LOC; each
file has a single stage responsibility.

---

## Phase 3 — Registry collapse

**Goal:** Risk-class × measure variation is data, not copied functions.

### SBM registry (highest leverage)

Replace:

- 32× `build_*_from_sensitivities`
- 21× `normalize_*_arrow_table`
- 21× `build_*_from_arrow`
- 22× `calculate_*_from_*_arrow`
- 23× `calculate_*_from_*_batch`
- 11× `input_hash_for_*_batch`

With:

```python
# packages/frtb-sbm/src/frtb_sbm/registry.py
SBM_BATCH_SPECS: Mapping[tuple[SbmRiskClass, SbmRiskMeasure], BatchSpec] = ...
```

Public API after collapse (example target):

```python
build_sbm_batch(sensitivities, risk_class, measure, *, context) -> SbmSensitivityBatch
build_sbm_batch_from_arrow(handoff, risk_class, measure, *, context) -> SbmSensitivityBatch
calculate_sbm_capital(batch, context, controls) -> SbmCapitalResult
input_hash_for_batch(batch) -> str
```

Delete per-risk-class function names; update tests and examples to use enums.

### CVA registry

Replace entity-specific column builders' repeated validate→coerce→freeze steps
with `EntityBatchSpec` table for counterparty, netting set, hedge, SA
sensitivity.

### DRC registry

Replace non-sec / sec / CTP batch builders' shared stages with `DrcPathSpec`
registry; Arrow adapters call the same registry as column adapters.

**Phase 3 exit criterion:** AST duplicate-function groups from wrapper matrices
eliminated; `check_code_drift.py` duplicate groups < 25.

---

## Phase 4 — Single kernel (row path elimination)

**Goal:** One business-logic kernel per package; rows are adapters only.

| Package | Action |
| --- | --- |
| **RRAO** | Delete dual kernel; `calculate_rrao_capital(positions)` → build batch → `calculate_rrao_capital_from_batch` |
| **DRC** | `calculate_drc_capital` in `scaffold.py` → adapter; kernel only in `kernel/` |
| **CVA** | `ba_cva.py` row paths compile to batches where not already |
| **SBM** | Row sensitivity list → `build_sbm_batch(...)`; delete row-only validation duplicates |

**Explicitly keep row adapters** where ergonomics matter for tests and demos,
but they must not contain regulatory math.

**Phase 4 exit criterion:** No function pair `(row_path, batch_path)` implementing
the same cited formula in separate modules.

---

## Phase 5 — Public API and dead-code trim

**Goal:** Small, learnable package surfaces.

**Delete:**

- per-risk-class public aliases superseded by registry + enums
- `accepted_row_dataclasses_materialized` where always zero (DRC, RRAO)
- duplicate test helpers → package `tests/_helpers.py` (#709)
- SBM fixture loader copy-paste → shared loader base (#709)
- storage-only placeholder modules that do not affect capital totals

**Target public entrypoints (illustrative):**

| Package | Core entrypoints |
| --- | --- |
| SBM | `calculate_sbm_capital`, `build_sbm_batch`, `build_sbm_batch_from_arrow`, `to_component_summary` |
| DRC | `calculate_drc_capital`, `build_drc_batch`, `build_drc_batch_from_arrow` |
| RRAO | `calculate_rrao_capital`, `build_rrao_batch`, `build_rrao_batch_from_arrow` |
| CVA | `calculate_cva_capital`, `build_cva_batches`, `build_cva_batches_from_arrow` |
| IMA | unchanged desk-level entrypoints; internal batch adapters only |

Update `docs/CLIENT_INTEGRATION.md`, package `PACKAGE_JOURNEY.md`, examples, and
maturity registry public entrypoint lists in the same PRs.

---

## Phase 6 — Baseline reset and governance

**Work:**

- Run `make drift-baseline` after consolidation waves.
- Refresh `docs/quality/simplification/` with a post-consolidation audit.
- Close phased slices (#706–#709, #714, #717–#724) as phases complete.
- Add `make consolidation-check` (optional) — assert max LOC per stage module and
  registry presence.

**Exit criterion:** `duplicate_function_groups` ≤ 20; no oversized `batch.py` in
capital packages; README/CLIENT_INTEGRATION reflects new API.

---

## Recommended package order

```text
frtb-common (Phase 1)
    ↓
frtb-sbm (Phases 2–4)      ← largest wrapper matrix; sets pattern
    ↓
frtb-cva (Phases 2–4)      ← worst stage mixing
    ↓
frtb-drc (Phases 2–4)
    ↓
frtb-rrao (Phases 2–4)       ← dual kernel elimination
    ↓
frtb-ima (Phases 2–3)        ← stage splits; less registry work
    ↓
frtb-orchestration (Phase 2 light)
    ↓
frtb-result-store (Phase 2 light)
```

Parallel work is allowed only where package boundaries are respected (for
example Phase 1 Arrow migration in independent packages after common helpers
land).

---

## What not to simplify

Do not collapse or abstract away:

- regulatory citation anchors and paragraph references;
- unsupported-profile fail-closed branches;
- explicit correlation/scenario selection logic (SBM MAR21-7);
- DRC HBR, seniority, securitisation evidence gates;
- RRAO evidence classification rules;
- CVA BA-CVA vs SA-CVA vs carve-out routing;
- IMA RFET/NMRF/PLA/backtesting regulatory thresholds;
- orchestration jurisdiction-family guards (ADR 0022);
- kernel import boundary (ADR 0023).

These should become **clearer** after consolidation, not hidden.

---

## Success metrics

| Metric | Current (approx.) | Target |
| --- | ---: | ---: |
| AST duplicate function groups | 36 | ≤ 20 |
| SBM `build_*` wrapper count | 32 | 0 (registry only) |
| Largest `batch.py` LOC | ~3013 | ≤ 800 per stage file |
| Packages with dual row/batch kernels | 4 | 0 |
| Packages on legacy `_hash_payload` | 1 (SBM) | 0 |

---

## GitHub issue map (ADR 0045)

| Phase | Issues |
| --- | --- |
| **Epic** | [#725](https://github.com/tomanizer/frtb-capital/issues/725) |
| **P1** common handoff | [#706](https://github.com/tomanizer/frtb-capital/issues/706) SBM hash · [#707](https://github.com/tomanizer/frtb-capital/issues/707) batch columns · [#708](https://github.com/tomanizer/frtb-capital/issues/708) Arrow · [#714](https://github.com/tomanizer/frtb-capital/issues/714) attribution serializers · [#722](https://github.com/tomanizer/frtb-capital/issues/722) CRIF split (optional) |
| **P2–P4** packages | [#717](https://github.com/tomanizer/frtb-capital/issues/717) SBM · [#719](https://github.com/tomanizer/frtb-capital/issues/719) CVA · [#718](https://github.com/tomanizer/frtb-capital/issues/718) DRC · [#720](https://github.com/tomanizer/frtb-capital/issues/720) RRAO · [#721](https://github.com/tomanizer/frtb-capital/issues/721) IMA · [#723](https://github.com/tomanizer/frtb-capital/issues/723) orchestration · [#724](https://github.com/tomanizer/frtb-capital/issues/724) result-store |
| **P5** trim | [#709](https://github.com/tomanizer/frtb-capital/issues/709) test/fixture helpers |
| **P6** metrics | #725 Phase 6 checklist (duplicate groups ≤ 20) |

Superseded (closed): #705, #716, #544, #710–#713, #715.

Maintainability backlog #508 routes through #725.

## References

- [ADR 0045](../decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
- [Epic #725](https://github.com/tomanizer/frtb-capital/issues/725)
- [`REFACTOR_HOTSPOTS.md`](REFACTOR_HOTSPOTS.md)
- [`simplification/2026-06-04/README.md`](simplification/2026-06-04/README.md)
