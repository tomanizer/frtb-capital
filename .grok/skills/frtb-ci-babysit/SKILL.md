---
name: frtb-ci-babysit
description: >-
  Babysit an frtb-capital PR from push to merge-ready: stabilise CI, incorporate
  bot reviews when available (Gemini, Copilot, Cursor Bugbot fallbacks), skip
  unavailable reviewers, run a final quality subagent audit.
when-to-use: >-
  Use when asked to babysit, watch, or fix a frtb-capital PR, monitor CI until
  green, incorporate bot review feedback, or runs /frtb-ci-babysit.
argument-hint: "[<pr-number>] [--agent <name>]"
allowed-tools: Shell, Read, Grep, Glob, Write, StrReplace, Task
---

# FRTB CI babysit

Babysit an `frtb-capital` pull request from push through merge-readiness. Four
sequential phases; complete each before advancing.

Read `AGENTS.md`, `CLAUDE.md`, and `.grok/skills/frtb-capital/SKILL.md` before
editing code.

## Cross-agent entrypoints

| Agent | Entry |
| --- | --- |
| Grok | `/frtb-ci-babysit` (this skill) |
| Claude Code | `/frtb-ci-babysit` → `.claude/commands/frtb-ci-babysit.md` |
| Codex | `AGENTS.md` → CI babysit section |
| Cursor | `.cursor/rules/frtb-capital.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |

## Arguments

| Input | Meaning |
| --- | --- |
| `<pr-number>` | Optional. If omitted, use `gh pr view` on the current branch. |
| `--agent <name>` | Worktree agent id (`BABYSITTER`) for worktrees and fallback review selection: `grok`, `claude`, `codex`, `cursor`, or `copilot`. Default: infer from context or `grok`. |

Requires `gh` authenticated for the repository and a compliant agent worktree for
commits.

Record `BABYSITTER` from `--agent` or context. Fallback reviews must use a
**different** reviewer than `BABYSITTER` (do not trigger Cursor Bugbot if
`BABYSITTER=cursor`; do not use the Phase 4 subagent as a substitute for Phase 2
when Gemini/Copilot could still run — Phase 4 remains the final gate).

---

## Step 0 — Start state

**Success criteria:** `PR` exported; worktree guard passed; baseline recorded.

```bash
# Optional: gh pr checkout <N> first if user supplied a PR number
gh pr view ${PR:-} --json number,title,headRefName,baseRefName,isDraft,mergeable,state
export PR=$(gh pr view ${PR:-} --json number --jq .number)
```

If no PR exists for the current branch, stop and ask the user. Set `$PR` once;
do not re-derive it later.

Worktree compliance (required before any edit):

```bash
python3 scripts/agent_worktree.py guard
```

On failure:

```bash
make agent-new AGENT=<agent> TASK=ci-babysit
# cd to printed worktree; gh pr checkout $PR if needed
```

Record: PR number, head SHA, draft state, base branch, CI run count, unresolved
human review thread count, and `BABYSITTER`.

---

## Reviewer availability helpers

Use these patterns on PR issue comments, review bodies, check summaries, and
job logs. Case-insensitive matching is enough.

### Gemini unavailable (skip Gemini wait)

Match any of:

- `try again later`
- `blocked for 24`
- `24 hour`
- `rate limit` / `quota exceeded`
- `not available` (in a Gemini/Code Assist context)
- No Gemini review after **45 minutes** from first green CI on the current SHA

### Copilot unavailable (skip Phase 3)

Match any of:

- `run out of ai credits`
- `ai credits for the month`
- `out of credits`
- `copilot subscription`
- `billing` + `copilot` (in the same comment)
- Copilot review explicitly failed or disabled for the repo

Collect recent PR text:

```bash
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
gh api "repos/$REPO/issues/$PR/comments" --paginate \
  --jq '.[].body' | head -c 200000
