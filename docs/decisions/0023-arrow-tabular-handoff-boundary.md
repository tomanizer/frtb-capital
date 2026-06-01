# 23. Arrow tabular handoff boundary

Date: 2026-06-01

## Status

Accepted

## Context

The suite needs a high-volume ingestion and handoff path for sensitivities,
default-risk exposures, residual-risk records, CVA exposure tables, input
manifests, and audit/output tables. Row-wise construction of accepted regulatory
dataclasses is not a scalable representation for large books, but moving capital
formulae into dataframe expressions would hide regulatory meaning in grouping,
sorting, null handling, and dtype behavior.

Apache Arrow provides a stable columnar interchange representation for tabular
handoff, including primitive arrays, dictionary arrays, schemas, metadata, and
efficient conversion to NumPy where column chunking, null policy, and dtype
compatibility allow it. The suite still needs package-owned regulatory batches
because package semantics differ: SBM factor keys, DRC issuer aggregation, RRAO
classification, CVA netting-set axes, and IMA scenario cubes are not generic
table operations.

## Decision

`pyarrow` is approved and required for normalized tabular handoff and IO layers.
The concrete dependency and first shared handoff API are implemented under #267
in `frtb_common.handoff`.

Arrow is an interchange and lineage representation, not a calculation-kernel
representation. The required runtime pattern is:

```text
external table / CRIF / file / manifest
    -> pyarrow-backed normalized handoff
    -> package-owned regulatory batch with typed axes and NumPy arrays
    -> NumPy-native capital kernels
    -> frozen audit/result records
```

Allowed `pyarrow` import zones are:

- shared tabular handoff and IO helpers in `frtb-common`;
- package CRIF normalization, vendor adapters, and handoff modules;
- IMA/orchestration manifest or suite-boundary handoff modules;
- benchmark tooling, tests, notebooks, documentation, and generated validation
  aids.

Prohibited zones are:

- formula kernels;
- aggregation kernels;
- scenario-selection kernels;
- weighting, netting, and factor-grid kernels;
- any other hot capital calculation module.

Kernels must not accept `pyarrow.Table`, `pandas.DataFrame`, `polars.DataFrame`,
or similar dataframe objects. Kernels receive package-owned arrays plus typed
axis metadata. Conversion from Arrow to NumPy happens once at the package
boundary, with explicit policies for nulls, chunks, dictionary columns, sorting,
stable row ids, and copy behavior. Where zero-copy conversion is impossible, the
copy must be deliberate and test-covered.

`pandas` and `polars` remain outside the required runtime dependency set. They
may be used in notebooks, validation, research, and optional non-kernel adapters
only under ADR 0011. They must not be used for regulatory formula kernels unless
a later ADR changes this decision.

The repository enforces this boundary through
`scripts/ci/check_kernel_import_boundary.py`, which is part of
`make quality-control`. The gate scans package runtime source modules and fails
when `pyarrow`, `polars`, or `pandas` are imported outside explicit adapter,
CRIF, handoff, IO, or tabular modules.

## Consequences

**Positive:**

- High-volume inputs can move through a columnar handoff without forcing one
  accepted dataclass per source row.
- Regulatory meaning remains visible in package-owned batches and explicit axes
  rather than hidden in dataframe groupby/sort expressions.
- Package kernels stay NumPy-native and can keep deterministic audit records,
  branch metadata, and attribution-ready intermediate records.
- The suite gets a single handoff vocabulary while still allowing SBM, DRC,
  RRAO, CVA, and IMA to own their domain semantics.
- Quality-control fails early if dataframe or Arrow imports leak into hot
  calculation modules.

**Negative:**

- Package adapters must own explicit Arrow-to-NumPy conversion and validation
  code instead of passing labelled tables directly into calculations.
- Some conversions will copy data where Arrow chunking, nulls, dictionary
  encoding, or dtype incompatibility prevents zero-copy NumPy access.
- Developers must update the import-boundary allowlist when adding a new
  legitimate adapter or handoff module name.

## Follow-up Work

- #267 adds the minimal `frtb-common` Arrow-backed normalized tabular handoff
  contract and concrete `pyarrow` dependency.
- #268 introduces the first SBM package-owned batch for GIRR delta.
- #269 adds shared CRIF-to-Arrow normalization while keeping package-specific
  risk mappings outside common.
- #270 and #271 roll the pattern through the remaining SBM paths and other
  packages after hotspot triage.
- #274 aligns IMA and orchestration handoff boundaries without moving IMA
  scenario-cube kernels away from NumPy.

## References

- [ADR 0011](0011-core-runtime-dependency-policy.md): core runtime dependency
  policy.
- [ADR 0012](0012-capital-impact-attribution.md): attribution-ready audit and
  branch metadata.
- #262: high-volume Arrow transition umbrella.
- #266: ADR issue for this boundary and kernel import enforcement.
