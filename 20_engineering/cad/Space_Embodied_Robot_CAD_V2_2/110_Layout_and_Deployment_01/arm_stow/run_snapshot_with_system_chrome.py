"""Run the installed CAD snapshot tool with the installed system Chrome.

The Playwright Python package is present, but its private downloaded Chromium
payload is not.  This wrapper changes only the browser channel; all job
resolution, CAD rendering and output writing remain owned by the installed
cad:cad snapshot implementation.
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path

from playwright.async_api import BrowserType


ROOT = Path(__file__).resolve().parent
RUNTIME_TMP = ROOT / ".snapshot_runtime_tmp"
RUNTIME_TMP.mkdir(exist_ok=True)
os.environ["TEMP"] = str(RUNTIME_TMP)
os.environ["TMP"] = str(RUNTIME_TMP)

CAD_SNAPSHOT_MAIN = Path(
    r"C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9\skills\cad\scripts\snapshot\__main__.py"
)

_playwright_launch = BrowserType.launch


async def _launch_system_chrome(self, *args, **kwargs):
    kwargs["channel"] = "chrome"
    return await _playwright_launch(self, *args, **kwargs)


BrowserType.launch = _launch_system_chrome
runpy.run_path(str(CAD_SNAPSHOT_MAIN), run_name="__main__")
