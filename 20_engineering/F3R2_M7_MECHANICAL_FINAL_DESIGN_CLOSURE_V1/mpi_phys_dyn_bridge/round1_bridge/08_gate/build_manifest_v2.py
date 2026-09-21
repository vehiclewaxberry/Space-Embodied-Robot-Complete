# -*- coding: utf-8 -*-
"""MPI-FB-08: rebuild the package manifest as V2 (re-walk whole PKG tree).

Reads every file under mpi_phys_dyn_bridge/ (round0_handover + round1_bridge),
recomputes sha256/bytes, classifies role/wave, cross-checks every V1 entry, and
writes MPI_BRIDGE_PACKAGE_MANIFEST_V2.json. Self-reference excluded (V2 does not
list itself); V1 is listed as a landed artifact. Read-only on everything else.
"""
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
PKG = r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge"
OUT = os.path.join(ROOT, PKG, "round1_bridge", "08_gate", "MPI_BRIDGE_PACKAGE_MANIFEST_V2.json")
V1 = os.path.join(ROOT, PKG, "round1_bridge", "00_authority", "MPI_BRIDGE_PACKAGE_MANIFEST_V1.json")

ROLE_BY_DIR = {
    "round0_handover/00_receipt": ("handover_receipt_baseline_hash_chain", "wave_2a_round0"),
    "round0_handover/01_frame_authority": ("frame_authority_package (MPI-FB-01)", "wave_2a_round0"),
    "round0_handover/02_route_c_inputs": ("route_c_physical_input_inventory", "wave_2a_round0"),
    "round0_handover/03_r2_flex_inputs": ("r2_flex_input_inventory", "wave_2a_round0"),
    "round0_handover/04_red_team": ("red_team_attack_plan_round0", "wave_2a_round0"),
    "round1_bridge/00_authority": ("configuration_management_authority", "wave_2a_round1"),
    "round1_bridge/02_bridge": ("physical_dynamics_bridge (MPI-FB-02)", "wave_2a_round1"),
    "round1_bridge/03_validation": ("bridge_numerical_validation (MPI-FB-03)", "wave_2a_round1"),
    "round1_bridge/04_mass": ("mass_inertia_bridge_validation (MPI-FB-04)", "wave_2a_round1"),
    "round1_bridge/05_e21_bridged": ("e21_bridged_arm_placement_gate (MPI-FB-05)", "wave_2a_round1"),
    "round1_bridge/06_mass_propagation": ("system_mass_properties_bridged (MPI-FB-06)", "wave_2a_round1"),
    "round1_bridge/07_rebind": ("rebind_candidates (MPI-FB-07)", "wave_2a_round1"),
    "round1_bridge/decisions": ("engineering_ruling_dynamic_mass_allocation_mc_a (wave_2b DYN-AUTHORITY)", "wave_2b"),
    "round1_bridge/r2_flex_prep": ("r2_flex_preparation_drafts", "wave_2a_round1"),
    "round1_bridge/redteam_round1": ("red_team_round1", "wave_2a_round1"),
    "round1_bridge/redteam_round2": ("red_team_round2", "wave_2b"),
    "round1_bridge/route_c_prep": ("route_c_text_preparation", "wave_2a_round1"),
    "round1_bridge/08_gate": ("mpi_fb08_gate_assembly", "wave_2c_fb08_gate"),
}
WAVE2B_00_AUTHORITY = {"OPEN_ITEMS_UPDATE_V1.csv", "R2_FLEX_INPUT_INVENTORY_V1_FULLHASH_ADDENDUM_V1.json"}


