"""Run the installed CAD snapshot CLI with the machine's existing Chrome.

The CAD skill's Playwright package is present, but its optional bundled
Chromium executable is not installed.  This narrow runtime adapter injects the
already-installed system Chrome executable into BrowserType.launch; all
rendering logic remains the unmodified CAD skill snapshot implementation.
"""

from __future__ import annotations

import runpy
from pathlib import Path

from playwright.async_api import BrowserType


SYSTEM_CHROME = Path(
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)
CAD_SNAPSHOT = Path(
    r"C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9"
    r"\skills\cad\scripts\snapshot"
)

if not SYSTEM_CHROME.is_file():
    raise FileNotFoundError(SYSTEM_CHROME)

_original_launch = BrowserType.launch


async def _launch_with_system_chrome(self, **kwargs):
    kwargs.setdefault("executable_path", str(SYSTEM_CHROME))
    return await _original_launch(self, **kwargs)


BrowserType.launch = _launch_with_system_chrome
runpy.run_path(str(CAD_SNAPSHOT), run_name="__main__")

