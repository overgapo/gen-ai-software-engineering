# Security Report — Expense Tracker (`src/`)

**Agent:** Security Verifier (Task 3) · **Model:** `claude-opus-4-8` · **Date:** 2026-07-24
**Scope:** the changes described in `fix-summary.md` (Changes 1–4) plus the code they
directly touch — `src/expenses.js`, `src/validation.js`, and their callers `src/app.js`,
`src/index.js`, `src/store.js`.
**Write scope honoured:** report only. **No source or test file was modified by this
agent.** Verification was done with a throwaway script under the session scratchpad
(`supertest` against `createApp()`), never inside the repo.

## Summary

**Posture: improved, and the seeded security defect is fully closed.** The `context/bugs/003`
remediation is correct on both halves — the secret now comes from `process.env.API_KEY`,
the comparison is `crypto.timingSafeEqual`, and the handler fails closed when the key is
unset or the header is absent. All three behaviours were confirmed against the running app,
and the literal `sk_live_9f8c2b1a7e4d` is gone from `src/`.

What remains are pre-existing weaknesses the fix round did not introduce but did not
address either, plus two small regressions in the changed code itself: the `/summary`
handler rewritten in Change 1 builds an object keyed by attacker-controlled strings, and
the tolerance introduced in Change 4 weakened the decimal check. No injection, no unsafe
dependency, and no remaining hardcoded credential in source.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH     | 0 |
| MEDIUM   | 3 |
| LOW      | 4 |
| INFO     | 3 |

Nothing here blocks the pipeline run. SEC-001 through SEC-003 are the ones worth fixing
before this code is treated as anything other than a teaching subject.

## Findings

### SEC-001 — MEDIUM — Unhandled body-parser errors leak stack traces and absolute filesystem paths

**Location:** `src/app.js:6-11` (no error-handling middleware; `express.json()` at line 8)

A malformed JSON body reaches Express's default error handler, which — because `NODE_ENV`
is never set to `production` anywhere in the repo (`package.json:7` runs a bare
`node src/index.js`, and neither `README.md` nor `HOWTORUN.md` sets it) — renders the full
stack trace into the HTTP response.

Reproduced:

```
POST /expenses  Content-Type: application/json  body: {oops
-> 400 text/html
   <pre>SyntaxError: Expected property name or '}' in JSON at position 1
       at parse (/Users/ash/projects/.../node_modules/body-parser/lib/types/json.js:96:19)
       ...
```

**Why it's exploitable:** any unauthenticated client can trigger it with a one-byte
malformed body. The response discloses the absolute deployment path, the directory layout,
and exact dependency file paths — standard reconnaissance input for path-traversal and
dependency-version targeting (CWE-209, CWE-200). It also means the API answers a JSON
route with an HTML error document, which content-type-strict clients mishandle.

**Remediation:** add a terminal error-handling middleware in `createApp()` that returns a
JSON body and never the stack, e.g.

```js
app.use((err, req, res, next) => {
  if (res.headersSent) return next(err);
  const status = err.status || err.statusCode || 500;
  return res.status(status).json({ error: status === 400 ? 'Malformed request body' : 'Internal error' });
});
```

and set `NODE_ENV=production` in any non-development run documented in `HOWTORUN.md`.

### SEC-002 — MEDIUM — `POST /expenses` accepts unauthenticated writes; store growth is unbounded

**Location:** `src/expenses.js:31-39` (handler) vs. `src/expenses.js:66-88` (the guarded DELETE)

`DELETE /expenses/:id` requires `x-api-key`; `POST /expenses` requires nothing. Confirmed:
a POST with no credentials whatsoever returns `201` and persists the record.

**Why it's exploitable:** an anonymous client can inject arbitrary expense records that
every other consumer of `GET /expenses` and `GET /summary` then reads as genuine data —
broken access control on a state-changing endpoint (CWE-284/CWE-306). Because the store is
a plain in-process array (`src/store.js:4`) with no cap and no eviction, the same endpoint
in a loop is also a memory-exhaustion path against the single Node process (CWE-770); the
only limiter is `express.json()`'s default 100 kB per request, which bounds each write but
not their number.

