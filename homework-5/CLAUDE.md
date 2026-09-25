# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`homework-5` is one assignment in a university course ("GenAI and Agentic AI for Software Engineering"). The parent repo (`../`) is a homework template with one directory per assignment (`homework-1` … `homework-6`); each is self-contained with its own `CLAUDE.md`, `README.md`, `HOWTORUN.md` and stack — do **not** carry another assignment's tooling or commands into here.

This directory is currently **empty scaffolding**: `TASKS.md` is the only file. `TASKS.md` is the binding assignment brief — read it first; everything below summarizes, disambiguates, and adds environment facts it doesn't cover.

## The assignment in one sentence

Register **three third-party MCP servers** (GitHub, Filesystem, and Jira *or* Notion) with the local Claude Code install, **write a fourth from scratch** with FastMCP (`custom-mcp-server/server.py`, exposing one resource + one `read` tool over `lorem-ipsum.md`), and commit the config, the code, the docs, and screenshots of each server actually answering a call.

The graded artifact is largely **evidence**, not code: `docs/screenshots/` must show a real MCP call result for each of the four servers. Task 3 specifically requires the prompt *"Give me the tickets/pages of the last 5 bugs on a project"* against a real project, with only ticket/page identifiers visible — redact titles and bodies before screenshotting.

## Environment facts that will bite

1. **This is the repo's first Python directory.** `homework-1`/`homework-2`/`homework-4` are all Node + Express + Jest; nothing here should follow them. There is no Python tooling in the repo yet — `custom-mcp-server/` brings its own.
2. **System `python3` is 3.9.5; `fastmcp` requires `>=3.10`.** `pip install fastmcp` against the system interpreter will fail. `uv` is installed (`/Users/ash/.local/bin/uv`) — use `uv venv --python 3.12` (or any ≥3.10) and pin the interpreter in `HOWTORUN.md`, since a grader reproducing on stock macOS Python hits the same wall.
3. **`.mcp.json` is discovered relative to the directory `claude` is launched from.** The deliverable lives at `homework-5/.mcp.json`, so it is only loaded when Claude Code is started *inside* `homework-5/`. State this explicitly in `HOWTORUN.md` — a config committed to the right path but never picked up is the most likely way this assignment silently fails to reproduce.
4. **Relative paths in `.mcp.json` resolve against the launch directory too.** Point the custom server at `custom-mcp-server/server.py` and the Filesystem server at a path that is stable for a fresh clone; absolute paths containing `/Users/ash/` are not reproducible for a grader.

## Secrets: the config is committed, the credentials are not

`.mcp.json` is a required deliverable and gets committed. The GitHub PAT and the Jira/Notion token must therefore **never** be literal values inside it — use `${VAR}` expansion (or `--transport http` + OAuth via `claude mcp login`, which stores credentials outside the repo) and document the required variables in `HOWTORUN.md`.

The root `.gitignore` already covers `.env`, `.env.*`, and `*.env`, so a local `.env` is safe. It does **not** ignore `mcp.json` / `.mcp.json` — that is deliberate, and it is why the token must not be inlined. Check `git diff --cached` before committing anything MCP-related.

## Commands

MCP registration (verified against the installed CLI — `claude mcp --help`):

```bash
# stdio server, project scope → writes ./.mcp.json (the committed deliverable)
claude mcp add -s project <name> -- <command> [args...]
claude mcp add -s project -e API_KEY=xxx <name> -- npx <package>   # env vars
claude mcp add -s project --transport http <name> <url>            # remote/OAuth servers
claude mcp add-json -s project <name> '<json>'                     # paste a full server block

claude mcp list          # health-checks approved servers; unapproved .mcp.json entries show ⏸
claude mcp get <name>    # details for one server
claude mcp login <name>  # OAuth for http/sse servers
claude mcp remove <name>
```

`-s project` is the scope that produces the committed `.mcp.json`; the default `local` scope writes to per-user state and leaves nothing to submit.

Custom server (once `custom-mcp-server/` exists — keep these in sync with `HOWTORUN.md`):

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r custom-mcp-server/requirements.txt   # must list fastmcp explicitly
python custom-mcp-server/server.py                     # stdio; expect no output, not a URL
fastmcp dev custom-mcp-server/server.py                # MCP Inspector — good source for screenshots
```

A stdio server that "hangs" with no output is working correctly — it is waiting for a client on stdin. Verify it via the Inspector or by calling the `read` tool from Claude Code, not by looking for a listening port.

## Custom server contract (from `TASKS.md`, easy to get wrong)

- The **resource** and the **tool** both read `lorem-ipsum.md` and both take `word_count`, defaulting to **30**, returning *exactly* that many whitespace-separated words. The tool is named `read` — that exact name is graded.
- The tool should return the resource's content rather than reimplement the slicing, so the two can't drift.
- `lorem-ipsum.md` needs comfortably more than 30 words, otherwise the default case can't demonstrate truncation.
- `requirements.txt` (or `pyproject.toml`) must name `fastmcp` explicitly — the brief checks for it as a deliverable, not just that the import works.
- Docs must include the one-line conceptual distinction: **resources** are URIs Claude reads from; **tools** are actions Claude invokes.

## Submission contract (grading gates, from `../README.md`)

- Work on the fork (`origin` = `git@github.com:overgapo/gen-ai-software-engineering.git`); **one branch per assignment** — create `homework-5-submission` (the checkout currently sits on `homework-4-submission`). The PR targets **your own fork's `main`**, never the upstream course repo. Reviewer: `Alexey-Popov`.
- The **PR body is the primary submission narrative** and must stand on its own: thorough summary, how AI was used, how to verify, plus 3–5 embedded screenshots. Bare or one-line PRs are rejected even when the branch is complete.
- Required in-repo docs: `README.md` (what was built, **author name**, AI tools used) and `HOWTORUN.md` (install, run, connect the MCP config, use/test the `read` tool).
- Screenshots go in `docs/screenshots/` — one per server, filenames as listed in `TASKS.md`.
