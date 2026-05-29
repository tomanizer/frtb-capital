---
description: Babysit an frtb-capital PR from push to merge-ready. Monitors CI, waits for and incorporates the automated Gemini review, marks the PR ready for review to trigger Copilot, incorporates Copilot feedback, then runs a final subagent audit. Use when asked to babysit, watch, or fix a frtb-capital PR.
allowed-tools: Bash, Read, Edit, Write, Agent
---

# FRTB CI Babysit

Babysit an `frtb-capital` pull request from push through merge-readiness. The
workflow has four sequential phases. Complete each phase before advancing.

---

## 0. Start state

Determine the PR:

```bash
gh pr view --json number,title,headRefName,baseRefName,isDraft,mergeable,state
```

If no PR exists for the current branch, stop and ask the user.

Confirm worktree compliance before editing anything:

```bash
python3 scripts/agent_worktree.py guard
```

Record: PR number, head SHA, draft state, base branch, CI run count, and
unresolved thread count. This is the baseline for the run.

---

## Phase 1 — CI stabilisation

### What to monitor

- `quality-control` — always runs, never skipped. If this job is absent from
  the check list something is wrong with the workflow wiring.
- `lint`, `format-check`, `typecheck`, `build`, `test (3.11)` — required for
  code and dependency changes.
- `dependency-audit`, `sbom` — required when `pyproject.toml` or `uv.lock`
  changed.
- `examples`, `notebooks` — required when IMA examples or notebooks changed.
- Python `3.12` and `3.13` test matrix jobs — may be legitimately skipped on
  normal PRs (they are scheduled/manual compatibility checks). Do not treat a
  skip as a failure.

```bash
gh pr checks --watch
```

### Failure handling

1. Read the failed job log in full before touching any code:
   ```bash
   gh run view <run-id> --log-failed
   ```
2. Classify the failure:
   - **Branch-related**: lint/type/test/build errors in touched files. Patch,
     validate locally, commit, push.
   - **Flaky/infrastructure**: runner timeout, transient registry failure,
     GitHub Actions outage. Rerun the failed jobs:
     ```bash
     gh run rerun <run-id> --failed
     ```
   - **Ambiguous**: one focused manual diagnosis before deciding.
3. Fix review threads before pushing CI fixes when a thread fix will add a new
   SHA — avoid stacking runs that the review will invalidate.

### Local validation targets

```bash
make agent-guard                  # worktree compliance
make ci-local-fast                # lint + format + typecheck + tests
make ci-local                     # + coverage + build
make quality-control              # import smoke + maturity check
```

Repeat until all required CI jobs are green.

---

## Phase 2 — Gemini automated review

After the first green CI run, Gemini Code Assist posts an automated review.
Its reviews are identified by the 🙄 emoji signature or by a reviewer login
matching `gemini` (case-insensitive).

### Check for the Gemini review

```bash
gh pr view $PR --json reviews --jq '
  .reviews[]
  | select(
      (.body | test("🙄")) or
      (.author.login | ascii_downcase | test("gemini"))
    )
  | {author: .author.login, state: .state, body: .body[:200]}
'
```

If the review has not yet arrived, wait and recheck. Do not advance to Phase 3
until the Gemini review is present.

### Incorporating Gemini feedback

Read the full review body. For each comment or suggestion:

1. Decide: valid finding, false positive, or out of scope for this PR.
2. For valid findings: apply the fix, validate locally with the relevant
   `make` target, commit with a message that references the Gemini finding.
3. For false positives or out-of-scope items: note them in a comment on the
   review thread but do not resolve the thread — leave that for the human
   reviewer.

Do not post replies to Gemini threads without recording what you decided and
why. Keep a short decision log in your working context.

### Mark PR ready for review

Once Gemini feedback is incorporated and CI is green on the updated SHA:

```bash
gh pr ready $PR
```

This converts the PR from draft to open and triggers the Copilot Code Review.

---

## Phase 3 — Copilot review

Copilot Code Review posts after the PR is marked ready for review. Its reviews
are identified by a reviewer login matching `copilot` or `github-copilot`
(case-insensitive).

### Check for the Copilot review