Rated MEDIUM because this app is a deliberately minimal demo with no user model and
non-durable data. **In a real deployment this is HIGH** — an unauthenticated write to a
financial record set.

**Remediation:** apply the same key check to `POST` (and to `GET` if the data is not meant
to be public) by extracting the auth block at `src/expenses.js:66-81` into a
`requireApiKey` middleware and mounting it on every mutating route; add a rate limiter
(`express-rate-limit`) and a hard cap on `store` size.

### SEC-003 — MEDIUM — Attacker-controlled `category` is used as an object key in `/summary` (object injection)

**Location:** `src/expenses.js:51-54` — inside the handler rewritten by Change 1

```js
const byCategory = {};
for (const e of rows) {
  byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
}
```

`category` is a free-form string validated only as "non-empty" (`src/validation.js:16-18`),
and it arrives through the unauthenticated POST of SEC-002. Using it as a key on an object
literal means inherited `Object.prototype` members are read by `byCategory[e.category]`
before the write. Reproduced against the live app:

- `category: "__proto__"` → the write is silently swallowed by V8's `__proto__` setter
  (a number is not an object, so it is discarded). Result:
  `{"count":3,"total":58.24,"byCategory":{"transport":40,"food":8.25}}` — the amount is
  counted in `total` but the category vanishes from the breakdown, so the two disagree.
  This is precisely the class of `/summary` inconsistency Change 1 was meant to eliminate.
- `category: "constructor"` → `(byCategory["constructor"] || 0)` resolves to
  `Object` (truthy), and `Object + 7` string-concatenates. Result:
  `{"byCategory":{"constructor":"function Object() { [native code] }7"}}` — a number field
  becomes a string containing engine internals.
- `category: "toString"` behaves identically.

**Why it's exploitable:** one unauthenticated POST corrupts the summary for every consumer
— the breakdown either loses money silently or returns a type-confused string where a
number is contracted. Downstream clients doing arithmetic on `byCategory` values get `NaN`
or a concatenation. `Object.prototype` itself is **not** polluted (verified:
`({}).__proto__ === Object.prototype` still holds), which is why this is MEDIUM and not
HIGH — the impact is data integrity and type confusion (CWE-1321-adjacent, CWE-843), not
remote prototype pollution.

**Remediation:** build the accumulator on a null-prototype object and normalise the write:

```js
const byCategory = Object.create(null);
for (const e of rows) {
  byCategory[e.category] = (byCategory[e.category] ?? 0) + e.amount;
}
```

`Object.create(null)` removes the inherited members entirely and makes `__proto__` an
ordinary own key; `??` avoids the truthiness trap. Additionally, constrain `category` in
`validateExpense` to a charset/length allow-list (e.g. `/^[\w -]{1,64}$/`).

### SEC-004 — LOW — `description` is never validated and is echoed back verbatim

**Location:** `src/validation.js:4-25` (no `description` branch) → `src/expenses.js:36-38`
(destructured and stored) → `src/expenses.js:41-44` (returned)

`validateExpense` checks `amount`, `category`, and `date` and ignores `description`
entirely. Confirmed: `validateExpense({amount:1, category:'x', date:'2026-01-01',
description:{a:1}})` returns `[]`, and a posted `"<script>alert(1)</script>"` is stored and
returned unchanged by `GET /expenses`.

**Why it's exploitable:** not directly XSS today — `res.json` sets
`application/json; charset=utf-8`, so a browser will not execute it. The risk is stored-XSS
by proxy (CWE-79): any consumer that renders `description` into HTML without escaping —
a dashboard, a report generator, an email template — executes attacker script that was
injected through the unauthenticated POST of SEC-002. There is also no length or type
bound, so an object, an array, or a ~100 kB string is accepted per record.

**Remediation:** validate it in `validateExpense` alongside the other fields — reject
non-string values and cap the length:

