"""B3-00 入口证据校验器（fail-closed）。

复核 B3 受控输入的四套哈希清单 + B601 资产现值哈希 + git 暂存区检查，
输出机器可读裁决到 evidence/b3_00/。只读校验，不修改任何被校验对象。

裁决键：
  V1_0_NATIVE_HASH   32 项原生组件（V1.0 冻结，任何 mismatch = 硬 fail）
  V1_0_EVIDENCE_SEAL 43 项评审视图封存
  B2_5_PACKET / B2_8_PDR_PACKET / A4_B2_PACKET  三套输入包清单
  B601_ASSET_HASHES  arm_b601_v1 全部文件现值（与 a3 验收链对照由上游完成）
  GIT_STAGING_CLEAN  暂存区必须为空（B3 未授权 Git 动作）
"""
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
V2 = REPO / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_0"
OUT_DIR = V2 / "evidence/b3_00"
V1 = REPO / "20_engineering/cad/Space_Embodied_Robot_CAD_V1_0"

MANIFESTS = [
    ("V1_0_NATIVE_HASH", V1 / "evidence/native_component_manifest.csv", V1, True),
    ("V1_0_EVIDENCE_SEAL", V1 / "evidence/evidence_seal_manifest.csv", V1 / "evidence", True),
    ("B2_5_PACKET", REPO / "20_engineering/design_inputs/v2_system_mechanical/input_packet_hash_manifest.csv", REPO, False),
    ("B2_8_PDR_PACKET", REPO / "20_engineering/design_review/V2_PDR_package/PDR_packet_hash_manifest.csv", REPO, False),
    ("A4_B2_PACKET", REPO / "10_research/space_embodied_robotics/comp_prot_03_a4_b2_v2_mechanical_architecture/v2_packet_hash_manifest.csv", REPO, False),
]
B601_DIR = REPO / "20_engineering/cad/spacecraft_layout/arm_b601_v1"

