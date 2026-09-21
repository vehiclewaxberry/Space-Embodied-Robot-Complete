#!/usr/bin/env python3
"""Delete only the twelve verified diagnostic STEP GLB caches in this package."""

from __future__ import annotations

import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
CACHE = PACKAGE / "07_reviews/cad_cache"
CAD = PACKAGE / "01_cad"
EXPECTED = {
    ".R_RC_CHN_L2_BASE_LINK2_V1.step.glb",
    ".R_RC_CHN_L2_LINER_LINK2_V1.step.glb",
    ".R_RC_CHN_L2_WALL_A_LINK2_V1.step.glb",
    ".R_RC_CHN_L2_WALL_B_LINK2_V1.step.glb",
    ".R_RC_CLP_J2_MOV_LINK2_V1.step.glb",
    ".R_RC_CLP_L2_01_LINK2_V1.step.glb",
    ".R_RC_CLP_L2_02_LINK2_V1.step.glb",
    ".R_RC_GDE_J3_SADDLE_LINK2_V1.step.glb",
    ".R_RC_GDE_J3_SADDLE_LINER_LINK2_V1.step.glb",
    ".R_RC_TRK_J3_RAIL_LINK2_V1.step.glb",
    ".R_RC_TRK_J3_STOP_A_LINK2_V1.step.glb",
    ".R_RC_TRK_J3_STOP_B_LINK2_V1.step.glb",
}


def main() -> None:
    package = PACKAGE.resolve()
    cache = CACHE.resolve()
    if cache.parent != (package / "07_reviews").resolve():
        raise RuntimeError("cache directory escaped package review boundary")
    files = sorted(path for path in cache.iterdir() if path.is_file())
    if {path.name for path in files} != EXPECTED:
        raise RuntimeError(f"diagnostic cache set drift: {[path.name for path in files]}")
    for path in files:
        if path.resolve().parent != cache:
            raise RuntimeError(f"cache file escaped exact directory: {path}")
    for path in files:
        path.unlink()
    if any(cache.iterdir()):
        raise RuntimeError("cache directory is not empty after exact file cleanup")
    cache.rmdir()
    remaining_glb = sorted(path.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob("*.glb"))
    cad_files = sorted(path.name for path in CAD.iterdir() if path.is_file())
    if remaining_glb or len(cad_files) != 12 or not all(name.lower().endswith(".step") for name in cad_files):
        raise RuntimeError(f"post-cleanup boundary failed: glb={remaining_glb}, cad={cad_files}")
    print(json.dumps({"deleted_glb_files": len(files), "remaining_glb_files": 0, "cad_step_files": 12, "cache_directory_exists": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
