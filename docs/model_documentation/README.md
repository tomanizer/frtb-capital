# Model Documentation Packs

This directory is the suite-level home for per-model SR 11-7 / PRA SS 1/23
documentation packs.

Current status:

- [`frtb-ima`](frtb-ima/README.md): implemented package. The formal model
  documentation pack lives here and links to supporting implementation
  evidence under `packages/frtb-ima/docs/` and
  `packages/frtb-ima/notebooks/`.
- `frtb-sa`, `frtb-drc`, `frtb-cva`, `frtb-orchestration`: planned packages;
  model documentation packs should be added as each package is created.

Each pack should cover intended use, conceptual soundness, calculation
derivation, assumptions and limitations, sensitivity analysis, monitoring, and
change history. Package evidence can remain inside the package directory when
that keeps calculation documentation close to the code.
