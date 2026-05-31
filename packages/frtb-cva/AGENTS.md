# AGENTS.md — frtb-cva

`frtb-cva` owns CVA capital.

## Current status

**Partial implementation.** The delivered slice supports:

- Reduced BA-CVA (`BA_CVA_REDUCED`) per MAR50.14–15.
- SA-CVA across all six delta risk classes and five vega risk classes per
  MAR50.42–MAR50.77 when `sa_cva_approved=True`.
- GIRR, FX, CCS (delta only), RCS, equity, and commodity paths with cited
  bucket tables, risk weights, and correlations.
- CCS qualified-index bucket 8 remains unsupported until the qualified-index issue.

Full BA-CVA hedge recognition, mixed carve-out assembly, and comparison profiles
remain unsupported and must fail closed.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-rrao`.
- Do not emit successful placeholder capital for unsupported paths.
- Cite specific MAR50 paragraphs for regulatory behaviour.
- Material numerical changes require an ADR and deterministic tests.