# accepted B601 期望哈希（a3 asset_import_manifest_v0_1.yaml 冻结值，R7 摄入核录）
B601_EXPECTED = {
    "arm_b601_v1.urdf": ("1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164", 11321),
    "meshes_b601_gripper/base_link.STL": ("22641c079014fe968702393f61e7f7f1a8f80c6c1df45a61e31545f6eaff3b65", 3898684),
    "meshes_b601_gripper/link1.STL": ("9db637a63d37bc2c6398ea5b8ba32fb54122c637d5d77dc134c8782839b654cd", 499084),
    "meshes_b601_gripper/link2.STL": ("def0d9d82343dccc1eff0d9d5572eca49b3c134db9807ca12302b99d153df65e", 5992184),
    "meshes_b601_gripper/link3.STL": ("ca14d73b5d63f352051f440f4cabc3989567f25ee9d19e7dd749f2d6f0d0561d", 4209984),
    "meshes_b601_gripper/link4.STL": ("061909364f20bb387f9ff82cb80e506af959142f9fbb4a39dc86fc8244ee768a", 2579684),
    "meshes_b601_gripper/link5.STL": ("3a32006227c1f9dbc70e77e07055c61e3f195f1054d4d2eb480262f0873bf001", 2119384),
    "meshes_b601_gripper/link6.STL": ("c586a7d0b8345d2cd32eab7dfd2e334aba56e83f582a6298d41bbf718f2ebef1", 1248184),
    "meshes_b601_gripper/gripper_link.STL": ("a826e164d420a6922e8ad5ee27813f39fa809f6e4fdf39b42fd8a59e7d12e847", 2676384),
    "meshes_b601_gripper/gripper_left.STL": ("c4e0de70f776b3573d975a6eaaa746cccbe57c2d5bb12501da8889979d3af268", 2119684),
    "meshes_b601_gripper/gripper_right.STL": ("615b119c0bb97a032badd5882144e4a2a50c905a3e071af1fa28b83bfe9b1b65", 2119684),
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(csv_path: Path, base: Path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rel = row["relative_path"].strip().strip('"')
            target = base / rel
            entry = {"relative_path": rel, "expected_sha256": row["sha256"],
                     "expected_bytes": int(row["bytes"])}
            if not target.exists():
                entry.update(status="MISSING", actual_sha256=None, actual_bytes=None)
            else:
                actual = sha256_of(target)
                entry.update(actual_sha256=actual, actual_bytes=target.stat().st_size,
                             status="MATCH" if actual == row["sha256"] else "MISMATCH")
            rows.append(entry)
    n_match = sum(r["status"] == "MATCH" for r in rows)
    return {"total": len(rows), "match": n_match,
            "verdict": "PASS" if n_match == len(rows) else "FAIL", "rows": rows}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"gate": "COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD",
              "step": "B3-00_entry_verification",
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "checks": {}, "fail_closed_triggers": []}

    for key, csv_path, base, hard_fail in MANIFESTS:
        res = verify_manifest(csv_path, base)
        report["checks"][key] = {k: res[k] for k in ("total", "match", "verdict")}
        report["checks"][key]["manifest"] = str(csv_path.relative_to(REPO))
        bad = [r for r in res["rows"] if r["status"] != "MATCH"]
        if bad:
            report["checks"][key]["mismatches"] = bad
            if hard_fail:
                report["fail_closed_triggers"].append(
                    f"{key}: {len(bad)} mismatch/missing (V1.0 冻结边界被破坏)")

    b601_rows = []
    for p in sorted(B601_DIR.rglob("*")):
        if p.is_file():
            b601_rows.append({"relative_path": str(p.relative_to(B601_DIR)).replace("\\", "/"),
                              "bytes": p.stat().st_size, "sha256": sha256_of(p)})
    actual = {r["relative_path"]: (r["sha256"], r["bytes"]) for r in b601_rows}
    b601_bad = []
    for rel, (sha, size) in B601_EXPECTED.items():
        a = actual.get(rel)
        if a is None or a[0] != sha or a[1] != size:
            b601_bad.append({"relative_path": rel, "actual": a})
    report["checks"]["B601_ASSET_HASHES"] = {
        "total": len(b601_rows), "compared": len(B601_EXPECTED),
        "verdict": "PASS" if not b601_bad else "FAIL",
        "expected_source": "a3 asset_import_manifest_v0_1.yaml",
        "rows": b601_rows}
    if b601_bad:
        report["checks"]["B601_ASSET_HASHES"]["mismatches"] = b601_bad
        report["fail_closed_triggers"].append(
            f"B601_ASSET_HASHES: {len(b601_bad)} mismatch (accepted B601 被改动)")
    report["b601_match_verdict"] = ("B601_HASH_AND_TOPOLOGY_MATCH" if not b601_bad
                                     else "B601_HASH_MISMATCH_FAIL_CLOSED")

    staged = subprocess.run(["git", "diff", "--cached", "--name-only"],
                            cwd=REPO, capture_output=True, text=True).stdout.strip()
    report["checks"]["GIT_STAGING_CLEAN"] = {
        "verdict": "PASS" if not staged else "FAIL",
        "staged_files": staged.splitlines()}
    if staged:
        report["fail_closed_triggers"].append("GIT_STAGING_CLEAN: 暂存区非空")

    hard = bool(report["fail_closed_triggers"])
    soft = [k for k, v in report["checks"].items()
            if v.get("verdict") == "FAIL" and k not in
            ("V1_0_NATIVE_HASH", "V1_0_EVIDENCE_SEAL", "GIT_STAGING_CLEAN")]
    report["verdict"] = ("B3_ENTRY_FAIL_CLOSED" if hard
                         else "B3_ENTRY_SOURCE_CONFLICT" if soft
                         else "B3_ENTRY_BASELINE_LOCKED")
    report["soft_conflicts"] = soft

    with open(OUT_DIR / "B3_entry_verification.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "B3_entry_baseline_manifest.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["check", "relative_path", "bytes", "sha256", "status"])
        for key, csv_path, base, _ in MANIFESTS:
            for r in verify_manifest(csv_path, base)["rows"]:
                w.writerow([key, r["relative_path"], r["expected_bytes"],
                            r["expected_sha256"], r["status"]])
        for r in b601_rows:
            w.writerow(["B601_ASSET", r["relative_path"], r["bytes"],
                        r["sha256"], "RECORDED"])

    print(json.dumps({"verdict": report["verdict"],
                      "checks": {k: v.get("verdict") for k, v in report["checks"].items()},
                      "fail_closed_triggers": report["fail_closed_triggers"],
                      "soft_conflicts": soft}, ensure_ascii=False, indent=2))
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
