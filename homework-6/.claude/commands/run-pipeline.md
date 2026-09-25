---
description: Run the transaction processing pipeline end-to-end and report the outcome
argument-hint: [optional path to an input file; defaults to sample-transactions.json]
allowed-tools: Bash, Read, Glob
---

# /run-pipeline

Run the transaction processing pipeline end to end and report what happened.

Input file: **$ARGUMENTS** (empty → `sample-transactions.json`).

## Steps

1. **Check the input exists.** If the file is missing, stop and say so — do not
   invent transactions or fall back to a different file.
2. **Run the pipeline**, which clears `shared/` first:

   ```bash
   .venv/bin/python orchestrator.py --clean
   ```

   Use `--input <path>` when an argument was given. If `.venv/` does not exist,
   say so and point at `HOWTORUN.md` rather than installing anything.
3. **Report the summary** from the run: totals by status, and the settled gross
   / fees / net line.
4. **Report every transaction that did not settle**, one line each, with its
   reason code and the stage that decided it:
   - `rejected` → what the validator refused and why
   - `held` → the risk score with its signals, or the compliance reason
5. **Reconcile.** Confirm the number of result files in `shared/results/`
   (excluding `summary.json`) equals the number of input records. The
   orchestrator exits non-zero if it does not — if that happens, report it as a
   **failure**, not a caveat. A record that never reached a terminal state is a
   transaction nobody is looking for.

## Reporting rules

- Quote the actual numbers from the run. Never describe an expected outcome you
  did not observe.
- If the run exits non-zero, lead with that. Do not bury it under the summary.
- Do not "fix" a surprising outcome by re-running with different flags. Report
  it, then investigate if asked.
- Never print an account number or a transaction description in the summary —
  they are in the result files, but they are not part of a status report.
