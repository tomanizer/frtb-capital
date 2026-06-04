# GitHub Copilot Instructions -- frtb-capital

Before changing code, read the repository guidance:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/AGENT_WORKTREE_POLICY.md`
- The relevant package-level `AGENTS.md` and `CLAUDE.md`

Follow those files as the source of truth. In particular:

- Do not edit the protected main clone. It is discovered by
  `scripts/agent_worktree.py` from Git worktree metadata or local
  `frtb.agentMainClone` config. Work under the resolved standard worktree root
  at `<worktree-root>/copilot/<task>` on a `copilot/<task>` branch. Run
  `python3 scripts/agent_worktree.py guard` before editing.
- Respect package boundaries. Capital packages must not import sibling capital
  packages; shared types belong in `frtb-common`.
- Keep suite aggregation in `frtb-orchestration`.
- Use Python 3.11+, dataclasses, enums, and pure functions.
- `numpy` is the default runtime numerical dependency for calculation kernels.
  Adding another runtime dependency requires an ADR.
- Add deterministic tests for calculation changes.
- Use synthetic data only.
- Cite specific regulatory paragraphs for regulatory behavior.
- Do not present prototype outputs as final regulatory capital.
- Before pushing, run `make agent-guard` and choose the local CI preset that
  matches the change:
  - `make ci-local-pr` for ordinary package code, tests, fixtures, scripts,
    examples, adapters, or focused refactors.
  - `make ci-local-governance` for CI workflow, governance, docs quality,
    dependency/SBOM, examples, notebook, or agent-instruction changes.
  - `make ci-local-performance` for vectorization, batch, adapter, benchmark,
    memory/performance-sensitive, or scaling-sensitive changes.
  - `make ci-local-release` for release-readiness, pre-merge hardening, broad
    cross-package changes, or final audit before a high-risk merge.
  If a preset is impractical, run the most relevant narrower commands and state
  the validation gap in the PR.

For IMA work, read `packages/frtb-ima/AGENTS.md` and
`packages/frtb-ima/CLAUDE.md` before editing IMA code.

For PR babysitting (CI stabilisation, Gemini/Copilot review incorporation, final
audit), read and follow `.grok/skills/frtb-ci-babysit/SKILL.md`. Use
`make agent-new AGENT=copilot TASK=<task-name>` when the worktree guard fails.
Requires the `gh` CLI.

For documentation audits across all packages (README, AGENTS/CLAUDE, ARCHITECTURE,
PUBLIC_API, ADR alignment), read and follow:

- `.grok/skills/frtb-doc-audit/SKILL.md`
- `.grok/skills/frtb-doc-audit/references/audit-checklist.md`

For simplification / maintainability audits (complexity, wrappers, duplication),
read and follow:

- `.grok/skills/frtb-simplify-audit/SKILL.md`
- `docs/quality/simplification/rubric.md`
- `docs/quality/simplification/2026-06-04/`

Use `make agent-new AGENT=copilot TASK=<task-name>` when the worktree guard fails.
Documentation-only changes do not bump package versions.
