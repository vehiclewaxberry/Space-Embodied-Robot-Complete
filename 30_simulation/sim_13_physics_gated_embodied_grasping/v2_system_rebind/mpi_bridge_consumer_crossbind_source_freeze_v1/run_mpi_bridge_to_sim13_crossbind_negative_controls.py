from __future__ import annotations

import json
from pathlib import Path

from crossbind.bridge import build_crossbind_record
from crossbind.negative_controls import run_negative_controls
from crossbind.package import find_repo_root
from crossbind.source_bundle import load_source_bundle


if __name__ == "__main__":
    package_root = Path(__file__).resolve().parent
    bundle = load_source_bundle(find_repo_root(package_root))
    controls = run_negative_controls(bundle, build_crossbind_record(bundle))
    print(json.dumps({"status": "PASS", "passed": len(controls), "total": len(controls), "controls": controls}, ensure_ascii=False, sort_keys=True, indent=2))

