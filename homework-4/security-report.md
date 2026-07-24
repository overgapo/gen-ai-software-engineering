# Security Report — Expense Tracker API

**Agent:** Security Verifier (required agent, Task 3) · **Model:** `claude-opus-4-8` ·
**Date:** 2026-07-23 · **Scope:** `fix-summary.md` + `src/**` · **Write scope:** this report only
(no code or test file was modified).

## Summary

**Overall posture: FAILING — the seeded security defect is still fully present.**

`fix-summary.md` reports **Status: BLOCKED** with **"Changes Made: None."** — the upstream research
quality gate failed (Level C), so the Bug Fixer applied no edits and `src/**` is unmodified. There is
therefore **no changed code to review**. Rather than return an empty report, this review was performed
against the **current baseline** of `src/**`, which is exactly the state the next Fixer run will start
from. Every finding below is open **as of this run**.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 1 |
| MEDIUM   | 2 |
| LOW      | 3 |
| INFO     | 1 |
| **Total**| **7** |

The seeded defect `context/bugs/003` (hardcoded key + `==` compare) is **NOT remediated** — *both*
halves are still open (F-01 and F-02). Per the bug-context contract, fixing only one would still leave
the finding open; here neither is fixed.

Confirmed clean: no injection sinks of any kind (no `child_process`, `exec`, `eval`, `Function()`,
`fs`, path handling, and no SQL/NoSQL layer — the store is an in-memory array), and `npm audit`
reports **0 vulnerabilities** across both runtime and dev trees.

---

## Findings

### F-01 · HIGH · Hardcoded API credential committed to source
**`src/expenses.js:12`** (used at `src/expenses.js:75`)

```js
const API_KEY = 'sk_live_9f8c2b1a7e4d';
```

The credential guarding the destructive `DELETE /expenses/:id` route is a string literal in tracked
source. `git grep` confirms the live value is readable in two tracked files:
`src/expenses.js:12` and `context/bugs/003/bug-context.md:13,28`.

**Why it's exploitable:** anyone with read access to the repository — a fork, a CI log, a cloned
mirror, a leaked archive — obtains a working credential and can delete arbitrary records with a single
`curl -X DELETE -H "x-api-key: sk_live_9f8c2b1a7e4d" …`. The `sk_live_` prefix advertises it as a
production secret, so scanners and scrapers will flag and harvest it. It also cannot be rotated
without a code change and redeploy, and the value persists in git history even after the line is
edited.

**Remediation:** read the key from configuration and **fail closed** when it is absent:

```js
const API_KEY = process.env.API_KEY;
// in the handler, before any comparison:
if (!API_KEY) return res.status(503).json({ error: 'Server not configured' });
```

Do not fall back to a default value. Document `API_KEY` in `README.md`/`HOWTORUN.md` and keep it in a
`.env` file (already covered by `.gitignore:4`). Treat `sk_live_9f8c2b1a7e4d` as burned and rotate it.
Keep the literal in `context/bugs/003/bug-context.md` only because that file's purpose is to document
the seeded defect — it must not be reintroduced into `src/` or `tests/`.

---

### F-02 · MEDIUM · Non-constant-time, type-loose comparison of a secret
**`src/expenses.js:75`**

```js
const provided = req.header('x-api-key');
if (provided == API_KEY) {
```

**Why it's exploitable:** JavaScript's `==` on strings short-circuits at the first differing byte, so
response latency correlates with the length of the matching prefix. An attacker who can issue many
requests and measure timing can recover the key byte-by-byte in roughly linear rather than exponential
attempts — the classic timing side-channel. The absence of rate limiting (F-03) removes the practical
barrier to collecting enough samples. The loose `==` is additionally poor practice on a secret: it is
not itself bypassable here (Express's `req.header()` yields `string | undefined`, and
`undefined == '<key>'` is `false` — verified), but it invites type-juggling bugs if the input source
ever changes.

**Remediation:** compare with a constant-time primitive, guarding the length mismatch first, since
`crypto.timingSafeEqual` throws on unequal-length buffers:

```js
const crypto = require('crypto');

function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const ba = Buffer.from(a, 'utf8');
  const bb = Buffer.from(b, 'utf8');
  if (ba.length !== bb.length) return false;   // length still leaks; acceptable for fixed-length keys
  return crypto.timingSafeEqual(ba, bb);
}
```

