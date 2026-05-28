# Security policy

## Reporting a vulnerability

Report suspected security issues privately by emailing **thomas.haederle@gmail.com**.

Do not file a public issue for a security report. Include:

- Affected package(s) and version(s).
- Reproduction steps.
- Impact assessment.

You will receive an acknowledgement within five business days.

## Scope

This suite is a calculation library with no network I/O, no authentication surface, and no secrets handling. The relevant security concerns are:

- **Supply chain.** Dependency locking and automated vulnerability monitoring
  are tracked by audit-followup work. Until that lands, supply-chain reports
  for unpinned dependencies or missing scan coverage are in scope.
- **Input validation.** All public APIs validate inputs at the boundary. Reports of crashes, denial-of-service via malformed input, or numerical undefined behaviour are in scope.
- **Determinism.** Reports of non-deterministic output for identical inputs are in scope as a model-risk issue.

## Out of scope

- Issues in software that depends on this suite.
- Issues in upstream regulatory data sources.
- Issues that require physical access to the user's machine.

## Disclosure timeline

Vulnerabilities will be disclosed in a coordinated release after a fix is available, typically within 30 days of confirmation.