```bash
gh pr view $PR --json reviews --jq '
  .reviews[]
  | select(.author.login | ascii_downcase | test("copilot"))
  | {author: .author.login, state: .state, body: .body[:200]}
'
```

Also check inline review comments:

```bash
gh api repos/{owner}/{repo}/pulls/$PR/comments \
  --jq '[.[] | select(.user.login | ascii_downcase | test("copilot"))]'
```

Wait for the Copilot review to arrive before advancing. If Copilot has not
reviewed within a reasonable time after the PR was marked ready, check whether
Copilot Code Review is enabled on the repository.

### Incorporating Copilot feedback

Apply the same decision process as for Gemini:

1. For valid code suggestions: apply, validate locally, commit.
2. For false positives: document why in your context; leave the thread
   unresolved for the human reviewer.
3. Inline code suggestions from Copilot can be accepted directly via:
   ```bash
   gh pr review $PR --comment -b "Accepting Copilot suggestion for <location>"
   ```
   but only after validating that the suggestion is correct and the tests pass.

Push all Copilot-motivated fixes and confirm CI is green before advancing.

---

## Phase 4 — Final audit (subagent)

Spawn a subagent to perform a final quality audit. Brief it as follows:

> You are auditing PR #<N> on the `frtb-capital` monorepo before it is marked
> merge-ready. The PR is on branch `<branch>`, base `<base>`.
>
> Your audit must check:
>
> 1. **Package boundary** — does the diff import any sibling capital package?
>    (`frtb-ima`, `frtb-rrao`, `frtb-drc`, `frtb-sbm`, `frtb-cva` must not
>    import each other; only `frtb-orchestration` may import multiple
>    components).
> 2. **CLAUDE.md checklist** — run through all ten items in the review
>    checklist in `CLAUDE.md`. Flag any item that is not satisfied.
> 3. **Quality-control gate** — run `make quality-control` and report the
>    result. If it fails, report the exact failed requirement ids from
>    `dist/quality/package-maturity.json`.
> 4. **Evidence completeness** — for any package touched by the diff whose
>    maturity is `implemented` or `partial_runtime`, confirm that the evidence
>    files required by that profile are present and not placeholders.
> 5. **Regulatory citations** — flag any new numerical constant in `src/`
>    files that has no regulatory paragraph citation in the same file or its
>    docstring.
> 6. **Test coverage** — for any new public function, confirm at least one
>    test covers the normal path and one covers invalid input.
>
> Return a structured verdict: PASS or FAIL with a list of specific findings.
> If PASS, say so explicitly so the babysitter can record a clean final state.

Wait for the subagent verdict. If FAIL: apply the flagged fixes, push, confirm
CI is green, and re-run the subagent audit. If PASS: record the final state.

---

## Output

Final status report must include:

- PR URL and number
- Head SHA at audit completion
- CI conclusion for all required jobs (list skipped jobs explicitly)
- Unresolved thread count (human threads only — do not count bot threads you
  have already actioned)
- Draft state: must be `false` (open, not draft)
- Mergeability status from `gh pr view --json mergeable`
- Subagent audit verdict
- Local branch cleanliness: `git status --short`

A PR is merge-ready when: CI green, draft false, zero unresolved human threads,
subagent audit PASS, and mergeability not `CONFLICTING`.

---

## CI expectations reference

| Job | When required | Skippable |
|---|---|---|
| `quality-control` | Always | Never |
| `lint` | Code changes | No |
| `format-check` | Code changes | No |
| `typecheck` | Code changes | No |
| `build` | Code changes | No |
| `test (3.11)` | Code changes | No |
| `test (3.12)` | Code changes | Yes — scheduled compat check |
| `test (3.13)` | Code changes | Yes — scheduled compat check |
| `dependency-audit` | `pyproject.toml` / `uv.lock` | No |
| `sbom` | `pyproject.toml` / `uv.lock` | No |
| `examples` | IMA examples/src changes | No |
| `notebooks` | IMA notebook/src changes | No |

---

## Worktree policy

All commits must happen from a compliant agent worktree, not from the
protected main clone at `~/Documents/Projects/frtb-capital`. If
`python3 scripts/agent_worktree.py guard` fails, create a new worktree with
`make agent-new AGENT=claude TASK=<task>` and move there before editing.
