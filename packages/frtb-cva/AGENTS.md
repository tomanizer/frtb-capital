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
- Mixed SA-CVA with BA-CVA netting-set carve-outs (`MIXED_CARVE_OUT`) per MAR50.8;
  SA-CVA sensitivities must carry context-level evidence for the non-carved slice.
- CCS qualified-index bucket 8, RCS qualified-index buckets 16/17, equity
  qualified-index buckets 12/13, and MAR50.50 routing where metadata is supplied.
- Optional CRIF adapter (`crif.py`), attribution (`attribution.py`), and impact
  (`impact.py`) without changing capital totals.

`US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA` are capital-producing
comparison profiles under audit with profile-owned citations and hashes.
MAR50.9 and analogous CCR-substitution alternatives remain unsupported and
must fail closed.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. The intended end state for CVA runtime
code is:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Use adapters for row, batch, Arrow, and CRIF ingress into package-owned CVA
batches; keep BA-CVA, SA-CVA, and mixed-method validation separate from kernels;
keep capital math in kernel modules without Arrow/dataframe imports; assemble
citations, hashes, audit, and public result records after the kernel; and use
`registry.py` for method, entity, and risk-class dispatch.

Do not add empty stage packages that shadow existing modules. Follow
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) when
introducing `adapters/`, `validation/`, `kernel/`, or `assembly/`.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-rrao`.
- Do not emit successful placeholder capital for unsupported paths.
- Cite specific MAR50 paragraphs for regulatory behaviour.
- Material numerical changes require an ADR and deterministic tests.
- Exposure time-series IDs and volatility surface/surface-point IDs are lineage
  metadata only. Do not import `frtb_result_store`, fetch exposure/surface
  artifacts, infer missing volatilities, or reprice instruments inside CVA
  kernels.
