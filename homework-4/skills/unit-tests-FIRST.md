# Skill: FIRST Unit Tests

**Purpose.** Give the Unit Test Generator a concrete, checkable definition of what a good
unit test is, so the tests it writes for the changed code are trustworthy rather than just
present. Every test this pipeline produces must satisfy **FIRST**.

Stack for this project: **Jest** + **supertest** against the in-memory Express app
(`src/app.js` exposes `createApp()`; `src/store.js` exposes `reset()` for a clean slate).

---

## FIRST, defined and applied

### F — Fast
A unit test runs in milliseconds so the whole suite runs on every save.
- Drive the app in-process with `supertest(createApp())`. **Never** call `app.listen()` or
  bind a real port; never `sleep`, poll, or hit the network.
- No real timers or clocks. If time matters, pass explicit dates in the fixture.

### I — Independent
Tests do not depend on each other or on execution order.
- Reset shared state in `beforeEach` — call `store.reset([...])` with the fixture this test
  needs. One test's writes (POST, DELETE) must never leak into the next.
- No shared mutable module-level variables between tests. Each test builds what it needs.

### R — Repeatable
The same test gives the same result on any machine, any time, run in any order.
- No dependence on "today", timezone, locale, randomness, or environment. Seed fixed dates
  and fixed data.
- If the code under test reads an env var (e.g. the fixed API key after the security fix),
  set it deterministically inside the test, and restore it afterward.

### S — Self-validating
The test asserts a precise pass/fail outcome — no human reads the output to decide.
- Assert on concrete values: `expect(res.status).toBe(200)`, `expect(res.body.total).toBe(20.75)`.
- No `console.log`-and-eyeball. A test with no meaningful assertion is not a test.

### T — Timely
Tests are written alongside the change they cover, and they pin the *fixed* behavior.
- Cover the code the Bug Fixer actually changed, from `fix-summary.md` — not unrelated code.
- For each fixed bug, write the test that would have **failed before the fix and passes
  after**. That is the test that proves the fix and guards the regression.

---

## Boundary discipline (do not skip)

A test that only checks the easy middle of a range passes even when the bug is still there.
For every fix, test the **edge that the bug lived on**:

- Date-range fix (`<` → `<=`): include a record dated **exactly on** the `to` bound and
  assert it is returned. A mid-range date proves nothing.
- Filtered-summary fix: assert the summary of a filtered query **equals** the aggregate of
  the matching filtered list — and that it **differs** from the unfiltered total.
- Security fix (env secret + constant-time compare): assert a correct key authorizes, a
  wrong key is rejected with 401, and — where feasible — that no valid key value is
  hardcoded in the test (read it from the env you set).

## Checklist before writing `test-report.md`

- [ ] Every new test maps to a change listed in `fix-summary.md`.
- [ ] `beforeEach` resets state; no test depends on another.
- [ ] No `listen()`, no network, no real sleep, no wall-clock/random dependence.
- [ ] Each fixed bug has a test that fails on the old code and passes on the new.
- [ ] Boundary cases are covered, not just mid-range happy paths.
- [ ] Every test has a concrete assertion; the suite is green via `npm test`.
