# HOWTORUN — Homework 5

Everything below assumes you are in the `homework-5/` directory of a fresh clone.

```bash
cd homework-5
```

---

## 0. Prerequisites

| Tool | Why | Check |
|------|-----|-------|
| [`uv`](https://docs.astral.sh/uv/) | runs the custom Python server | `uv --version` |
| Node.js ≥ 18 (`npx`) | runs the Filesystem MCP server | `node --version` |
| Claude Code CLI | the MCP client | `claude --version` |

> ⚠️ **Do not use the system Python.** macOS ships CPython 3.9, and `fastmcp` requires **≥ 3.10** —
> `pip install fastmcp` against `/usr/bin/python3` fails. `uv` sidesteps this entirely: it fetches
> and pins CPython 3.12 on its own. Verified against **CPython 3.12.11 / fastmcp 3.4.7**.

---

## 1. Install dependencies

`uv` reads [`custom-mcp-server/requirements.txt`](custom-mcp-server/requirements.txt), which names
`fastmcp` explicitly.

**Option A — no setup at all (what `.mcp.json` uses).** `uv run` builds and caches the environment
on first launch; there is nothing to install by hand:

```bash
uv run --python 3.12 \
  --with-requirements custom-mcp-server/requirements.txt \
  custom-mcp-server/server.py
```

**Option B — an explicit virtualenv**, if you want an interpreter to poke at:

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r custom-mcp-server/requirements.txt
python custom-mcp-server/server.py
```

---

## 2. Run the custom server

Either command above starts it. **Expect it to look like it hangs**, printing a FastMCP banner and
then nothing:

```
🖥  Server:      lorem-ipsum, 3.4.7
INFO  Starting MCP server 'lorem-ipsum' with transport 'stdio'
```

That is correct. It is a **stdio** server: it holds the terminal open waiting for an MCP client on
stdin. There is no port to open and no URL to visit — do not go looking for one. `Ctrl-C` to stop.

You normally never run it by hand; Claude Code spawns it for you (step 3).

---

## 3. Connect the MCP configuration

All four servers are already registered in the committed [`.mcp.json`](.mcp.json) at **project
scope**, so there is nothing to add. Two things must be true for it to load:

### 3a. Launch Claude Code *inside* `homework-5/`

`.mcp.json` is discovered **relative to the directory `claude` is started from**, and so are the
relative paths inside it (`custom-mcp-server/server.py`, and `.` for the Filesystem server's root).
Starting Claude Code from the repository root silently loads nothing.

```bash
cd homework-5   # ← must be here
claude
```

### 3b. Approve the servers on first launch

Project-scope servers are untrusted until you approve them. On the first `claude` run inside this
directory you are prompted to approve the servers from `.mcp.json` — accept. Until then
`claude mcp list` shows them as `⏸ Pending approval`.

Verify:

```bash
claude mcp list
```

```
github: https://api.githubcopilot.com/mcp/ (HTTP) - ✔ Connected
jira: https://mcp.atlassian.com/v1/sse (SSE) - ✔ Connected
filesystem: npx -y @modelcontextprotocol/server-filesystem . - ✔ Connected
lorem-ipsum: uv run --python 3.12 … custom-mcp-server/server.py - ✔ Connected
```

### 3c. Authenticate GitHub and Jira

Both are official *remote* MCP servers, and in neither case does a credential enter this repository.

**GitHub — a personal access token in the environment.** GitHub's remote MCP endpoint only accepts
OAuth clients it has *pre-registered*; it does not support dynamic client registration, so
`claude mcp login github` cannot work against it and fails with
`Incompatible auth server: does not support dynamic client registration`. The supported path for a
third-party client is a personal access token sent as a bearer header. `.mcp.json` therefore
references `${GITHUB_PAT}` — expanded from your environment at load time, never stored in the file:

```bash
# Create a fine-grained PAT at https://github.com/settings/personal-access-tokens
# Repository access: the repositories you want visible. Permissions (read-only):
#   Contents, Metadata, Issues, Pull requests
export GITHUB_PAT=github_pat_xxxxxxxx     # put this in ~/.zshrc or a shell-sourced .env
cd homework-5 && claude                    # the variable must be set *before* launching
```

The root `.gitignore` covers `.env`, so a local `.env` file is a safe place for it.

**Jira — OAuth 2.1.** The Atlassian server does support dynamic registration; it opens a browser
once and stores credentials in per-user state outside the repo:

```bash
claude mcp login jira
```

`filesystem` and `lorem-ipsum` need no credentials.

> **Jira prerequisites:** the Atlassian remote MCP server is Cloud-only (no Server/Data Center) and
> is gated behind Rovo — a site admin must enable it under *Atlassian Admin → Settings → Rovo*. If
> `claude mcp login jira` succeeds but no tools appear, that switch is why.

---

## 4. Use and test the `read` tool

Inside `claude`, started in `homework-5/`:

```
> Use the lorem-ipsum MCP server's read tool with no arguments.
```

Returns exactly **30** words, the default:

> Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut
> labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris
> nisi

More prompts worth trying:

```
> Call the lorem-ipsum read tool with word_count 5.
> Read the lorem://text resource.
> Read the lorem://text/10 resource.
```

`read(word_count=5)` → `Lorem ipsum dolor sit amet,`
`read(word_count=1000)` → the whole file (123 words); it never pads.

### Testing it without Claude Code

Drive the server over real stdio with a FastMCP client:

```bash
uv run --python 3.12 --with-requirements custom-mcp-server/requirements.txt - <<'PY'
import asyncio
from fastmcp import Client

async def main():
    async with Client("custom-mcp-server/server.py") as c:
        print([t.name for t in await c.list_tools()])
        res = await c.read_resource("lorem://text")
        tool = await c.call_tool("read", {})
        assert len(res[0].text.split()) == 30
        assert tool.content[0].text == res[0].text
        print("resource and tool agree, 30 words")

asyncio.run(main())
PY
```

### Exercising the other three servers

```
> List the 5 most recent pull requests in this repository.        # github
> List the files in this directory and summarise the structure.   # filesystem
> Give me the tickets of the last 5 bugs on <PROJECT>.            # jira
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No MCP servers at all | `claude` launched outside `homework-5/` | `cd homework-5` and relaunch |
| `⏸ Pending approval` | project-scope servers not yet trusted | run `claude` in this directory and approve |
| `ModuleNotFoundError: fastmcp` | system Python 3.9 | use `uv run` / `uv venv --python 3.12` |
| Server "hangs" with no URL | correct — stdio transport | verify via step 4, not by looking for a port |
| `jira` connects but has no tools | Rovo not enabled on the Atlassian site | site admin enables it in Atlassian Admin |
| `github`: `Incompatible auth server: does not support dynamic client registration` | tried to OAuth into GitHub's remote MCP endpoint | use a PAT instead — see step 3c |
| `github` returns 401 | `GITHUB_PAT` unset, expired, or missing a scope | re-export the token and relaunch `claude` from `homework-5/` |
