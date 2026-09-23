#!/usr/bin/env python3
"""Front-end for the transaction processing pipeline.

A deliberately small FastAPI app: it serves one static page and four JSON
endpoints. It holds no pipeline logic -- it reads what the pipeline wrote and
can ask the orchestrator to run again.

Note on what is exposed: the API returns the *projection* the run summary
builds, not raw result records. Result files carry the account numbers and the
customer description; a dashboard has no business shipping those to a browser
(agents.md §5).
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # pragma: no cover - script execution
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator import DEFAULT_INPUT, DEFAULT_SHARED, run_pipeline  # noqa: E402
from pipeline import config  # noqa: E402
from pipeline.models import load_record  # noqa: E402
from pipeline.reporting import build_summary  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
RESULTS_DIR = DEFAULT_SHARED / "results"
SUMMARY_PATH = RESULTS_DIR / config.SUMMARY_FILENAME

app = FastAPI(title="Transaction Pipeline Dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _current_summary() -> dict:
    """Latest summary: the stored file if present, otherwise rebuilt on read."""
    if SUMMARY_PATH.exists():
        return load_record(SUMMARY_PATH)
    if not RESULTS_DIR.exists() or not any(RESULTS_DIR.glob("*.json")):
        raise HTTPException(status_code=404, detail="no pipeline run found; run the pipeline first")
    return build_summary(RESULTS_DIR)


# On def vs async def below: FastAPI runs a path operation declared with plain
# `def` in a threadpool, and awaits an `async def` one on the event loop. So the
# endpoints that read result files from disk -- and the one that runs the whole
# pipeline -- are plain `def`, while the two that do no blocking work are
# `async def`, avoiding pointless threadpool overhead.


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    # FileResponse streams the file asynchronously by itself, so this operation
    # blocks on nothing.
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/summary")
def get_summary() -> JSONResponse:
    return JSONResponse(_current_summary())


@app.get("/api/results")
def get_results() -> JSONResponse:
    summary = _current_summary()
    return JSONResponse(
        {
            "total": summary["total"],
            "by_status": summary["by_status"],
            "totals": summary["totals"],
            "transactions": summary["transactions"],
        }
    )


@app.get("/api/results/{transaction_id}")
def get_result(transaction_id: str) -> JSONResponse:
    summary = _current_summary()
    for row in summary["transactions"]:
        if row["transaction_id"] == transaction_id:
            return JSONResponse(row)
    raise HTTPException(status_code=404, detail=f"{transaction_id} not found in the latest run")


@app.post("/api/run")
def trigger_run() -> JSONResponse:
    """Run the pipeline from scratch.

    A full run is seconds of synchronous file I/O. Declared with plain ``def``
    so FastAPI hands it to a threadpool worker -- an ``async def`` here would
    stall the event loop for the whole run and freeze every other request.
    """
    return JSONResponse(run_pipeline(DEFAULT_INPUT, DEFAULT_SHARED, clean=True))


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
