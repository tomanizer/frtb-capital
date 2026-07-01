# AGENTS.md — frtb-rrao

Follow the suite-level portable worktree policy in
[`../../AGENTS.md`](../../AGENTS.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

`frtb-rrao` owns the Standardised Approach residual risk add-on component.

## Current status

The package has an implemented v1 canonical-input RRAO calculation path for
Basel MAR23, U.S. NPR 2.0 proposed section `__.211`, and the EU CRR3 Article
325u comparison profile. It must still fail explicitly for unsupported profiles,
unsupported evidence paths, and ambiguous classification evidence.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. The intended end state for RRAO runtime
code is:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Use adapters for row, batch, Arrow, and CRIF-like ingress into the package-owned
RRAO batch; keep classification and evidence validation separate from kernels;
keep residual-risk add-on math in kernel modules without Arrow/dataframe imports;
assemble citations, hashes, audit, and public result records after the kernel;
and use `registry.py` for profile and factor-type dispatch.

Do not add empty stage packages that shadow existing modules. Follow
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) when
introducing `adapters/`, `validation/`, `kernel/`, or `assembly/`.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-cva`.
- Do not emit successful placeholder capital for unmapped regulatory paths.
- Preserve zero-capital exclusion records as auditable lines rather than
  dropping input rows.
- Organisation scope IDs are metadata only. Preserve supplied
  `CalculationScope` values on audit/results, but keep enterprise hierarchy
  traversal and rollups in `frtb-result-store`; see
  [`../../docs/HIERARCHY_OWNERSHIP.md`](../../docs/HIERARCHY_OWNERSHIP.md).
