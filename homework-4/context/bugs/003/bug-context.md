# Bug 003 — hardcoded API secret + insecure comparison (SECURITY)

- **Type:** Security vulnerability (hardcoded credential + insecure comparison)
- **Severity:** High
- **Location:** [`src/expenses.js`](../../../src/expenses.js) — `const API_KEY` and the `DELETE /expenses/:id` handler

## Symptom

Destructive `DELETE /expenses/:id` is guarded by an API key that is **hardcoded in
source**:

```js
const API_KEY = 'sk_live_9f8c2b1a7e4d';
...
if (provided == API_KEY) { ... }
```

Two distinct problems:

1. **Hardcoded secret.** The credential is committed to the repository, so it leaks to
   anyone with source access and cannot be rotated without a code change and redeploy.
2. **Insecure comparison.** `==` is loose (type-juggling) and not constant-time, leaking
   timing information that can help an attacker recover the key byte-by-byte.

## Reproduction

```
DELETE /expenses/2  with header  x-api-key: sk_live_9f8c2b1a7e4d   ->  204 (deleted)
DELETE /expenses/1  with header  x-api-key: nope                   ->  401
```

The key visible in the repo is sufficient to authorize deletion.

## Expected behavior

- Read the key from configuration (`process.env.API_KEY`), never from source. If it is
  unset, the route should refuse (fail closed).
- Compare using a constant-time check on equal-length buffers, e.g.
  `crypto.timingSafeEqual`, guarding against length mismatch first.
- No valid credential value should appear anywhere in the committed code or tests.

## Notes for the pipeline

This is the seeded issue the **Security Verifier** must flag (report only, no code edits),
and that the **Bug Fixer** remediates via the plan. Keep the remediation faithful: moving
the secret to env *and* switching to `timingSafeEqual` are both required — fixing only one
leaves the finding open.
