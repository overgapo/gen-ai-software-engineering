# Research notes — context7 queries during code generation

**Agent**: Agent 2 (code generation)
**Author**: Andrii Shukailo ([@overgapo](https://github.com/overgapo))
**MCP server**: `context7` (`npx -y @upstash/context7-mcp@latest`, server version 4.1.1)
**Tools used**: `resolve-library-id` → `query-docs`

Three queries were made while building the pipeline front-end and the custom MCP
server. Each entry records what was searched for, the library ID context7
returned, what came back, and what actually changed in the code as a result.

---

## Query 1 — Running blocking work in a FastAPI endpoint

- **Searched**: "run blocking synchronous code in a threadpool from an async path operation without blocking the event loop"
- **Library resolved**: FastAPI → **`/websites/fastapi_tiangolo`** (2 377 snippets, High reputation, benchmark 84.81)
  - Alternatives offered: `/websites/fastapi_tiangolo_reference` (71.91), `/websites/deepwiki_fastapi_fastapi` (65.83). Picked the main docs site for the highest benchmark and snippet coverage.
- **What came back** (sources `fastapi.tiangolo.com/async`, `/advanced/stream-data`):
  > "When a path operation function is declared with standard `def` instead of `async def`, FastAPI runs it in an external threadpool that is awaited, preventing the server from blocking. For trivial compute-only path operations without blocking I/O, using `async def` is generally preferred in FastAPI to avoid the overhead of threadpool execution."

- **Applied — this corrected code I had already written.** `POST /api/run` was:

  ```python
  from starlette.concurrency import run_in_threadpool

  @app.post("/api/run")
  async def trigger_run() -> JSONResponse:
      summary = await run_in_threadpool(run_pipeline, DEFAULT_INPUT, DEFAULT_SHARED, True)
      return JSONResponse(summary)
  ```

  That works, but it reaches for Starlette's primitive to re-create something
  FastAPI already does from the function signature. The docs' idiom is simply
  to declare the operation with `def`:

  ```python
  @app.post("/api/run")
  def trigger_run() -> JSONResponse:
      return JSONResponse(run_pipeline(DEFAULT_INPUT, DEFAULT_SHARED, clean=True))
  ```

  The same rule then settled the rest of `frontend/app.py`, which had been
  inconsistent: endpoints that read result files from disk (`/api/summary`,
  `/api/results`) stay plain `def` so their blocking reads land in a threadpool,
  while `GET /` became `async def` — `FileResponse` streams asynchronously on its
  own, so sending it through a threadpool worker is pure overhead. One dependency
  (`starlette.concurrency`) dropped out of the file.

---

## Query 2 — Serving the dashboard's static assets

- **Searched**: "mount StaticFiles and serve an index.html file with FileResponse from a path operation"
- **Library ID**: **`/websites/fastapi_tiangolo`** (same as above)
- **What came back** (sources `/tutorial/static-files`, `/reference/staticfiles`, `/advanced/custom-response`):

  ```python
  app.mount("/static", StaticFiles(directory="static"), name="static")
  ```

  plus the full `StaticFiles` signature — `directory`, `packages`, `html`,
  `check_dir`, `follow_symlink` — and the note that **mounted sub-applications are
  independent and their endpoints are not included in the OpenAPI docs**, and that
  `html=True` makes `StaticFiles` serve `index.html` on directory requests.

- **Applied**: kept the explicit `GET /` → `FileResponse(index.html)` route rather
  than switching the mount to `html=True`. Two reasons the docs made concrete:
  a mounted `StaticFiles` app is invisible to OpenAPI, so `html=True` would have
  left the dashboard's own entry point undocumented at `/docs`; and an explicit
  route keeps the page reachable at exactly `/` without depending on directory-
  request behaviour. `include_in_schema=False` marks it as the one route that is
  a page rather than an API.

---

## Query 3 — FastMCP tool and resource decorators

- **Searched**: "define a tool with `@mcp.tool` and a resource with `@mcp.resource` URI, then run the server over stdio"
- **Library resolved**: FastMCP → **`/prefecthq/fastmcp`** (5 040 snippets, High reputation, benchmark 85.25)
  - Alternatives: `/websites/gofastmcp` (83.66), `/llmstxt/gofastmcp_llms-full_txt` (16 756 snippets but benchmark 56.22). Picked the source repo: highest benchmark, and the installed package is `fastmcp==4.0.5`, so the repo docs track the API most closely.
- **What came back** (sources `README.md`, `docs/tutorials/create-mcp-server.mdx`, `docs/deployment/running-server.mdx`):

  ```python
  from fastmcp import FastMCP

  mcp = FastMCP(name="My First MCP Server")

  @mcp.tool
  def add(a: int, b: int) -> int:
      """Adds two integer numbers together."""
      return a + b

  @mcp.resource("resource://config")
  def get_config() -> dict:
      """Provides the application's configuration."""
      return {"version": "1.0", "author": "MyTeam"}

  @mcp.resource("greetings://{name}")          # resource template
  def personalized_greeting(name: str) -> str:
      return f"Hello, {name}!"

  if __name__ == "__main__":
      mcp.run()
  ```

  > "STDIO is the default transport for FastMCP servers. When you call `run()`
  > without arguments, your server uses STDIO transport. […] the client spawns a
  > new server process for each session and manages its lifecycle."

- **Applied** to `mcp/server.py`:
  - `@mcp.tool` is used **bare**, not called — the older `@mcp.tool()` form is not what current docs show.
  - The docstring is the tool description the client sees, and the type hints are
    the schema, so `get_transaction_status(transaction_id: str) -> dict` needs no
    hand-written JSON schema.
  - `pipeline://summary` is a plain resource (fixed URI), not a template — no
    `{placeholder}`, so it takes no arguments.
  - `mcp.run()` with no arguments is correct for the `mcp.json` entry, which
    spawns the server over stdio.
  - Because the client spawns a fresh process per session, the server keeps no
    state: every call reads `shared/results/` from disk, which is also why it can
    never serve a stale answer after a new pipeline run.

---

## Note on what context7 was *not* used for

The pipeline core is standard library only (`decimal`, `json`, `hashlib`,
`datetime`, `pathlib`, `uuid`). Rounding and precision decisions came from
`specification.md` §4 rather than from library docs — `ROUND_HALF_UP` is a policy
choice for this system, not an API question. context7's own instructions say to
use it for library and framework documentation, not for business logic, and that
line is where it was drawn.
