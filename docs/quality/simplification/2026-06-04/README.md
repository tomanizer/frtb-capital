# 2026-06-04 simplification audit summary

Audit-only run across all eight workspace packages. Records maintainability
findings and tracking issues; **does not** change runtime calculation code.

Guard: run `python3 scripts/agent_worktree.py guard` in a compliant worktree before
any follow-up implementation PR.

Skill: [`.grok/skills/frtb-simplify-audit/SKILL.md`](../../../../.grok/skills/frtb-simplify-audit/SKILL.md)

## Reports

| Package | Report | Tracking issue |
| --- | --- | --- |
| `frtb-common` | [frtb-common.md](frtb-common.md) | [#537](https://github.com/tomanizer/frtb-capital/issues/537) |
| `frtb-cva` | [frtb-cva.md](frtb-cva.md) | [#538](https://github.com/tomanizer/frtb-capital/issues/538) |
| `frtb-drc` | [frtb-drc.md](frtb-drc.md) | [#539](https://github.com/tomanizer/frtb-capital/issues/539) |
| `frtb-ima` | [frtb-ima.md](frtb-ima.md) | [#540](https://github.com/tomanizer/frtb-capital/issues/540) |
| `frtb-orchestration` | [frtb-orchestration.md](frtb-orchestration.md) | [#541](https://github.com/tomanizer/frtb-capital/issues/541) |
| `frtb-result-store` | [frtb-result-store.md](frtb-result-store.md) | [#542](https://github.com/tomanizer/frtb-capital/issues/542) |
| `frtb-rrao` | [frtb-rrao.md](frtb-rrao.md) | [#543](https://github.com/tomanizer/frtb-capital/issues/543) |
| `frtb-sbm` | [frtb-sbm.md](frtb-sbm.md) | [#544](https://github.com/tomanizer/frtb-capital/issues/544) |

Prior run: [`2026-06-02/`](../2026-06-02/). Live refactor queue:
[`REFACTOR_HOTSPOTS.md`](../../REFACTOR_HOTSPOTS.md).

## Suite-level findings

| P | Scope | Finding | First follow-up |
| --- | --- | --- | --- |
| P0 | package-local | Row + batch duplicate business logic (SBM, DRC, RRAO, CVA) risks hash and capital drift | Regression tests on hashes/totals before merging paths |
| P0 | `frtb-common` | SBM/DRC/CVA still use local `_hash_payload`; RRAO and result-store use `stable_json_hash` | Migrate one package per PR |
| P1 | package-local | SBM: ~20 near-identical `build_*_from_sensitivities` wrappers | Table-driven factory + stable public aliases |
| P1 | package-local | `batch.py` monoliths (~2k–2.5k LOC) in SBM, DRC, CVA | Split: arrays → validate → kernel → assemble |
| P1 | package-local | `frtb-result-store` `io.py` / `model_entities.py` god modules | Split by IO vs entity concerns |
| P1 | package-local | RRAO dual kernel (dataclass vs batch) | Shared validation rules, then kernel decision |
| P2 | package-local | Orchestration `suite.py` / `standardised.py` grew post–ADR 0039 | Extract jurisdiction/attribution helpers |
| P2 | audit-only | `accepted_row_dataclasses_materialized` always zero in DRC/RRAO | Remove or document as N/A |
| P2 | package-local | IMA `assess_rfet_evidence` ~280+ lines | Split qualitative vs quantitative gates |

## Recommended implementation order

1. Add/extend hash regression tests; run `check_simplification_drift.py` before each PR.
2. Migrate `_hash_payload` → `frtb_common.stable_json_hash` (SBM, DRC, CVA).
3. Package-local helper extraction (`_text`, `_citations`, `_payloads`) where not done.
4. Collapse SBM sensitivity-builder wrappers; split largest `batch.py` files.
5. RRAO shared validation module; decide single vs dual kernel.
6. Result-store `io.py` split; orchestration `suite.py` helper extraction.
7. IMA RFET evidence stage split per `REFACTOR_HOTSPOTS.md`.

## Evidence commands

```bash
uv run python scripts/ci/check_simplification_drift.py
find packages -path '*/src/*' -name '*.py' -print | xargs wc -l | sort -nr | head -40
rg "_hash_payload|stable_json_hash" packages/*/src -n
```

Implementation PRs remain **one package per PR** unless an ADR covers cross-cutting contract change.