Then `if (safeEqual(provided, API_KEY))`. Fix F-01 and F-02 together — the bug-context explicitly
requires both.

---

### F-03 · MEDIUM · No rate limiting or lockout on the credential check
**`src/expenses.js:73-83`**

`DELETE /expenses/:id` accepts unlimited authentication attempts with no throttling, backoff, lockout,
or logging of failures.

**Why it's exploitable:** the key is a 12-character hex-ish string. With no request ceiling an attacker
can run an unbounded online guessing campaign, and — combined with F-02 — can harvest the timing
samples needed to shortcut brute force entirely. Failed attempts are also invisible: nothing is logged,
so an ongoing attack leaves no trace for an operator to notice.

**Remediation:** apply a limiter to the authenticated route, e.g.
`express-rate-limit` (`app.use('/expenses', rateLimit({ windowMs: 60_000, max: 20 }))`), and log 401s
with the source IP and timestamp. If adding a dependency is undesirable for this assignment, a small
in-memory counter keyed by IP with an exponential delay is sufficient to demonstrate the control.

---

### F-04 · LOW · User-controlled property key written to a plain object
**`src/expenses.js:60`** (aggregation loop at `src/expenses.js:58-61`)

```js
byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
```

`category` comes straight from the request body (`src/expenses.js:40`) and is validated only as a
non-empty string (`src/validation.js:16-18`) — reserved property names are accepted.

**Why it matters:** posting `{"category": "constructor", …}` makes the lookup resolve to
`Object.prototype.constructor` (truthy), so the `|| 0` guard is bypassed and the addition becomes
string concatenation. Verified behaviour: the response body becomes
`{"constructor":"function Object() { [native code] }1"}` — corrupted arithmetic plus a small internal
detail reflected to the client. This is **not** prototype pollution: `__proto__` assignment with a
non-object value is a silent no-op (verified — `Object.prototype` was untouched and the key did not
appear). The impact is response integrity, not RCE, hence LOW.

**Remediation:** use a null-prototype accumulator and an explicit numeric guard:

```js
const byCategory = Object.create(null);
for (const e of rows) {
  byCategory[e.category] = (Object.hasOwn(byCategory, e.category) ? byCategory[e.category] : 0) + e.amount;
}
return res.json({ count: rows.length, total, byCategory: { ...byCategory } });
```

Optionally reject `__proto__`, `constructor`, and `prototype` as category values in `validateExpense`.

---

### F-05 · LOW · Inconsistent access control — writes are unauthenticated
**`src/expenses.js:35`** (`POST /expenses`), vs. **`src/expenses.js:73`** (`DELETE`)

Deletion requires an API key; creation requires nothing. `GET /expenses`, `GET /summary`, and
`GET /expenses/:id` are likewise open.

**Why it matters:** any unauthenticated client can inject arbitrary records, distorting every
subsequent `/summary` total, and can read the full dataset. For a single-tenant demo with seeded
sample data this may be a deliberate simplification, but the asymmetry — guarding delete while leaving
create open — is the kind of gap that survives into a real deployment unnoticed.

**Remediation:** decide the trust boundary explicitly and apply it uniformly. Once F-01/F-02 land,
extract the key check into a middleware and mount it on every mutating route
(`router.post('/expenses', requireApiKey, …)`). If read endpoints are intentionally public, state that
in `README.md` so the choice is documented rather than implicit.

---

### F-06 · LOW · No bounds on string fields; unbounded in-memory growth
**`src/validation.js:16-18`** (no length cap on `category`) and **`src/store.js:21-25`** (no cap on
stored records; `description` at `src/expenses.js:40` is never validated at all)

**Why it matters:** `description` is accepted with no type or length check whatsoever, and the store
grows without limit for the process lifetime. Express's default 100 kB JSON body limit caps a single
request, but nothing caps the number of requests — a loop of `POST /expenses` steadily consumes heap
until the process degrades or is OOM-killed. Every payload also passes through `/summary`'s reduce, so
the cost compounds. Availability impact only; no data is exposed.

