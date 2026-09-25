---
description: Validate transactions without running the pipeline (dry run, writes nothing)
argument-hint: [optional path to an input file; defaults to sample-transactions.json]
allowed-tools: Bash, Read, Glob
---

# /validate-transactions

Check every transaction against the validation rules **without processing
anything**. Nothing is written to `shared/`, so this is safe to run at any time,
including against a completed run you do not want to disturb.

Input file: **$ARGUMENTS** (empty → `sample-transactions.json`).

## Steps

1. Run the validator in dry-run mode:

   ```bash
   .venv/bin/python pipeline/validator.py --dry-run
   ```

   Add `--input <path>` when an argument was given.
2. Report: **total**, **valid**, **invalid**.
3. Show the per-transaction table the command prints, and for every invalid row
   give its reason code and the detail.
4. Group the invalid rows by reason code when there is more than one of a kind —
   five records failing for the same reason is a producer problem, and that
   pattern is the useful finding.

## Notes

- The command exits `1` when any record is invalid. That is the expected result
  for `sample-transactions.json`, which deliberately contains two bad records
  (`TXN006` unsupported currency, `TXN007` negative amount) — a non-zero exit
  here is information, not a failure of the command.
- Validation is first-failure-wins: a record broken in two ways reports only the
  first check it failed, in the order given in `specification.md` §7.1. If you
  need the full list of everything wrong with a record, say so — that is a
  different question from what this command answers.
- This command never modifies anything. If you find yourself wanting to fix a
  record, that is a separate, explicit task.
