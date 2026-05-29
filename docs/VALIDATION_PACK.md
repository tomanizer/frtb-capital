# Validation Packs

This suite-level page points reviewers to package-specific validation bundles.
Package evidence remains close to the package that owns the calculation model.

## FRTB-IMA

- Formal model documentation pack:
  [`FRTB-IMA model documentation pack`](modules/frtb-ima/model_documentation/README.md)
- Package validation-pack build instructions:
  [`packages/frtb-ima/docs/VALIDATION_PACK.md`](../packages/frtb-ima/docs/VALIDATION_PACK.md)
- Deterministic validation notebooks:
  [`packages/frtb-ima/notebooks/`](../packages/frtb-ima/notebooks/)

The `frtb-ima` validation pack is built from the committed synthetic
`capital_run_v1` fixture. It is not a regulatory report and does not present
final regulatory capital.

## Scaffolded Packages

The following packages are importable scaffolds. They have no model validation
pack yet because they do not calculate capital:

- `frtb-common`
- `frtb-sbm`
- `frtb-drc`
- `frtb-rrao`
- `frtb-cva`
- `frtb-orchestration`

Validation-pack pages should be added when these packages move from scaffold to
implemented calculation. The orchestration validation pack should reconcile the
composed SA total from SBM, DRC, and RRAO once those components produce typed,
audited outputs.
