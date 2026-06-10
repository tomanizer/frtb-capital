# ADR 0044 Stage Module Skeleton Constraints

ADR 0044 targets a common capital-package layout:

```text
adapters -> CanonicalBatch -> validation -> kernel -> assembly
```

This note records the Phase 0 skeleton rule for follow-up agents. Empty stage
packages are useful only when they do not change Python import resolution. Do
not add a `validation/` package next to an existing `validation.py` module, or an
`adapters/`, `kernel/`, or `assembly/` package next to an existing same-name
module, unless the same PR moves the old module contents and updates imports.
Creating the directory first can make `import frtb_x.validation` resolve to an
empty package instead of the existing module.

## Safe skeleton policy

- A stage package may be introduced empty only when no same-basename module
  already exists in that package.
- A stage package that would shadow an existing module must be created in the
  same behavior-preserving PR that moves the module contents.
- Public imports must continue to resolve from the package top level until the
  package-specific consolidation issue intentionally changes that API.
- Skeleton PRs must not move regulatory math, validation rules, fixture hashes,
  or public API names.

## Package notes

| Package | Stage layout guidance |
| --- | --- |
| `frtb-sbm` | Create `adapters/`, `kernel/`, and `assembly/` only with their owning moves; create `validation/` only when replacing the existing `validation.py` module. |
| `frtb-cva` | Create stage packages together with the `batch.py` and validation/weighting split in #719 so entity-batch behavior stays covered by package tests. |
| `frtb-drc` | Create `adapters/`, `kernel/`, `assembly/`, and `validation/` with #718 when batch, CTP, securitisation, and scaffold paths are moved atomically. |
| `frtb-rrao` | Create `validation/` only while replacing the current row/batch validation sources in #720; do not shadow `validation.py` ahead of that move. |
| `frtb-ima` | Create RFET and observation validation packages with #721 when focused tests are added for the extracted stages. |
| `frtb-orchestration` | Create validation/projection helpers with #723; keep sibling capital imports out of runtime modules. |
| `frtb-result-store` | Create IO and mart stage modules with #724; keep result-store imports above capital packages only. |

This document is intentionally a constraint note, not a completed stage split.
Package-specific issues remain responsible for the actual module moves, tests,
and duplicate reduction evidence.