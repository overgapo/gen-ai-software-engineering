# Screenshots

Evidence for the homework-4 submission. `TASKS.md` requires four subjects; the PR body
should embed 3–5 of these images and must stand on its own.

Suggested filenames (numbered so they sort in pipeline order):

| File | What to capture |
|------|-----------------|
| `01-pipeline-run.png` | `./run-pipeline.sh` in the terminal — the six `▶ N/6 <agent> [model]` headers with their `✔ … → <artifact>` lines. Shows single-command execution **and** the per-agent model selection. |
| `02-fixes-applied.png` | `git diff src/` after the run (or `fix-summary.md` open) — the before/after of the three seeded defects. |
| `03-security-scan.png` | `security-report.md` — findings with severity, `file:line`, and remediation. |
| `04-unit-tests.png` | `npm test` output, green — plus a glimpse of the generated `tests/*.test.js` or `test-report.md`. |

Optional extras worth having:

- `05-bugs-before.png` — the `curl` calls from `HOWTORUN.md` showing the three defects
  reproducing **before** the pipeline (makes the before/after story concrete).
- `06-verified-research.png` — `research/verified-research.md` showing the quality level and
  PASS/FAIL gate produced via the research-quality skill.

Use PNG, crop to the relevant terminal/editor region, and keep the text legible.