```js
if (description !== undefined &&
    (typeof description !== 'string' || description.length > 500)) {
  errors.push({ field: 'description', message: 'description must be a string of at most 500 characters' });
}
```

Escape on render at every consumer; do not rely on the API for that.

### SEC-005 — LOW — Key-length side channel in front of the constant-time comparison

**Location:** `src/expenses.js:73-77`

```js
const providedBuf = Buffer.from(provided);
const expectedBuf = Buffer.from(API_KEY);
const authorized =
  providedBuf.length === expectedBuf.length &&
  crypto.timingSafeEqual(providedBuf, expectedBuf);
```

The length guard is *necessary* — `timingSafeEqual` throws on unequal-length buffers — but
`&&` short-circuits, so a wrong-length key returns measurably faster than a right-length
one. The byte comparison is constant-time; the length check is not.

**Why it's exploitable:** an attacker who can time many `DELETE` requests can recover the
key's byte length, shrinking the brute-force space. This is a genuine but minor leak: it
discloses one integer, not key material, and the surrounding HTTP jitter makes it hard to
measure remotely. Noted as a hardening gap, not a defect in the Change 3 fix.

**Remediation:** hash both sides to a fixed width before comparing, which removes the
length branch entirely:

```js
const digest = (s) => crypto.createHash('sha256').update(s).digest();
const authorized = crypto.timingSafeEqual(digest(provided), digest(API_KEY));
```

### SEC-006 — LOW — Change 4's absolute tolerance weakens the decimal check and mis-rejects large amounts

**Location:** `src/validation.js:28` — `return Math.abs(Math.round(n * 100) - n * 100) < 1e-9;`

The fix correctly unblocks the values `context/bugs/004` was about (`19.99`, `8.29`, `0.07`
all accepted; `1.005` still rejected — verified). But a *fixed absolute* epsilon does not
scale with magnitude, so the check is now wrong at both ends. Verified:

| Input | Result | Expected |
|-------|--------|----------|
| `19.99` | accepted | accepted ✅ |
| `1.005` | rejected | rejected ✅ |
| `1.0000000000001` | **accepted** | should be rejected — 13 decimal places |
| `12345678901.994` | **rejected** | a legitimate 3-dp value, but so is `12345678901.99` at that magnitude |

**Why it matters:** this is an input-validation weakening at a trust boundary (CWE-1284),
not a memory-safety issue — hence LOW. Over-precise amounts that slip through propagate
into `total` and `byCategory` sums where they accumulate rounding drift; conversely,
legitimate large amounts are rejected because at ~1e10 the float spacing already exceeds
`1e-9`.

**Remediation:** validate the decimal places on the *decimal representation* rather than
by float arithmetic, which sidesteps IEEE-754 entirely:

```js
function hasAtMostTwoDecimals(n) {
  if (!Number.isFinite(n)) return false;
  const [, frac = ''] = String(n).split('.');
  return !frac.includes('e') && frac.length <= 2;
}
```

(Better still for money: accept integer minor units, or a decimal string parsed with a
fixed-point library, and never hold currency in a binary float.)

### SEC-007 — LOW — The formerly-hardcoded secret still exists in git history and in the repo's docs

**Location:** `fix-summary.md:129,132,141`, `implementation-plan.md:127,255,258`,
`context/bugs/003/bug-context.md:13,28`, `research/codebase-research.md:112,235`,
`research/verified-research.md:48`; plus every commit that contained
`src/expenses.js` before Change 3.

Change 3 removed the literal from `src/`, which is what `context/bugs/003` asked for. It
did not — and could not — remove it from history or from the surrounding documentation,
where `sk_live_9f8c2b1a7e4d` still appears fourteen times, including as the value the
verification steps tell an operator to actually run the server with.

**Why it matters:** relocating a secret to an environment variable does not *rotate* it
(CWE-540). In a real system, anyone with repo read access — or any fork, mirror, or CI log
— still holds the live credential, and the migration would provide false assurance. Rated
LOW **only** because this value is a fabricated teaching artifact that never guarded
anything real; against a genuine secret this would be HIGH and would require immediate
rotation.

