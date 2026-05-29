# GitHub Copilot Instructions -- frtb-capital

Before changing code, read the repository guidance:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/AGENT_WORKTREE_POLICY.md`
- The relevant package-level `AGENTS.md` and `CLAUDE.md`

Follow those files as the source of truth. In particular:

- Do not edit the protected main clone at `~/Documents/Projects/frtb-capital`.
  Work under `~/Documents/Projects/frtb-capital-worktrees/copilot/<task>` on a
  `copilot/<task>` branch. Run `python3 scripts/agent_worktree.py guard`
  before editing.
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

For IMA work, read `packages/frtb-ima/AGENTS.md` and
`packages/frtb-ima/CLAUDE.md` before editing IMA code.
