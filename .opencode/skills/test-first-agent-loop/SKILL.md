---
name: test-first-agent-loop
description: Require builders to run validation, reviewers to demand evidence, and all agents to record failures honestly instead of claiming success without test results.
---

# Test First Agent Loop

Use this skill when a prompt requires implementation, review, or signoff.

## Builder Requirements

The builder must:

- identify required validation commands before claiming completion;
- run unit tests, build/static generation, smoke checks, domain checks, route checks, browser tests, and security scans when relevant;
- stop feature work when validation fails;
- fix failures only inside approved scope;
- rerun failed commands and the full suite when practical;
- document exact commands, results, failures, fixes, and remaining risks.

## Reviewer Requirements

The reviewer must block signoff when:

- validation commands are missing;
- output is summarized without evidence;
- tests are superficial or unrelated;
- generated output changed without review;
- screenshots are missing for UI work that needs browser evidence;
- security/redaction checks were skipped before publication.

## Honest Reporting

Use precise language:

- `passed` only when the command completed successfully;
- `failed` when the command returned non-zero or produced blocking errors;
- `not run` when skipped, with a reason;
- `not applicable` only when the category genuinely does not apply.

Never hide failures to make a prompt look complete.
