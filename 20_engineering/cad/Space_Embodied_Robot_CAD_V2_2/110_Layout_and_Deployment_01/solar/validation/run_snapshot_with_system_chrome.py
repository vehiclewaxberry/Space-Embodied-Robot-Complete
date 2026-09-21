"""Run the installed CAD snapshot engine with the existing system Chrome.

The installed Playwright package points to a missing managed Chromium build.
This local wrapper changes only the browser executable argument at runtime; it
does not modify the CAD skill, install a browser, or write outside this solar
task directory.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SNAPSHOT_MAIN = Path(
    r"C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9"
    r"\skills\cad\scripts\snapshot\__main__.py"
)
SYSTEM_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def _load_snapshot_module():
    spec = importlib.util.spec_from_file_location("cad_snapshot_runtime", SNAPSHOT_MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load snapshot module: {SNAPSHOT_MAIN}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if not SYSTEM_CHROME.is_file():
        raise RuntimeError(f"System Chrome not found: {SYSTEM_CHROME}")
    snapshot = _load_snapshot_module()

    async def start_with_system_chrome(self) -> None:
        if self.started:
            return
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                executable_path=str(SYSTEM_CHROME),
                headless=True,
                timeout=snapshot.RENDER_BROWSER_STARTUP_TIMEOUT_MS,
            )
            self.context = await self.browser.new_context(
                viewport={
                    "width": snapshot.SIMPLE_RENDER_WIDTH,
                    "height": snapshot.SIMPLE_RENDER_HEIGHT,
                },
                device_scale_factor=1,
            )
            self.page = await self.context.new_page()
            await self.page.route(snapshot.SNAPSHOT_ROUTE_GLOB, self.handle_route)
            await self.page.goto(
                snapshot.SNAPSHOT_RENDER_URL,
                wait_until="load",
                timeout=snapshot.DEFAULT_TIMEOUT_SECONDS * 1000,
            )
            await self.page.wait_for_function(
                "typeof window.__snapshotRender === 'function'",
                timeout=snapshot.DEFAULT_TIMEOUT_SECONDS * 1000,
            )
            self.started = True
        except Exception:
            await self.close()
            raise

    snapshot.BatchSnapshotRenderer.start = start_with_system_chrome
    return snapshot.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
