# AGENTS.md — frtb-cva

`frtb-cva` owns CVA capital.

## Current status

**Partial implementation.** The delivered slice supports:

- Reduced BA-CVA (`BA_CVA_REDUCED`) per MAR50.14–15.
- SA-CVA GIRR delta (`SA_CVA`) per MAR50.53–57 when `sa_cva_approved=True`.

Full BA-CVA hedge recognition, non-GIRR SA-CVA risk classes, mixed carve-out
assembly, and comparison profiles remain unsupported and must fail closed.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-rrao`.
- Do not emit successful placeholder capital for unsupported paths.
- Cite specific MAR50 paragraphs for regulatory behaviour.
- Material numerical changes require an ADR and deterministic tests.
