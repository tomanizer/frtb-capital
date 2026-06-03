# Review conversations — consider and resolve

Run **Phase 3.5** after Phases 2–3 (or after Phase 1 when reviews are skipped) and
**again** after the last fix push before merge-ready.

## List unresolved threads

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"
gh api graphql -f query='
query($owner:String!, $name:String!, $number:Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          path
          line
          comments(first: 20) {
            nodes {
              author { login }
              body
              createdAt
            }
          }
        }
      }
    }
  }
}' -f owner="$OWNER" -f name="$NAME" -F number="$PR" \
  --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved==false)'
```

Also scan top-level issue comments for actionable human requests not in threads.

## Bot vs human authors

Treat as **bot** (resolve only after explicit reply when declining):

`gemini`, `github-copilot`, `copilot`, `cursor`, `cursor[bot]`, `bugbot`,
`github-actions`, `dependabot`, `chatgpt-codex-connector`, `copilot-swe-agent`

Everyone else is **human** for merge-ready counting unless the login is your own
babysitter service account.

## Per-thread workflow

For **every** unresolved thread:

1. **Consider** — read path, diff, and comment; decide valid / false positive / deferred.
2. **Act** — fix and push, or reply on the thread explaining the decision (required
   before resolving human threads).
3. **Resolve** — when addressed or explicitly declined with a posted reply:

```bash
gh api graphql -f query='
mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread { isResolved }
  }
}' -f threadId='PRRT_...'
```

Do **not** resolve without a reply on human threads. For bot threads, reply briefly
when declining (e.g. “Acknowledged — out of scope for this PR; tracked in #N”).

## Out-of-scope / deferred

If deferred, cite issue number or ADR in the reply, then resolve so the PR does not
stall on stale threads.

## Merge-ready

**Zero unresolved review threads** after Phase 3.5. Report total threads considered,
resolved, and any left open with reason (should be none for merge-ready).