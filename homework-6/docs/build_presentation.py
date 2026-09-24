#!/usr/bin/env python3
"""Render docs/presentation.html to docs/presentation.pdf with headless Chrome.

Chrome is used rather than a PDF library because the deck is already an HTML
document: this keeps one source of truth instead of a layout that has to be
maintained twice.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DOCS = Path(__file__).resolve().parent
SOURCE = DOCS / "presentation.html"
OUTPUT = DOCS / "presentation.pdf"

CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
)


def find_chrome() -> str:
    for candidate in CANDIDATES:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    raise SystemExit("no Chrome/Chromium found; install one or export the deck by hand")


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"missing {SOURCE}")

    previous_mtime = OUTPUT.stat().st_mtime if OUTPUT.exists() else 0

    with tempfile.TemporaryDirectory() as profile:
        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            f"--user-data-dir={profile}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={OUTPUT}",
            SOURCE.as_uri(),
        ]
        try:
            # Chrome writes the PDF and then sometimes lingers instead of
            # exiting, so this is bounded rather than trusting it to finish.
            subprocess.run(command, check=True, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            pass

    if not OUTPUT.exists() or OUTPUT.stat().st_mtime == previous_mtime:
        raise SystemExit("Chrome did not produce a new PDF")

    size = OUTPUT.stat().st_size
    print(f"wrote {OUTPUT.relative_to(DOCS.parent)} ({size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
