"""Hash this module's own source/contract files (project SIM13/14/15 pattern)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "src"))
from dh_v1.hashing import sha256_file  # noqa: E402

GROUPS = {
    "src": sorted((MODULE / "src" / "dh_v1").glob("*.py")),
    "scripts": sorted((MODULE / "scripts").glob("*.py")),
    "tests": sorted((MODULE / "tests").glob("*.py")),
    "contracts": [
        *sorted((MODULE / "00_authority").glob("*")),
        *sorted((MODULE / "01_host_manifest").glob("*")),
        *sorted((MODULE / "02_frames_units").glob("*")),
        *sorted((MODULE / "03_cad_intake").glob("*")),
        *sorted((MODULE / "04_step_states").glob("*")),
        *sorted((MODULE / "05_collision_assets").glob("*")),
        *sorted((MODULE / "06_plant").glob("*.yaml")) + sorted((MODULE / "06_plant").glob("*.csv")) + sorted((MODULE / "06_plant").glob("*.md")),
        *sorted((MODULE / "07_scenarios").glob("*")),
        *sorted((MODULE / "08_control_safe").glob("*")),
        *sorted((MODULE / "09_dataset").glob("*.json")) + sorted((MODULE / "09_dataset").glob("*.yaml")) + sorted((MODULE / "09_dataset").glob("*.md")),
        *sorted((MODULE / "10_backends").glob("*")),
        *sorted((MODULE / "11_verification").glob("*.json")),
    ],
}

def main() -> None:
    artifacts = []
    for group, files in GROUPS.items():
        for f in files:
            if f.is_file():
                artifacts.append({
                    "group": group,
                    "path": str(f.relative_to(MODULE)).replace("\\", "/"),
                    "sha256": sha256_file(f),
                    "bytes": f.stat().st_size,
                })
    out = {
        "schema": "DH_V1_SOURCE_MANIFEST_V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    p = MODULE / "11_verification" / "DH_V1_SOURCE_MANIFEST.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {len(artifacts)} artifacts -> {p.name}")

if __name__ == "__main__":
    main()