def sha256_bytes(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


entries = []
for dirpath, _, files in os.walk(os.path.join(ROOT, PKG)):
    for fn in sorted(files):
        full = os.path.join(dirpath, fn)
        rel_pkg = os.path.relpath(full, os.path.join(ROOT, PKG)).replace("\\", "/")
        rel_root = PKG + "/" + rel_pkg
        if rel_root.endswith("08_gate/MPI_BRIDGE_PACKAGE_MANIFEST_V2.json"):
            continue  # self-reference excluded
        subdir = os.path.dirname(rel_pkg)
        role, wave = ROLE_BY_DIR.get(subdir, ("unclassified", "unknown"))
        if subdir == "round1_bridge/00_authority" and fn in WAVE2B_00_AUTHORITY:
            wave = "wave_2b"
        entries.append({
            "path": rel_root,
            "bytes": os.path.getsize(full),
            "sha256": sha256_bytes(full),
            "role": role,
            "produced_by_wave": wave,
        })
entries.sort(key=lambda e: e["path"])

v1 = json.load(open(V1, encoding="utf-8"))
v1_by_path = {e["path"]: e for e in v1["files"]}
cur_by_path = {e["path"]: e for e in entries}
cross = {"v1_entries": len(v1_by_path), "match": 0, "mismatch": [], "missing_now": [],
         "new_since_v1": sorted(set(cur_by_path) - set(v1_by_path))}
for p, e in v1_by_path.items():
    if p not in cur_by_path:
        cross["missing_now"].append(p)
    elif cur_by_path[p]["sha256"] == e["sha256"] and cur_by_path[p]["bytes"] == e["bytes"]:
        cross["match"] += 1
    else:
        cross["mismatch"].append({"path": p, "v1_sha256": e["sha256"], "v1_bytes": e["bytes"],
                                  "now_sha256": cur_by_path[p]["sha256"], "now_bytes": cur_by_path[p]["bytes"]})

# register the one documented re-run: rt2_static_output.json was re-run by the wave_2b
# red team after the V1 snapshot (same byte count; documented inside RED_TEAM_ROUND2_EXECUTION_V1.json
# reproduction_package and concurrent_wave2b_landings_observed)
documented = []
remaining = []
rt2_doc_sha = "a0d0c2693184b07d109a83670e522120124057f66baa133f288204c1afd454f6"
for m in cross["mismatch"]:
    if m["path"].endswith("redteam_round2/rt2_static_output.json") and m["now_sha256"] == rt2_doc_sha \
            and m["now_bytes"] == m["v1_bytes"] == 110644:
        documented.append({**m, "disposition": "DOCUMENTED_RE_RUN_BY_REDTEAM_ROUND2 (same byte count; hash matches the "
                                                "reproduction_package pin inside RED_TEAM_ROUND2_EXECUTION_V1.json); V1 pin superseded"})
    else:
        remaining.append(m)
cross["mismatch_documented"] = documented
cross["mismatch_undocumented"] = remaining

counts_by_wave = {}
for e in entries:
    counts_by_wave[e["produced_by_wave"]] = counts_by_wave.get(e["produced_by_wave"], 0) + 1

zero_mismatch = (not cross["missing_now"]) and (not remaining)
manifest = {
    "schema": "MPI_BRIDGE_PACKAGE_MANIFEST_V2",
    "generated_local": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
    "generator": "KIMI M7 MPI-FB-08 gate assembly agent (pure python hashlib walk; read-only on all listed files)",
    "purpose": "MPI-FB-08 Gate 输入清单刷新：复走 PKG 全目录树（round0_handover/ + round1_bridge/），逐文件 path/bytes/sha256/role/wave；含 redteam_round2 六件、decisions 两件、00_authority 全部、round0 全部、08_gate 验证产物",
    "supersedes": "round1_bridge/00_authority/MPI_BRIDGE_PACKAGE_MANIFEST_V1.json (V1 remains on disk byte-untouched; V2 is the current registration)",
    "self_hash_policy": "SELF_REFERENCE_EXCLUDED - this manifest does not list itself (same convention as V1 / e21 / V5 manifests and 02_bridge self_hash_policy); downstream consumers pin its sha256 after emission",
    "method": "pure python hashlib.sha256 over raw file bytes; sha256 stored as canonical lowercase 64-hex (compare case-insensitively against UPPERCASE conventions in receipt/bridge pins)",
    "scope_roots": [
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round0_handover/",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/",
    ],
    "file_count": len(entries),
    "counts_by_wave": counts_by_wave,
    "v1_crosscheck": cross,
    "zero_undocumented_mismatch": zero_mismatch,
    "expected_post_snapshot_landings": [
        {"path": PKG + "/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json",
         "note": "gate verdict JSON, emitted after this manifest snapshot; to be registered by the next CM re-walk"},
        {"path": PKG + "/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.md",
         "note": "gate human-readable companion, same registration rule"},
    ],
    "files": entries,
    "nonclaims": [
        "本清单不授予任何 release credit；Mechanical Loop V5 Gate 维持 HOLD",
        "本清单不修改任何被列文件；07_rebind 两件保持 _CANDIDATE 命名、base 字节不动",
        "列入清单 ≠ 内容背书；各产物权威语义以其自身 schema 与红队/CM 裁决为准",
        "本清单为 generated_local 时刻快照；此后新增文件（08_gate 两件 gate 文本）须经复走目录树补登",
    ],
    "next_stage_authorized": False,
    "release_credit": False,
}
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
print(json.dumps({"file_count": len(entries), "counts_by_wave": counts_by_wave,
                  "v1_match": cross["match"], "v1_entries": cross["v1_entries"],
                  "missing_now": cross["missing_now"],
                  "mismatch_documented": len(documented),
                  "mismatch_undocumented": len(remaining),
                  "new_since_v1": cross["new_since_v1"],
                  "zero_undocumented_mismatch": zero_mismatch}, indent=2, ensure_ascii=False))