**Remediation:** for this repo, no action is required beyond awareness — but state in
`README.md` that the value is fictitious and that a real migration must be paired with
rotation. Generally: rotate the credential at the issuer the moment it is known to have
been committed, treat history rewriting as insufficient on its own, and use a placeholder
(`API_KEY=<your-key>`) in documentation.

### SEC-008 — INFO — No security headers, no rate limiting, no CORS policy

**Location:** `src/app.js:6-11` — `createApp()` mounts only `express.json()` and the router

No `helmet` (so no `X-Content-Type-Options`, `X-Frame-Options`, or HSTS), no rate limiter on
any route including the credentialed `DELETE`, and no explicit CORS configuration. The
absence of CORS headers is a browser-side default-deny for cross-origin reads, so this is
not a live gap today; it becomes one the moment CORS is enabled without thought. The
missing rate limit is what makes SEC-002's flooding path and SEC-005's timing measurement
practical.

**Remediation:** `app.use(helmet())` and `app.use(rateLimit({ windowMs: 60_000, max: 100 }))`
in `createApp()`; if cross-origin access is ever needed, configure `cors` with an explicit
origin allow-list rather than `*`.

**CSRF** was considered and is not applicable: the API is JSON-only with no cookie or
session authentication (`src/app.js:6-11` mounts no session middleware), and authorization
travels in a custom `x-api-key` header, which a cross-site form post cannot set.

### SEC-009 — INFO — The `API_KEY` requirement introduced by Change 3 is undocumented

**Location:** `src/expenses.js:10,69` vs. `HOWTORUN.md`, `README.md` (neither mentions `API_KEY`)

Fail-closed is the correct behaviour, and the guard at `src/expenses.js:69` implements it
properly. But neither operator-facing document tells anyone to set the variable, so a
reader following `HOWTORUN.md` gets `npm start` and a `DELETE` that returns `401` forever
with no explanation. `.gitignore` already excludes `.env`, but no `.env.example` exists.

**Remediation:** document `API_KEY=<your-key> npm start` in `HOWTORUN.md`, add a
committed `.env.example` with a placeholder (not the value from SEC-007), and consider
logging a startup warning when `API_KEY` is unset so the failure mode is self-explanatory.

### SEC-010 — INFO — Dependency audit is clean

**Location:** `package.json:10-16`; `express@4.22.2`, `jest@29.7.0`, `supertest@7.2.2`

`npm audit` reports **0 vulnerabilities** across 356 resolved packages (69 prod, 288 dev,
1 optional). Change 3's only new dependency is Node's built-in `crypto` — no third-party
package was added, and `crypto.timingSafeEqual` is the correct primitive, used correctly.
No finding.

## Verified Remediations

### ✅ `context/bugs/003` — hardcoded secret + insecure comparison — **FULLY REMEDIATED**

The agent definition requires *both* halves; both are present.

| Requirement | Status | Evidence |
|---|---|---|
| Secret read from the environment | ✅ | `src/expenses.js:10` — `const API_KEY = process.env.API_KEY;` |
| Literal removed from source | ✅ | `grep -rn "sk_live_9f8c2b1a7e4d" src/` → no matches (repo-wide hits are docs only, see SEC-007) |
| Loose `==` replaced | ✅ | `src/expenses.js:75-77` — no `==` remains in the handler |
| Constant-time comparison | ✅ | `src/expenses.js:77` — `crypto.timingSafeEqual(providedBuf, expectedBuf)`, `crypto` required at `:1` |
| Guarded against `timingSafeEqual`'s unequal-length throw | ✅ | `src/expenses.js:76` — length checked before the call (side channel noted as SEC-005) |
| Fails closed when `API_KEY` is unset | ✅ | `src/expenses.js:69-71` — `!API_KEY` → `401` before any comparison |
| Rejects non-string / missing header | ✅ | `src/expenses.js:69` — `typeof provided !== 'string'` → `401`; prevents `undefined`/array reaching `Buffer.from` |

