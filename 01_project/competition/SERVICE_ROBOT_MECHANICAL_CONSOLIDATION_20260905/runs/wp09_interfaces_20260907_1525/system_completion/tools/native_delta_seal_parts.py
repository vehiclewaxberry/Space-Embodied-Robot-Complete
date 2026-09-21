"""Seal imported-part receipt hashes once; no COM/OCC and no geometry edits."""
from pathlib import Path
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parents[1]


def main():
    out = C / "results/NATIVE_DELTA_IMPORTED_PARTS.json"
    if out.exists():
        raise RuntimeError("Imported-part snapshot already exists; preserve it")
    spec = importlib.util.spec_from_file_location(
        "native_delta_delivery_validation", C / "tools/native_delta_delivery.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    manifest = C / "results/NATIVE_DELTA_INPUTS.json"
    inputs, manifest_hash = v.read(manifest), v.sha(manifest)
    expected, verified, frame_proof = v.validate_parts(inputs, manifest_hash)
    rows = []
    for proof in verified:
        ident = proof["id"]
        source = expected[ident]
        receipt_path = Path(proof["cold_receipt"]["path"])
        receipt = v.read(receipt_path)
        v.same_file(receipt_path, proof["cold_receipt"]["sha256"])
        candidates = [p for p in receipt["parts"]
                      if p.get("id") == ident
                      and p.get("status") in v.PART_STATUSES
                      and p.get("source_sha256") == source["source_sha256"]
                      and p.get("native_save", {}).get("sha256") == proof["native"]["sha256"]
                      and "source_native_volume_error_mm3" in p]
        v.require(candidates, f"Completed per-part receipt disappeared: {ident}")
        part = candidates[-1]
        # Expected hashes come from the completed import receipt. Current file
        # hashing only compares against them; it never defines expected truth.
        native_hash = part["native_save"]["sha256"]
        v.same_file(source["native_path"], native_hash)
        v.same_file(source["step_path"], source["source_sha256"])
        rows.append({
            "id": ident,
            "source_path": source["step_path"],
            "source_sha256": source["source_sha256"],
            "native_path": source["native_path"],
            "native_sha256": native_hash,
            "import_receipt": str(receipt_path),
            "import_receipt_sha256": proof["cold_receipt"]["sha256"],
            "import_batch_status": receipt.get("status"),
            "completed_part_status": part["status"],
            "source_native_volume_error_mm3": part["source_native_volume_error_mm3"],
            "cold_facts": part["part_cold_reopen"]["facts"],
            "frame_equivalence_receipt": frame_proof if ident.startswith("wing_edge_frame_") else None,
        })
    v.require(len(rows) == 138 and len({r["id"] for r in rows}) == 138,
              "Imported snapshot must cover exactly 138 unique part IDs")
    v.same_file(manifest, manifest_hash)
    result = {
        "status": "PASS_138_IMPORTED_PARTS_HASH_SNAPSHOT_SEALED",
        "input_manifest_path": str(manifest), "input_manifest_sha256": manifest_hash,
        "part_count": 138, "parts": rows, "frame_equivalence": frame_proof,
        "expected_native_hash_basis": "COMPLETED_IMPORT_RECEIPT_NATIVE_SAVE_SHA256",
        "current_file_hashes_only_compare_to_expected": True,
        "manufacturing_release": False, "all_assembly_bodies_remeasured": False,
    }
    with out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "path": str(out),
                      "sha256": v.sha(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
