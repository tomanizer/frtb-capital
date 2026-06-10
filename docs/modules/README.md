# FRTB Module Documents

This directory is the suite-level home for capital component documentation. It
contains implemented IMA and RRAO module documentation, DRC partial-runtime
planning and requirements, partial-runtime front doors for SBM and CVA, and
suite support documentation for common, orchestration, and result storage.

For market risk Standardised Approach, SA is the composed total `SBM + DRC +
RRAO` under Basel MAR20.4. The implementation taxonomy therefore uses three
component packages: `frtb-sbm`, `frtb-drc`, and `frtb-rrao`. See the
[Standardised Approach composition note](standardised-approach.md).

## Teaching Entrypoints

For a first integration pass, start with the suite-level
[client integration guide](../CLIENT_INTEGRATION.md), run `make demo` from the
repo root, then follow the package journey for the component you are wiring.
The journey documents are the user-facing bridge between raw input shapes,
public package entrypoints, orchestration handoffs, attribution, and result
storage.

| Package | Journey | Demo |
| --- | --- | --- |
| IMA | [packages/frtb-ima/docs/PACKAGE_JOURNEY.md](../../packages/frtb-ima/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-ima/examples/run_demo.py` |
| SBM | [packages/frtb-sbm/docs/PACKAGE_JOURNEY.md](../../packages/frtb-sbm/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-sbm/examples/run_demo.py` |
| DRC | [packages/frtb-drc/docs/PACKAGE_JOURNEY.md](../../packages/frtb-drc/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-drc/examples/run_demo.py` |
| RRAO | [packages/frtb-rrao/docs/PACKAGE_JOURNEY.md](../../packages/frtb-rrao/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-rrao/examples/run_demo.py` |
| CVA | [packages/frtb-cva/docs/PACKAGE_JOURNEY.md](../../packages/frtb-cva/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-cva/examples/run_demo.py` |
| Orchestration | [packages/frtb-orchestration/docs/PACKAGE_JOURNEY.md](../../packages/frtb-orchestration/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-orchestration/examples/run_demo.py` |

Use `make examples-check` for CI-equivalent example smoke coverage and
`make notebooks-check` for the current notebook smoke suite.

| Module | Package status | Module docs | Regulatory requirements | PRD | Workable requirements |
| --- | --- | --- | --- | --- | --- |
| Common | Shared primitives | [frtb-common/README.md](frtb-common/README.md) | N/A | N/A | N/A |
| IMA | Implemented | [frtb-ima/README.md](frtb-ima/README.md) | [frtb-ima/REGULATORY_REQUIREMENTS.md](frtb-ima/REGULATORY_REQUIREMENTS.md) | [frtb-ima/PRD.md](frtb-ima/PRD.md) | [packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml](../../packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml) |
| SBM | Partial runtime; BASEL_MAR21 delta, vega, and curvature across all seven risk classes (row, batch, and Arrow paths) | [frtb-sbm/README.md](frtb-sbm/README.md) | [frtb-sbm/REGULATORY_REQUIREMENTS.md](frtb-sbm/REGULATORY_REQUIREMENTS.md) | [frtb-sbm/PRD.md](frtb-sbm/PRD.md) | [packages/frtb-sbm/docs/requirements/BASEL_FRTB_SBM.yml](../../packages/frtb-sbm/docs/requirements/BASEL_FRTB_SBM.yml) |
| DRC | Partial runtime; U.S. NPR 2.0 and Basel MAR22 non-securitisation, securitisation non-CTP, and CTP row/batch paths | [frtb-drc/README.md](frtb-drc/README.md) | [frtb-drc/REGULATORY_REQUIREMENTS.md](frtb-drc/REGULATORY_REQUIREMENTS.md) | [frtb-drc/PRD.md](frtb-drc/PRD.md) | [packages/frtb-drc/docs/requirements/BASEL_FRTB_DRC.yml](../../packages/frtb-drc/docs/requirements/BASEL_FRTB_DRC.yml) |
| RRAO | Implemented for supported canonical inputs | [frtb-rrao/README.md](frtb-rrao/README.md) | [frtb-rrao/REGULATORY_REQUIREMENTS.md](frtb-rrao/REGULATORY_REQUIREMENTS.md) | [frtb-rrao/PRD.md](frtb-rrao/PRD.md) | [packages/frtb-rrao/docs/requirements/BASEL_FRTB_RRAO.yml](../../packages/frtb-rrao/docs/requirements/BASEL_FRTB_RRAO.yml) |
| CVA | Partial runtime; reduced/full BA-CVA, supported SA-CVA delta/vega, and mixed carve-out paths implemented | [frtb-cva/README.md](frtb-cva/README.md) | [frtb-cva/REGULATORY_REQUIREMENTS.md](frtb-cva/REGULATORY_REQUIREMENTS.md) | [frtb-cva/PRD.md](frtb-cva/PRD.md) | [packages/frtb-cva/docs/requirements/BASEL_FRTB_CVA.yml](../../packages/frtb-cva/docs/requirements/BASEL_FRTB_CVA.yml) |
| Orchestration | Implemented for suite arithmetic, SA composition, IMA and CVA summary handoffs, jurisdiction-family guards, and top-of-house aggregation | [frtb-orchestration/README.md](frtb-orchestration/README.md) | [frtb-orchestration crosswalk](../regulatory/crosswalk/frtb-orchestration.yml) | N/A | [frtb-orchestration/PUBLIC_API.md](frtb-orchestration/PUBLIC_API.md) |
| Result store | Partial; local DuckDB/Parquet run store for capital graph drilldown, artifacts, lineage, and attribution | [frtb-result-store/README.md](frtb-result-store/README.md) | N/A | [frtb-result-store/DETAILED_DESIGN.md](frtb-result-store/DETAILED_DESIGN.md) / [issue plan](frtb-result-store/ISSUE_BREAKDOWN.md) | [frtb-result-store/PUBLIC_API.md](frtb-result-store/PUBLIC_API.md) |

## Implementation Pattern

The `frtb-sbm`, `frtb-drc`, `frtb-rrao`, and `frtb-cva` packages follow one
implementation pattern. `frtb-common` owns package-neutral mechanics: shared
status metadata, explicit unsupported/unimplemented exception types,
Arrow-backed tabular handoff primitives, package-neutral CRIF-to-Arrow
normalization, JSON-ready serialization helpers, regulatory citation test
helpers, and the `ComponentCapitalSummary` contract for standardised-component
orchestration. Capital packages may import from `frtb-common`; they must not
import from each other.

Rule-profile semantics, sign conventions, capital audit-record structures,
business calendars, and regulatory parameters stay in the owning component or
orchestration package unless a focused cross-cutting ADR extracts a neutral
contract into `frtb-common`.

Regulatory parameters belong in cited package policy objects or versioned rule
profiles, not scattered through calculation modules. A profile or policy object
records its identity, source citations, and enough lineage to reproduce the
calculation. Calculation code receives explicit typed inputs and policy
configuration; it must not look up global constants by regime name inside
kernels.

Each package owns a canonical input model at its public boundary. Importers,
CRIF mappers, examples, and future vendor adapters must translate into that
model before calculation starts. Shared CRIF-to-Arrow normalization may own
column discovery, alias normalization, primitive coercion, rejected-row
partitioning, and diagnostics, but package adapters still own RiskType mapping
and regulatory validation. Public validation rejects missing identities,
duplicate keys unless aggregation is explicit, unknown enum values, non-finite
numbers, implicit sign conventions, and unsupported regulatory features.

Calculation modules are pure kernels: typed inputs in, frozen result objects
out. Database reads, Excel output, dashboard writes, persisted manifests, and
result-store writes belong in adapters, `frtb-orchestration`, or
`frtb-result-store`, not in capital package kernels. `frtb-orchestration` owns
composed SA capital, IMA fallback routing, top-of-house aggregation,
cross-component reconciliation, reporting adapters, and run manifests.

Every capital-producing result must carry enough metadata to reproduce and
explain the number: run id, package id, model version, code version, rule
profile id and hash, input snapshot hash, calculation node, source citation
ids, validation status, and fallback status with reason code where applicable.

Default numerical kernels should use package-owned `numpy` arrays and
deterministic output ordering. Arrow-backed tabular handoffs are allowed at
common IO, CRIF normalization, adapter, and handoff boundaries only; package
kernels must receive typed axes and arrays, not Arrow or dataframe objects.
Avoid row-wise dataframe execution, hidden table shims, mutable model classes
that load/calculate/save/report in one object, and duplicated risk-class
classes where profile data can drive shared aggregation logic. Any new runtime
dependency beyond the approved Arrow batch boundary requires an ADR.
Dataframe and statistical libraries may be used in notebooks, validation, tests,
research, and optional adapters when they do not leak into the capital
calculation runtime path; see
[`ADR 0011`](../decisions/0011-core-runtime-dependency-policy.md) and
[`ADR 0023`](../decisions/0023-arrow-tabular-handoff-boundary.md).

Every calculation feature needs deterministic unit tests, invalid-input tests,
cited golden fixtures, explicit unsupported-feature tests, audit-metadata
tests, and benchmark coverage where realistic bucket or risk-factor counts
matter. When a determinism check or audit control is intended to detect
bit-identical output drift, use raw numeric hashes rather than rounded
floating-point outputs. Document the control intent and any platform or BLAS
limits.

## Research Sources

The documents use these primary references:

- Basel MAR20, standardised approach structure:
  https://www.bis.org/basel_framework/chapter/MAR/20.htm
- Basel MAR21, sensitivities-based method:
  https://www.bis.org/basel_framework/chapter/MAR/21.htm
- Basel MAR22, default risk capital:
  https://www.bis.org/basel_framework/chapter/MAR/22.htm
- Basel MAR23, residual risk add-on:
  https://www.bis.org/basel_framework/chapter/MAR/23.htm
- Basel MAR50, CVA framework:
  https://www.bis.org/basel_framework/chapter/MAR/50.htm
- U.S. NPR 2.0 / Federal Register 91 FR 14952:
  https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959
- CRR3 Regulation (EU) 2024/1623:
  https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng
- EBA residual risk add-on RTS:
  https://www.eba.europa.eu/legacy/regulation-and-policy/regulatory-activities/market-counterparty-and-cva-risk/regulatory-2?version=2021
- Commission Delegated Regulation (EU) 2022/2328:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022R2328

The local reference implementation used for design inspiration is the external
`extract_cva` capital navigator implementation. It is not part of this
repository.

That implementation is treated as an implementation reference only. Regulatory
requirements in these documents are sourced from Basel, U.S. NPR, CRR3, and EBA
references.
