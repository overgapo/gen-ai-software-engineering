# Screenshots

One MCP call result per configured server. Filenames are fixed by `TASKS.md` — keep them exactly
as listed.

| File | Server | What it must show |
|------|--------|-------------------|
| `github-mcp-result.png` | `github` | A prompt and the GitHub MCP tool result — e.g. recent pull requests on this fork |
| `filesystem-mcp-result.png` | `filesystem` | A prompt and the Filesystem MCP result — a directory listing or file read under `homework-5/` |
| `jira-or-notion-mcp-result.png` | `jira` | The prompt *"Give me the tickets of the last 5 bugs on a project"* **and** its response |
| `custom-mcp-read-tool-result.png` | `lorem-ipsum` | The `read` tool returning its 30-word default |

## Before capturing

Start Claude Code inside `homework-5/` (otherwise `.mcp.json` is not loaded), approve the
project-scope servers, and complete `claude mcp login` for `github` and `jira`. See
[`../../HOWTORUN.md`](../../HOWTORUN.md).

Each screenshot should include **both the prompt and the response**, and ideally the MCP tool-call
line (`mcp__<server>__<tool>`) so it is visible which server answered.

## ⚠️ Redaction — Jira only

`TASKS.md` is explicit: represent the working response with **ticket numbers only**. Before
capturing `jira-or-notion-mcp-result.png`, blur or crop:

- issue **summaries / titles** and descriptions
- reporter and assignee names, avatars, email addresses
- any customer, product or internal project detail beyond the project key

Leave visible: the issue keys (e.g. `PROJ-1234`), the issue type (`Bug`), and status. That is
enough to prove the call worked.
