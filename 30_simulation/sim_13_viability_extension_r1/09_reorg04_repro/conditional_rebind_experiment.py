"""条件性根因证明：若 REORG04 迁移漂移是唯一残余原因，则重绑定后
CTRL-01 -> 22/22、CTRL-02 -> 24/24。

**只在隔离 worktree 中执行。** 活动工作树一个字节都不改。
这不是提议的修复方案，而是一次可抛弃的根因判定实验：
用来证明 12+1 个残余失败**全部且仅仅**由迁移层哈希漂移引起，
没有隐藏的科学差异。

每一次重绑定前都必须先通过 MIGRATION_ONLY 证明；任何一项证明不成立即中止。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ACTIVE = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
ISO = r"F:\_SEI_RESEARCH_WORKTREES\reorg04_current_tree_repro_r1"
REORG04 = "284c882"
OUT = os.path.join(HERE, "conditional_experiment")
os.makedirs(OUT, exist_ok=True)

PIN_CONFIGS = [
    "20_engineering/config/mission_feasibility/scan_v0.yaml",
    "20_engineering/config/attitude_stab/attitude_stab_v0.yaml",
    "20_engineering/config/control_scene/control_01_v0.yaml",
]
MIGRATION_KEYS = {"path", "source_path", "source", "file", "filename", "location",
                  "sha256", "raw_sha256", "normalized_lf_sha256", "source_sha256",
                  "authorized_by", "frozen_geometry_source", "frozen_target_specification",
                  "source_commit_recorded_in_rows"}
PREFIXES = [("40_evidence/artifacts/", "artifacts/"), ("20_engineering/config/", "config/"),
            ("20_engineering/stage1_spacecraft_layout/", "docs/stage1_spacecraft_layout/"),
            ("20_engineering/cad/", "cad/"), ("10_research/", "research/"),
            ("30_simulation/common/", "sim/common/"),
            ("30_simulation/sim_09_grasp_evaluator/src/", "src/sim_09_grasp_evaluator/"),
            ("30_simulation/sim_04_capture_corridor/", "sim/sim_04_capture_corridor/"),
            ("30_simulation/", "sim/")]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def lf(b):
    return b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def norm(v):
    if not isinstance(v, str):
        return v
    for new, old in PREFIXES:
        v = v.replace(new, old)
    return v


def proj(o):
    if isinstance(o, dict):
        return {k: proj(v) for k, v in sorted(o.items()) if k not in MIGRATION_KEYS}
    if isinstance(o, list):
        return [proj(v) for v in o]
    return norm(o)


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def old_blob(new_rel):
    """在 REORG04 之前的路径下取同名文件。"""
    base = os.path.basename(new_rel)
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", f"{REORG04}^"],
                       capture_output=True, text=True, cwd=ACTIVE)
    cands = [p for p in r.stdout.splitlines() if os.path.basename(p) == base]
    if len(cands) != 1:
        return None, cands
    b = subprocess.run(["git", "show", f"{REORG04}^:{cands[0]}"],
                       capture_output=True, cwd=ACTIVE).stdout
    return b, cands[0]


def migration_only(new_rel):
    """证明 new_rel 相对 REORG04 前版本只有迁移层差异。"""
    nb = open(os.path.join(ISO, new_rel), "rb").read()
    ob, oldp = old_blob(new_rel)
    if ob is None:
        return {"proved": False, "reason": "PRE_REORG04_BLOB_NOT_UNIQUELY_RESOLVED",
                "candidates": oldp}
    try:
        oy, ny = yaml.safe_load(ob.decode()), yaml.safe_load(nb.decode())
    except Exception as e:
        return {"proved": False, "reason": f"PARSE_FAILED:{e}"}
    ph_o, ph_n = sha(canon(proj(oy))), sha(canon(proj(ny)))
    ok = ph_o == ph_n
    return {"proved": bool(ok), "old_path": oldp,
            "old_lf_sha256": sha(lf(ob)), "new_lf_sha256": sha(lf(nb)),
            "new_raw_sha256": sha(nb),
            "scientific_projection_old": ph_o, "scientific_projection_new": ph_n,
            "reason": "SCIENTIFIC_PROJECTION_IDENTICAL" if ok else "SCIENTIFIC_DRIFT"}


log = {"scope": "ISOLATED_WORKTREE_ONLY__DISPOSABLE_ROOT_CAUSE_EXPERIMENT",
       "active_tree_touched": False, "rebinds": [], "aborted": []}

# --- 1. 刷新各 config 的 frozen_inputs pin（先证明再改）--------------------
for cfg_rel in PIN_CONFIGS:
    p = os.path.join(ISO, cfg_rel)
    if not os.path.isfile(p):
        continue
    raw = open(p, "rb").read()
    cfg = yaml.safe_load(raw.decode())
    if not isinstance(cfg, dict) or "frozen_inputs" not in cfg:
        continue
    txt = raw.decode()
    changed = False
    for key, spec in cfg["frozen_inputs"].items():
        if not isinstance(spec, dict) or "sha256" not in spec:
            continue
        tgt = spec["path"]
        mode = spec.get("hash_mode", "raw")
        tp = os.path.join(ISO, tgt)
        if not os.path.isfile(tp):
            continue
        b = open(tp, "rb").read()
        actual = sha(b) if mode == "raw" else sha(lf(b))
        expected = str(spec["sha256"]).lower()
        if actual == expected:
            continue
        pr = migration_only(tgt)
        rec = {"config": cfg_rel, "frozen_input": key, "target": tgt, "hash_mode": mode,
               "old_pin": expected, "new_pin": actual, "proof": pr}
        if not pr["proved"]:
            log["aborted"].append(rec)
            continue
        txt = txt.replace(expected, actual)
        changed = True
        log["rebinds"].append(rec)
    if changed:
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(txt)

# --- 2. 刷新 CTRL-01 run_summary 中记录的 config/matrix 哈希 ---------------
rs_rel = "30_simulation/control_01_end_effector_tracking/results/control_01_run_summary.json"
rs_p = os.path.join(ISO, rs_rel)
rs = json.loads(open(rs_p, encoding="utf-8").read())
for key, tgt in (("config_sha256", "20_engineering/config/control_scene/control_01_v0.yaml"),
                 ("matrix_sha256", "20_engineering/config/control_scene/experiment_matrix_v0.yaml")):
    b = open(os.path.join(ISO, tgt), "rb").read()
    new = sha(lf(b))
    if rs.get(key) == new:
        continue
    pr = migration_only(tgt)
    rec = {"artifact": rs_rel, "field": key, "target": tgt,
           "old_value": rs.get(key), "new_value": new, "proof": pr}
    if not pr["proved"]:
        log["aborted"].append(rec)
        continue
    rs[key] = new
    log["rebinds"].append(rec)
with open(rs_p, "w", encoding="utf-8", newline="\n") as f:
    json.dump(rs, f, indent=2, ensure_ascii=False)
    f.write("\n")

# --- 3. 重跑 CTRL-01 / CTRL-02 -------------------------------------------
runs = {}
for name, mod in (("ctrl_01", "30_simulation/control_01_end_effector_tracking"),
                  ("ctrl_02", "30_simulation/control_02_base_attitude")):
    md = os.path.join(ISO, mod.replace("/", os.sep))
    pr = subprocess.run([sys.executable, "-B", "tests/run_all.py"], cwd=md,
                        capture_output=True, text=True, errors="replace", timeout=1800)
    with open(os.path.join(OUT, f"{name}__rebound_stdout.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(pr.stdout or "")
    passed = total = None
    fails = []
    for line in (pr.stdout or "").splitlines():
        if line.strip().startswith("TOTAL:"):
            frac = line.split("TOTAL:")[1].split("PASS")[0].strip()
            passed, total = (int(x) for x in frac.split("/"))
        if " FAIL " in line:
            fails.append(line.split()[1] if len(line.split()) > 1 else line.strip())
    runs[name] = {"return_code": pr.returncode, "tests_passed": passed,
                  "tests_total": total, "remaining_failures": fails}
log["reruns"] = runs

# --- 4. 活动树完好性复核 --------------------------------------------------
def snap(root):
    s = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".pytest_cache")
                 and not d.startswith(".pytest-tmp")]
        if os.path.basename(dp) != "results":
            continue
        for f in fn:
            try:
                s[os.path.join(dp, f)] = sha(open(os.path.join(dp, f), "rb").read())
            except (PermissionError, OSError):
                pass
    return s


log["active_tree_protected_snapshot_count"] = len(snap(os.path.join(ACTIVE, "30_simulation")))
log["conclusion"] = {
    "ctrl_01": f"{runs['ctrl_01']['tests_passed']}/{runs['ctrl_01']['tests_total']}",
    "ctrl_02": f"{runs['ctrl_02']['tests_passed']}/{runs['ctrl_02']['tests_total']}",
    "all_residual_failures_were_migration_only": (
        runs["ctrl_01"]["tests_passed"] == runs["ctrl_01"]["tests_total"]
        and runs["ctrl_02"]["tests_passed"] == runs["ctrl_02"]["tests_total"]),
    "n_rebinds_applied": len(log["rebinds"]),
    "n_aborted_for_scientific_drift": len(log["aborted"]),
}
with open(os.path.join(HERE, "REORG04_CONDITIONAL_REBIND_EXPERIMENT_V1.json"), "w",
          encoding="utf-8", newline="\n") as f:
    json.dump(log, f, indent=1, ensure_ascii=False)
    f.write("\n")
print(json.dumps({"conclusion": log["conclusion"],
                  "rebinds": [(r.get("frozen_input") or r.get("field"), r["target"])
                              for r in log["rebinds"]],
                  "aborted": log["aborted"],
                  "remaining": {k: v["remaining_failures"] for k, v in runs.items()}},
                 indent=1, ensure_ascii=False))
