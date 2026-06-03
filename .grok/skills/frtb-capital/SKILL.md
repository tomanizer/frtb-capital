# frtb-capital

Use this skill when working in the `frtb-capital` repository with Grok or
Grok Build.

## Required Reading

Before changing code, read:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/AGENT_WORKTREE_POLICY.md`
- The relevant package-level `AGENTS.md` and `CLAUDE.md`

Grok Build also reads the `AGENTS.md` and `CLAUDE.md` instruction families
directly; this skill is a short repo-specific reminder and entrypoint.

## Working Rules

- Run `python3 scripts/agent_worktree.py guard` before editing. If it fails,
  create a worktree under the resolved standard worktree root with
  `make agent-new AGENT=grok TASK=<task-name>`.
- Respect package boundaries. Capital packages must not import sibling capital
  packages; shared types belong in `frtb-common`.
- Keep suite aggregation in `frtb-orchestration`.
- SA is composed from `frtb-sbm`, `frtb-drc`, and `frtb-rrao`; it is not a
  standalone package.
- Use Python 3.11+, dataclasses, enums, and pure functions.
- `numpy` is the default runtime numerical dependency for calculation kernels.
  Adding another runtime dependency requires an ADR.
- Use synthetic data only.
- Add deterministic tests for calculation changes.
- Cite specific regulatory paragraphs for regulatory behavior.
- Do not present prototype outputs as final regulatory capital.

For IMA work, read `packages/frtb-ima/AGENTS.md` and
`packages/frtb-ima/CLAUDE.md` before editing IMA code.