Behaviour confirmed against the running app via `supertest`:

```
DELETE /expenses/1  (no x-api-key header)     -> 401
DELETE /expenses/1  (x-api-key: nope)         -> 401
DELETE /expenses/1  (x-api-key: <correct>)    -> 204
```

The type-loose `==` of the original defect also allowed `provided` to be coerced; the new
`typeof provided !== 'string'` check closes that path explicitly. **This finding is closed.**

### ✅ Changes 1, 2, and 4 introduce no new injection or authorization weakness

- **Change 1** (`src/expenses.js:49`, `/summary` now uses `filterExpenses`) — the filter
  path itself is safe: `category` is compared with strict `===` (`:17`), so an object or
  array smuggled in via `?category[$ne]=x` simply fails to match rather than being
  interpreted; `Date.parse` on a non-string yields `NaN`, and every comparison against
  `NaN` is `false`, so a malformed range returns an empty list rather than throwing.
  Verified: `?category[]=food` → `200 []`, `?to[]=2026-01-31` → `200` with a correctly
  filtered list. The object-key accumulator further down the same handler is SEC-003.
- **Change 2** (`src/expenses.js:25`, `<` → `<=`) — a pure comparison-operator change on
  parsed timestamps. No security surface.
- **Change 4** (`src/validation.js:28`) — arithmetic only; no injection surface. Its
  loosening of the bound is SEC-006.
- **No injection sinks anywhere in scope:** no SQL/NoSQL (the store is an in-process array,
  `src/store.js:4`), no `child_process`/`exec`, no `eval`/`new Function`, no `fs` path
  built from user input, no template rendering. `Number(req.params.id)` (`src/expenses.js:59,83`)
  yields `NaN` for junk input, which `find`/`findIndex` resolve to a clean `404`.

## References

Files and line ranges reviewed:

- `src/expenses.js:1-91` — all five route handlers plus `filterExpenses` and the exports
  - `:1` — `crypto` require added by Change 3
  - `:10` — `API_KEY` now from `process.env` (Change 3 · verified remediation)
  - `:13-29` — `filterExpenses`; `:25` is Change 2's inclusive upper bound
  - `:31-39` — `POST /expenses` (**SEC-002**, **SEC-004**)
  - `:41-44` — `GET /expenses`
  - `:46-56` — `GET /summary`; `:49` is Change 1, `:51-54` is **SEC-003**
  - `:58-64` — `GET /expenses/:id`
  - `:66-88` — `DELETE /expenses/:id`; `:69-71` fail-closed, `:73-77` constant-time compare
    (**verified remediation**, side channel **SEC-005**)
- `src/validation.js:1-32` — `validateExpense` and `hasAtMostTwoDecimals`
  - `:4-25` — no `description` branch (**SEC-004**)
  - `:16-18` — `category` validated as non-empty string only (feeds **SEC-003**)
  - `:28` — Change 4's tolerance (**SEC-006**)
- `src/app.js:1-14` — `createApp()`; `:6-11` middleware stack (**SEC-001**, **SEC-008**)
- `src/index.js:1-19` — entry point, seed data, `PORT` handling; no `NODE_ENV` (**SEC-001**)
- `src/store.js:1-35` — in-memory store; `:4` unbounded array (**SEC-002**)
- `package.json:1-17` — scripts and dependency set (**SEC-010**)
- `.gitignore:1-4` — `.env` already excluded (**SEC-009**)
- `fix-summary.md:1-167` — change inventory defining this review's scope
- `context/bugs/003/bug-context.md:1-40` — seeded security defect's acceptance criteria
- `git diff -- src/` — authoritative before/after for Changes 1–4

Commands run (read-only): `git status`, `git diff -- src/`, `npm audit`, `npm ls`,
`grep -rn "sk_live_9f8c2b1a7e4d"`, and a `supertest`/`node` probe executed from the session
scratchpad directory. **No file in `src/` or `tests/` was created, modified, or deleted by
this agent.**
