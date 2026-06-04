# AGENTS.md — frtb-cva

Follow the suite-level portable worktree policy in
[`../../AGENTS.md`](../../AGENTS.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

`frtb-cva` owns CVA capital.

## Current status

**Implemented package-owned scope.** The delivered slice supports:

- Reduced and full BA-CVA (`BA_CVA_REDUCED`, `BA_CVA_FULL`) per MAR50.14–26.
- SA-CVA across all six delta risk classes and five vega risk classes per
  MAR50.42–MAR50.77 when `sa_cva_approved=True`.
- Mixed SA-CVA with BA-CVA netting-set carve-outs (`MIXED_CARVE_OUT`) per MAR50.8.
- CCS qualified-index bucket 8, RCS/equity qualified-index paths, and MAR50.50
  routing where metadata is supplied.
- Optional CRIF adapter (`crif.py`), attribution (`attribution.py`), and impact
  (`impact.py`) without changing capital totals.

`US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA` are capital-producing
comparison profiles under audit with profile-owned citations and hashes.
MAR50.9 and analogous CCR-substitution alternatives remain unsupported and
must fail closed.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-rrao`.
- Do not emit successful placeholder capital for unsupported paths.
- Cite specific MAR50 paragraphs for regulatory behaviour.
- Material numerical changes require an ADR and deterministic tests.
