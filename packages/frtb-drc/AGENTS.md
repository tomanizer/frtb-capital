# AGENTS.md — frtb-drc

Follow the suite-level portable worktree policy in
[`../../AGENTS.md`](../../AGENTS.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

`frtb-drc` owns the Standardised Approach default risk charge component.

## Current status

The package has a capital-producing partial implementation for U.S. NPR 2.0
non-securitisation, securitisation non-CTP, and correlation trading portfolio
(CTP) DRC row and batch paths, plus Basel MAR22 non-securitisation row and
batch paths, Basel MAR22 securitisation non-CTP and CTP row and batch paths,
and EU CRR3 non-securitisation row and batch paths. EU CRR3 securitisation
non-CTP, EU CRR3 CTP, and all PRA UK CRR paths must fail explicitly until cited
profile mappings and deterministic tests exist.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. The intended end state for DRC runtime
code is:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Use adapters for row, batch, Arrow, and any future CRIF-like ingress into the
package-owned DRC batch; keep profile/path validation separate from kernels;
keep default-risk math in kernel modules without Arrow/dataframe imports;
assemble citations, hashes, audit, and public result records after the kernel;
and use `registry.py` for non-securitisation, securitisation, and CTP dispatch.

Do not add empty stage packages that shadow existing modules. Follow
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) when
introducing `adapters/`, `validation/`, `kernel/`, or `assembly/`.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-rrao`, or `frtb-cva`.
- Do not emit successful placeholder capital.
- Preserve attribution-ready lineage for capital-producing paths: stable record
  ids, deterministic grouping, input citations, and branch metadata.
