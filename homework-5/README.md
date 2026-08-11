# Homework 5 — MCP Server Configuration

**Author / student:** ash (`ash@firelink.media`)

Four MCP servers wired into Claude Code from this directory: three third-party ones
(**GitHub**, **Filesystem**, **Jira**) and one **written from scratch** with FastMCP that serves
word-limited slices of `lorem-ipsum.md`.

All four are registered at **project scope**, so the whole configuration lives in the committed
[`.mcp.json`](.mcp.json) and travels with the repository.

---

## Resources vs. Tools

The two MCP primitives the custom server demonstrates:

- **Resources** are URIs that Claude *reads from* — files, API endpoints, database rows. Claude
  pulls the content in as context; reading one has no side effects.
- **Tools** are actions Claude *invokes* — reading a file, running a command, creating a ticket.
  They take arguments, do work, and return a result.

The custom server exposes the same text through both, on purpose: `lorem://text` as a resource
and `read` as a tool.

---

## What is configured

| Server | Transport | Auth | What it does here |
|--------|-----------|------|-------------------|
| `github` | HTTP (`api.githubcopilot.com/mcp/`) | PAT via `${GITHUB_PAT}` header | Lists PRs, commits and issues on this fork |
| `filesystem` | stdio (`npx @modelcontextprotocol/server-filesystem`) | none — path-scoped | Lists and reads files under `homework-5/` |
| `jira` | SSE (`mcp.atlassian.com/v1/sse`) | OAuth via `claude mcp login` | Queries a real Jira project for recent bugs |
| `lorem-ipsum` | stdio (`uv run … server.py`) | none | Custom FastMCP server — resource + `read` tool |

**No credentials are stored in this repository.** Jira uses OAuth 2.1 — Claude Code keeps that token
in per-user state outside the repo. GitHub's remote MCP endpoint does *not* support dynamic client
registration, so an OAuth login from a third-party client is impossible; it takes a personal access
token instead, which `.mcp.json` references as `${GITHUB_PAT}` and Claude Code expands from the
environment at load time. Either way `.mcp.json` holds nothing but URLs, commands and variable
names — there is no secret to leak and nothing to redact before committing.

---

## The custom MCP server

[`custom-mcp-server/server.py`](custom-mcp-server/server.py) — a FastMCP server named
`lorem-ipsum` that reads [`custom-mcp-server/lorem-ipsum.md`](custom-mcp-server/lorem-ipsum.md)
(123 words) and returns the first *N* whitespace-separated words.

It publishes three entry points:

| Kind | URI / name | `word_count` |
|------|-----------|--------------|
| Resource | `lorem://text` | fixed at the default, 30 |
| Resource template | `lorem://text/{word_count}` | taken from the URI |
| Tool | `read` | optional argument, defaults to 30 |

Resource and tool both delegate to a single private helper, `_read_words()`, so the two can never
drift apart — the tool genuinely returns the resource's content instead of reimplementing the
slicing. Requesting more words than the file holds returns everything available rather than
padding; a negative `word_count` raises.

Dependencies are declared in
[`custom-mcp-server/requirements.txt`](custom-mcp-server/requirements.txt), which names `fastmcp`
explicitly.

### Verified behaviour

Driven over real stdio with a `fastmcp.Client`, not just imported:

```
TOOLS:      [('read', {'word_count': {'default': 30, 'type': 'integer', …}})]
RESOURCES:  ['lorem://text']
TEMPLATES:  ['lorem://text/{word_count}']

resource lorem://text        -> 30 words
resource lorem://text/10     -> 10 words
tool read()                  -> 30 words, byte-identical to the resource
tool read(word_count=5)      -> 'Lorem ipsum dolor sit amet,'
tool read(word_count=1000)   -> 123 words (the whole file)
```

---

## Running it

See **[HOWTORUN.md](HOWTORUN.md)** for install, startup, connecting the MCP config, and testing the
`read` tool. The one thing worth repeating here: `.mcp.json` is discovered relative to the
directory Claude Code is launched from, so you must start `claude` **inside `homework-5/`**.

---

## AI tools used

- **Claude Code (Opus 5)** — the whole assignment: analysing `TASKS.md` against the course
  submission rules, writing `server.py`, `lorem-ipsum.md` and the docs, registering all four
  servers via `claude mcp add -s project`, and writing the stdio verification client.
- **Web search via Claude Code** — to confirm the current remote-MCP endpoints for GitHub
  (`api.githubcopilot.com/mcp/`) and Atlassian (`mcp.atlassian.com/v1/sse`) rather than relying on
  the model's training data, and to work out each one's auth model — Atlassian supports OAuth
  dynamic client registration, GitHub does not and needs a bearer PAT.

What I verified myself rather than trusting the model: the server was exercised end-to-end over
stdio with assertions on the 30-word default and on tool/resource equality; `claude mcp list` was
run to confirm all four servers are registered; the Jira OAuth login, the GitHub PAT and every
screenshot in `docs/screenshots/` are real calls against my own GitHub and Jira accounts.

## Screenshots

In [`docs/screenshots/`](docs/screenshots/) — one MCP call result per server:
`github-mcp-result.png`, `filesystem-mcp-result.png`, `jira-or-notion-mcp-result.png`,
`custom-mcp-read-tool-result.png`. Jira titles and descriptions are redacted; only issue keys are
visible.