gh pr view $PR --json reviews --jq '.reviews[].body'
```

When a phase is skipped, record `SKIPPED: <phase> — <reason>` in the final report.

---

## Phase 1 — CI stabilisation

**Success criteria:** All required checks for this PR are `success`; acceptable
checks are explicitly `skipped` per the table below.

### Monitor

```bash
gh pr checks $PR --watch
```

Prefer the aggregate `ci-required` check when present. On failure, inspect logs:

```bash
gh run view <run-id> --log-failed
```

### Required jobs (current `.github/workflows/ci.yml`)

| Job | When it must pass on PRs | Notes |
| --- | --- | --- |
| `quality-control` | Always | Never skipped; includes maturity and drift gates. |
| `version-bump-guard` | Always | Fails if non-`release/*` PR bumps versions. |
| `uv-lock-guard` | Always | Fails if `uv.lock` changes without dependency-spec changes. |
| `ci-required` | Always | Aggregates child job results. |
| `lint` | When `changes.code` | Includes `format-check` step inside lint. |
| `typecheck` | When `changes.code` | |
| `build` | When `changes.code` | |
| `test (3.11)` | When `changes.code` | Only PR Python test job. |
| `docs` | When `changes.docs` | Runs `make docs-check`. |
| `dependency-audit` | When `changes.dependency` | |
| `sbom` | When `changes.dependency` | |
| `examples` | When `changes.examples` | |
| `notebooks` | When `changes.notebooks` | |

**Skipped on pull requests (expected, not failures):**

| Job | Why |
| --- | --- |
| `test (3.12)`, `test (3.13)` | `test-compat` runs only on `schedule` and `workflow_dispatch`, not on PRs. |

Do not treat skipped `test-compat` matrix jobs on a PR as a defect.

### Failure handling

1. Read the failed job log in full.
2. Classify: **branch-related** (fix locally), **flaky/infra** (`gh run rerun <run-id> --failed`), or **ambiguous** (one diagnosis pass first).
3. Avoid pushing CI fixes on top of unaddressed review threads when the fix will
   invalidate bot reviews — order fixes deliberately.

### Local validation

```bash
make agent-guard
make ci-local-fast                # lint + format + typecheck + tests
make ci-local                     # + coverage + build
make quality-control              # import smoke + maturity + drift reports
```

On maturity failures, inspect `dist/quality/package-maturity.json` after
`make maturity-check` or download the `package-maturity` CI artifact.

Repeat until required jobs are green.

---

## Phase 2 — External code review (Gemini or fallbacks)

**Success criteria:** One external review path completed (incorporated or
documented skip), or all paths skipped with explicit reasons; CI green on the
current SHA before Phase 3/4.

Track `PHASE2_STATUS`: `gemini` | `cursor-bugbot` | `pr-comment-review` | `skipped`.

### 2a — Try Gemini

Poll for a Gemini/Code Assist review (🙄 in body or author login matches `gemini`):

```bash
gh pr view $PR --json reviews --jq '
  .reviews[]
  | select(
      (.body | test("🙄")) or
      (.author.login | ascii_downcase | test("gemini"))
    )
  | {author: .author.login, state: .state, body: .body[:500]}
'
```

- If a review arrives: triage findings (fix + validate, or document false positives).
  Set `PHASE2_STATUS=gemini`. Go to **2d**.
- If PR text matches **Gemini unavailable** patterns: skip Gemini. Go to **2b**.
- If **45 minutes** elapse with no Gemini review and no availability error: treat as
  unavailable; go to **2b**.

### 2b — Fallback reviews (Gemini unavailable only)

Try each path below **in order**. Stop at the first path that produces actionable
review content (inline comments or a review body with findings). Do not use the
babysitting agent as the “external” reviewer.

#### Fallback 1 — Cursor Bugbot (preferred GitHub trigger)

Skip this fallback when `BABYSITTER=cursor`.

Post a **new top-level** PR comment (not a reply in a thread):

```bash
gh pr comment $PR --body "@cursoragent review"
```

Use exactly that text for this repository. If Bugbot does not respond within the
poll window, retry once with `cursor review` or `bugbot run` (alternate triggers
in [Cursor Bugbot docs](https://cursor.com/docs/bugbot)) before moving to
Fallback 2.

Poll up to **45 minutes** for:

- `Cursor Bugbot` check on the PR, or
- review/comments from `cursor[bot]`, `cursor`, or `bugbot` logins.

```bash
gh pr checks $PR
gh pr view $PR --json reviews,comments
```

If findings arrive: triage like Gemini. Set `PHASE2_STATUS=cursor-bugbot`. Go to **2d**.

#### Fallback 2 — Non-author PR review comment

Skip when no suitable reviewer remains (e.g. only `BABYSITTER` is available).

Spawn a **read-only** subagent (not `BABYSITTER` labeled the same as the PR author
agent if avoidable). Brief it to review `gh pr diff $PR` against `CLAUDE.md`
checklist items 1–6 (same scope as Phase 4). Post the summary on the PR:

```bash
gh pr diff $PR > /tmp/frtb-babysit-${PR}.diff
gh pr review $PR --comment --body-file /tmp/frtb-babysit-review-${PR}.md
```

Set `PHASE2_STATUS=pr-comment-review`. Go to **2d**.

#### Fallback 3 — Skip external review

If fallbacks fail or time out, set `PHASE2_STATUS=skipped` with reason
(`cursor not installed`, `bugbot timeout`, `no alternate reviewer`). Continue —
Phase 4 subagent audit still runs.

### 2c — Incorporate findings

For any non-skipped path: apply valid fixes, validate locally, push, confirm CI green.

### 2d — Mark PR ready (for Copilot when available)

If the PR is still a draft **and** Copilot is not pre-flagged unavailable (Phase 3a):

```bash
gh pr ready $PR
```

If Copilot is already known unavailable, you may still `gh pr ready` so humans can
review, but skip waiting in Phase 3.

---

## Phase 3 — Copilot review (optional)

**Success criteria:** Copilot triaged, or phase **skipped** with documented reason;
CI green on current SHA.

### 3a — Availability

Before waiting, scan PR comments/reviews for **Copilot unavailable** patterns.
If matched: `COPILOT_STATUS=skipped` and jump to Phase 4.

Copilot reviews: author login matches `copilot` or `github-copilot`.

```bash
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
gh api "repos/$REPO/pulls/$PR/comments" \
  --jq '[.[] | select(.user.login | ascii_downcase | test("copilot"))]'
```

### 3b — Wait and incorporate

Only when Copilot is expected to be available:

- Wait up to **45 minutes** after `gh pr ready` for Copilot review or inline comments.
- If credit/quota messages appear during the wait: `COPILOT_STATUS=skipped`.
- Otherwise triage findings like Phase 2; push fixes; confirm CI green.

If Copilot never arrives and no availability message explains it, skip with
`COPILOT_STATUS=skipped — timeout` and continue.

---

## Phase 4 — Final audit (subagent)

**Success criteria:** Subagent returns explicit **PASS**; otherwise fix, push, re-run.

Spawn a read-only reviewer subagent with this brief:

> Audit PR #$PR on `frtb-capital` before merge-ready.
>
> 1. **Package boundary** — no sibling capital imports except orchestration.
> 2. **`CLAUDE.md` review checklist** — all ten items; cite failures.
> 3. **`make quality-control`** — report failed requirement ids from
>    `dist/quality/package-maturity.json` if any.
> 4. **Evidence** — touched `implemented` / `partial_runtime` packages have
>    non-placeholder maturity evidence.
> 5. **Regulatory citations** — new thresholds in `src/` have paragraph citations.
> 6. **Tests** — new public functions have normal-path and invalid-input tests.
>
> Verdict: **PASS** or **FAIL** with a numbered finding list.

On **FAIL**: apply fixes, push, green CI, re-audit. On **PASS**: continue to output.

---

## Final output

Report must include:

- PR URL and number
- Head SHA at completion
- CI conclusion per required job (list skipped jobs explicitly)
- **Phase 2:** `PHASE2_STATUS` and skip/fallback reasons
- **Phase 3:** `COPILOT_STATUS` (`completed` or `skipped` + reason)
- Unresolved **human** thread count
- Draft state (must be `false` for merge-ready)
- `mergeable` from `gh pr view`
- Subagent verdict (Phase 4)
- `git status --short`

**Merge-ready when:** required CI green, not draft, no unresolved human threads,
subagent **PASS**, mergeability not `CONFLICTING`.

Skipped Gemini/Copilot/fallback reviews are **not** merge blockers when documented;
the Phase 4 subagent audit remains required.

---

## Worktree policy

Never commit from the protected main clone (`~/Documents/Projects/frtb-capital`).
Use `~/Documents/Projects/frtb-capital-worktrees/<agent>/<task>` on branch
`<agent>/<task>`. See `docs/AGENT_WORKTREE_POLICY.md`.