**Remediation:** validate `description` as an optional string with a max length (e.g. 500), cap
`category` (e.g. 64 chars), set an explicit body limit (`express.json({ limit: '16kb' })`), and enforce
a maximum record count in `store.add` that returns an error once exceeded. Combine with F-03's limiter
for meaningful protection.

---

### F-07 · INFO · No security response headers
**`src/app.js:6-11`**

The app registers only `express.json()` — no `helmet`, no explicit `Content-Security-Policy`,
`X-Content-Type-Options`, or `Referrer-Policy`, and Express's `X-Powered-By` banner is left on,
disclosing the framework.

**Why it's low-impact here:** all responses are `application/json` (`res.json`), so there is no HTML
rendering surface and no reflected/stored **XSS** vector despite `description` being unvalidated
(F-06) — a browser will not execute a JSON body served with that content type. **CSRF** is likewise
not applicable: authentication is a custom `x-api-key` header, not a cookie, so a cross-origin form
post cannot carry credentials, and no CORS middleware is configured (browsers' same-origin default
blocks cross-origin reads). Both were checked explicitly and are clean.

**Remediation:** `app.use(helmet())` and `app.disable('x-powered-by')` for defence in depth. Not
blocking for this assignment.

---

## Verified Remediations

**None.** No seeded or previously-reported issue was confirmed fixed in this run, because
`fix-summary.md` records zero code changes and `git status` shows `src/**` unmodified.

| Seeded issue | Expected remediation | Status |
|---|---|---|
| `context/bugs/003` — hardcoded secret | Key read from `process.env.API_KEY`, fail closed when unset | **OPEN** — literal still at `src/expenses.js:12` (F-01) |
| `context/bugs/003` — insecure comparison | `crypto.timingSafeEqual` with a length guard | **OPEN** — still `provided == API_KEY` at `src/expenses.js:75` (F-02) |

Non-security seeded defects are outside this agent's remit but were observed still present and are
noted only so the record is complete: `src/expenses.js:56` (`/summary` ignores filters) and
`src/expenses.js:29` (exclusive `<` upper bound).

### Dependency review

`npm audit` and `npm audit --omit=dev` both report **0 vulnerabilities**. Installed:
`express@4.22.2` (satisfies the `^4.19.2` range and is current for the 4.x line),
`jest@29.7.0`, `supertest@7.2.2` (dev only). No unsafe or unmaintained packages found; no
transitive advisories. Re-run `npm audit` after any dependency added for F-03 (e.g.
`express-rate-limit`) or F-07 (`helmet`).

---

## Gate for the next pipeline run

This report must be re-run after the Bug Fixer actually applies the `context/bugs/003` remediation.
The re-review passes only when **all** of the following hold:

1. No credential literal in `src/**` or `tests/**` (`git grep sk_live_` returns only
   `context/bugs/003/bug-context.md`).
2. `process.env.API_KEY` is the sole source of the key, with a fail-closed branch when unset.
3. The comparison uses `crypto.timingSafeEqual` behind a length check.
4. No test hardcodes a valid key — tests must set `process.env.API_KEY` themselves.

---

## References

Files and lines reviewed:

- `src/expenses.js:1-85` — full review; findings at `:12`, `:29`, `:56`, `:60`, `:73-83`, `:75`
- `src/validation.js:1-31` — trust-boundary input validation; findings at `:16-18`, `:27-29`
- `src/app.js:1-13` — middleware stack; finding at `:6-11`
- `src/store.js:1-34` — in-memory persistence; finding at `:21-25`
- `src/index.js:1-18` — entry point, seed data, `PORT` handling — no findings
- `fix-summary.md:1-69` — scope input; establishes zero code changes this run
- `context/bugs/003/bug-context.md:1-47` — seeded security defect contract
- `package.json:10-16`, `npm audit`, `npm ls --depth=0` — dependency review
- `.gitignore:1-4` — confirms `.env` is excluded, so F-01's remediation path is safe
- `tests/` — empty; no test-side credential exposure to review yet

Verification commands run during this review: `git grep 'sk_live_9f8c2b1a7e4d'`,
`git status --short`, `npm audit`, `npm audit --omit=dev`, `npm ls --depth=0`, a `node -e` probe
confirming the F-04 prototype-key behaviour, and a `node -e` probe confirming
`undefined == '<key>'` is `false` (F-02). **No file under `src/` or `tests/` was modified.**
