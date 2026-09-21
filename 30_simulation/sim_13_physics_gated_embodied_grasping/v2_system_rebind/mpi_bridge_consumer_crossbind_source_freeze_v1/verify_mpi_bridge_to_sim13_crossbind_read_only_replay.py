from __future__ import annotations

import json
from pathlib import Path

from crossbind.bridge import build_crossbind_record
from crossbind.negative_controls import run_negative_controls
from crossbind.package import find_repo_root, validate_frozen
from crossbind.source_bundle import load_source_bundle
from crossbind.strict_io import inventory_snapshot


if __name__ == "__main__":
    package_root = Path(__file__).resolve().parent
    repo_root = find_repo_root(package_root)
    before = inventory_snapshot(package_root)
    validation = validate_frozen(package_root, repo_root)
    bundle = load_source_bundle(repo_root)
    record = build_crossbind_record(bundle)
    controls = run_negative_controls(bundle, record)
    after = inventory_snapshot(package_root)
    if before != after:
        raise SystemExit("READ_ONLY_REPLAY_INVENTORY_CHANGED")
    print(json.dumps({
        "status": "PASS_READ_ONLY_REPLAY",
        "inventory_unchanged": True,
        "files": len(after["files"]),
        "directories": len(after["directories"]),
        "negative_controls": len(controls),
        "validation_checks": validation["passed"],
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "writes": 0,
        "release_credit": False,
    }, ensure_ascii=False, sort_keys=True, indent=2))
