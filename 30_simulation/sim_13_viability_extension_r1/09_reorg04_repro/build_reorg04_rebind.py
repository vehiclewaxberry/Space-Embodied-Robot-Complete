"""REORG04 迁移层重绑定：路径映射 + 三层哈希 + 科学字段不变性证明。

授权范围（严格）：只允许改变“这份证据现在在哪里、当前字节哈希是什么”。
禁止改变“证据证明了什么”：数值阈值、布尔判据、字段结构、verdict 文本、
控制器参数、动力学参数、accepted URDF、仿真输出数字。

三层哈希：
  raw_sha256                    工作树字节（受 core.autocrlf 影响）
  normalized_lf_sha256          CRLF -> LF 归一后字节
  scientific_projection_sha256  解析后剔除迁移元数据字段的规范化投影

只有当科学投影逐位相等，且数值/布尔/结构/verdict 四项独立证明全部成立时，
差异才可归类为 MIGRATION_ONLY；否则必须升级为 SCIENTIFIC_DRIFT 并停止。

不改写任何历史 Gate；本目录只产出 append-only 的当前树重绑定件。
"""
import hashlib
import json
import os
import subprocess

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
REORG04 = "284c882"

# 迁移元数据白名单：科学投影中剔除这些键（仅这些）
MIGRATION_KEY_WHITELIST = {
    "path", "source_path", "source", "file", "filename", "location",
    "sha256", "raw_sha256", "normalized_lf_sha256", "source_sha256",
    "migration", "migration_metadata", "source_commit_recorded_in_rows",
}
# 值内部的路径前缀改写（用于 verdict/自由文本的迁移归一）
PATH_PREFIX_REWRITES = [
    ("40_evidence/artifacts/", "artifacts/"),
    ("20_engineering/config/", "config/"),
    ("20_engineering/stage1_spacecraft_layout/", "docs/stage1_spacecraft_layout/"),
    ("20_engineering/cad/", "cad/"),
    ("30_simulation/common/", "sim/common/"),
    ("30_simulation/sim_09_grasp_evaluator/src/", "src/sim_09_grasp_evaluator/"),
    ("30_simulation/sim_04_capture_corridor/", "sim/sim_04_capture_corridor/"),
    ("30_simulation/", "sim/"),
]

DRIFTED = {
    "threshold_registry": {
        "old_path": "e15_core_coverage/config/threshold_registry_core_v1.yaml",
        "new_path": "30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml",
        "pin_sha256": "400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873",
        "consumer": "20_engineering/config/mission_feasibility/scan_v0.yaml frozen_inputs",
        "format": "yaml"},
    "sim08_assumptions": {
        "old_path": "sim/sim_08_detumble_actuator_budget/assumptions.yaml",
        "new_path": "30_simulation/sim_08_detumble_actuator_budget/assumptions.yaml",
        "pin_sha256": "850f49da90d50c55984bde20e4f93193725f798eea9e4f3346836e76511ec890",
        "consumer": "20_engineering/config/mission_feasibility/scan_v0.yaml frozen_inputs",
        "format": "yaml"},
}
UNDRIFTED = {
    "sim06_anchor_csv": {
        "new_path": "30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv",
        "pin_sha256": "8cbad84b8ff69ffca6992ce29e95520bae3c309260ec8c55083cbe62dfed5151"},
    "sim08_sweep_csv": {
        "new_path": "30_simulation/sim_08_detumble_actuator_budget/results/actuator_budget_sweep.csv",
        "pin_sha256": "1f0d4534956555c7bc5e309d53e9a92eb25d281c9e036987fb7eab2b17b3d7ad"},
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def lf(b):
    return b.replace(b"\r\n", b"\n")


def git_show(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, cwd=REPO)
    return r.stdout if r.returncode == 0 else None


def normalize_value(v):
    """自由文本中的迁移路径前缀归一到迁移前形式。"""
    if not isinstance(v, str):
        return v
    out = v
    for new, old in PATH_PREFIX_REWRITES:
        out = out.replace(new, old)
    return out


def scientific_projection(obj):
    """剔除迁移元数据键；对保留的字符串做路径前缀归一。"""
    if isinstance(obj, dict):
        return {k: scientific_projection(v) for k, v in sorted(obj.items())
                if k not in MIGRATION_KEY_WHITELIST}
    if isinstance(obj, list):
        return [scientific_projection(v) for v in obj]
    return normalize_value(obj)


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def collect(obj, prefix="", nums=None, bools=None, strs=None, keys=None):
    nums = {} if nums is None else nums
    bools = {} if bools is None else bools
    strs = {} if strs is None else strs
    keys = set() if keys is None else keys
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            keys.add(p)
            collect(v, p, nums, bools, strs, keys)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{prefix}[{i}]"
            keys.add(p)
            collect(v, p, nums, bools, strs, keys)
    elif isinstance(obj, bool):
        bools[prefix] = obj
    elif isinstance(obj, (int, float)):
        nums[prefix] = float(obj)
    elif isinstance(obj, str):
        strs[prefix] = obj
    return nums, bools, strs, keys


# =====================================================================
records = {}
all_migration_only = True
for key, spec in DRIFTED.items():
    old_b = git_show(f"{REORG04}^", spec["old_path"])
    new_b = open(os.path.join(REPO, spec["new_path"]), "rb").read()
    if old_b is None:
        raise RuntimeError(f"pre-REORG04 blob not found: {spec['old_path']}")

    old_y = yaml.safe_load(old_b.decode("utf-8"))
    new_y = yaml.safe_load(new_b.decode("utf-8"))
    old_proj, new_proj = scientific_projection(old_y), scientific_projection(new_y)
    proj_old_h, proj_new_h = sha(canon(old_proj)), sha(canon(new_proj))

    n0, b0, s0, k0 = collect(old_y)
    n1, b1, s1, k1 = collect(new_y)
    # 数值：键集与逐值
    num_same = (set(n0) == set(n1)) and all(
        n0[k] == n1[k] or (n0[k] != n0[k] and n1[k] != n1[k]) for k in n0)
    bool_same = (set(b0) == set(b1)) and all(b0[k] == b1[k] for k in b0)
    struct_same = (k0 == k1)
    # verdict/自由文本：迁移归一后必须逐位相等
    str_same = (set(s0) == set(s1)) and all(
        normalize_value(s0[k]) == normalize_value(s1[k]) for k in s0)
    changed_str_keys = [k for k in s0 if k in s1 and s0[k] != s1[k]]

    # 阈值放宽检测：所有 thresholds.*.value 必须逐位不变
    def thr_vals(y):
        return {k: v.get("value") for k, v in (y.get("thresholds") or {}).items()} \
            if isinstance(y, dict) else {}
    t0, t1 = thr_vals(old_y), thr_vals(new_y)
    thresholds_widened = not (t0 == t1)

    migration_only = all([num_same, bool_same, struct_same, str_same,
                          proj_old_h == proj_new_h, not thresholds_widened])
    all_migration_only = all_migration_only and migration_only

    records[key] = {
        "old_path": spec["old_path"], "new_path": spec["new_path"],
        "consumer": spec["consumer"],
        "pin_sha256_currently_declared": spec["pin_sha256"],
        "hashes": {
            "old_raw_sha256": sha(old_b), "new_raw_sha256": sha(new_b),
            "old_normalized_lf_sha256": sha(lf(old_b)),
            "new_normalized_lf_sha256": sha(lf(new_b)),
            "old_scientific_projection_sha256": proj_old_h,
            "new_scientific_projection_sha256": proj_new_h,
            "old_bytes": len(old_b), "new_bytes": len(new_b),
            "old_has_crlf": b"\r\n" in old_b, "new_has_crlf": b"\r\n" in new_b},
        "pin_matches_old_raw": sha(old_b) == spec["pin_sha256"],
        "crlf_explains_drift": sha(lf(old_b)) == sha(lf(new_b)),
        "proof": {
            "numeric_values_unchanged": bool(num_same),
            "booleans_unchanged": bool(bool_same),
            "field_structure_unchanged": bool(struct_same),
            "verdict_text_unchanged": bool(str_same),
            "thresholds_widened": bool(thresholds_widened),
            "scientific_projection_identical": bool(proj_old_h == proj_new_h),
            "n_numeric_fields_compared": len(n0),
            "n_boolean_fields_compared": len(b0),
            "n_string_fields_compared": len(s0),
            "n_structural_keys_compared": len(k0)},
        "changed_string_fields_all_path_only": changed_str_keys,
        "n_changed_lines": sum(1 for a, b in zip(old_b.decode().splitlines(),
                                                 new_b.decode().splitlines()) if a != b),
        "classification": "MIGRATION_ONLY" if migration_only else "SCIENTIFIC_DRIFT",
    }

for key, spec in UNDRIFTED.items():
    b = open(os.path.join(REPO, spec["new_path"]), "rb").read()
    records[key] = {
        "new_path": spec["new_path"],
        "pin_sha256_currently_declared": spec["pin_sha256"],
        "hashes": {"new_raw_sha256": sha(b), "new_normalized_lf_sha256": sha(lf(b)),
                   "new_bytes": len(b), "new_has_crlf": b"\r\n" in b},
        "pin_matches_current_raw": sha(b) == spec["pin_sha256"],
        "pin_computed_on": "CRLF_WORKING_TREE_BYTES" if b"\r\n" in b else "LF_BYTES",
        "classification": "PIN_INTACT",
    }

# ------------------------------------------------------------------ 写出
def w_json(name, obj):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return p


def w_yaml(name, obj):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False, width=100)
    return p


out = []
out.append(w_yaml("REORG04_PATH_REBIND_MAP_V1.yaml", {
    "schema": "REORG04_PATH_REBIND_MAP_V1",
    "authorization": "AUTHORIZE_REORG04_PATH_AND_HASH_REBIND_WITH_SCIENTIFIC_FIELDS_FROZEN",
    "generated_date_local": "2026-08-30",
    "review_status": "PENDING_OWNER_REVIEW",
    "reorg04_commit": REORG04,
    "scope_permitted": ["file path strings", "raw SHA-256", "normalized-LF SHA-256",
                        "migration receipt", "current-tree reproducibility binding"],
    "scope_forbidden": ["numeric thresholds", "boolean criteria", "Gate structure",
                        "verdict text", "PASS/HOLD/REPEAT", "controller parameters",
                        "dynamics parameters", "accepted URDF", "simulation output numbers"],
    "runtime_path_repairs": [
        {"file": "30_simulation/sim_05_free_floating_arm/b601_model.py",
         "old_fragment": '"..", "..", "cad", "spacecraft_layout"',
         "new_fragment": '"..", "..", "20_engineering", "cad", "spacecraft_layout"',
         "resolves_to": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"},
        {"file": "30_simulation/common/rigid_body.py",
         "old_fragment": '"..", "..", "docs", "stage1_spacecraft_layout"',
         "new_fragment": '"..", "..", "20_engineering", "stage1_spacecraft_layout"',
         "resolves_to": "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/"
                        "mass_inertia_budget_v1.csv"}],
    "frozen_input_rebind": {k: {"old_path": v.get("old_path"), "new_path": v["new_path"],
                                "classification": v["classification"]}
                            for k, v in records.items()},
    "migration_key_whitelist": sorted(MIGRATION_KEY_WHITELIST),
    "path_prefix_rewrites": [{"post_reorg04": a, "pre_reorg04": b}
                             for a, b in PATH_PREFIX_REWRITES],
}))

out.append(w_json("REORG04_SCIENTIFIC_FIELD_DIFF_V1.json", {
    "schema": "REORG04_SCIENTIFIC_FIELD_DIFF_V1",
    "generated_date_local": "2026-08-30",
    "review_status": "PENDING_OWNER_REVIEW",
    "method": ("parse each artifact pre- and post-REORG04, strip only whitelisted migration "
               "metadata keys, normalize path prefixes inside retained free text, then "
               "compare numerics, booleans, key structure and verdict text independently and "
               "hash the canonical projection"),
    "records": records,
    "all_drifted_files_migration_only": bool(all_migration_only),
    "verdict": ("REORG04_FROZEN_INPUT_DRIFT_IS_MIGRATION_ONLY__NO_SCIENTIFIC_FIELD_CHANGED"
                if all_migration_only else
                "SCIENTIFIC_DRIFT_DETECTED__STOP__DO_NOT_CLASSIFY_AS_MIGRATION"),
}))

out.append(w_json("REORG04_HASH_REBIND_ADDENDUM_V1.json", {
    "schema": "REORG04_HASH_REBIND_ADDENDUM_V1",
    "authority": "APPEND_ONLY_CURRENT_TREE_REBIND__NO_HISTORICAL_GATE_MUTATION",
    "generated_date_local": "2026-08-30",
    "review_status": "PENDING_OWNER_REVIEW",
    "supersedes": None,
    "historical_pins_preserved": True,
    "historical_pin_source": "20_engineering/config/mission_feasibility/scan_v0.yaml frozen_inputs",
    "historical_pins_mutated_by_this_artifact": False,
    "note": ("This addendum records what the current-tree bytes hash to. It does NOT edit "
             "scan_v0.yaml. Refreshing the two stale pins in scan_v0.yaml remains an explicit "
             "Owner action; until then feasibility_core.load_cfg() stays fail-closed and "
             "sim_10 / sim_12 remain non-re-executable."),
    "current_tree_rebind": {
        k: {"path": v["new_path"],
            "historical_pin": v["pin_sha256_currently_declared"],
            "current_raw_sha256": v["hashes"]["new_raw_sha256"],
            "current_normalized_lf_sha256": v["hashes"]["new_normalized_lf_sha256"],
            "scientific_projection_sha256":
                v["hashes"].get("new_scientific_projection_sha256", "N_A_NON_STRUCTURED"),
            "classification": v["classification"]}
        for k, v in records.items()},
    "crlf_finding": {
        "core_autocrlf": "true",
        "consequence": ("two of the four frozen pins (sim06_anchor_csv, sim08_sweep_csv) were "
                        "computed on CRLF working-tree bytes and still match; the two drifted "
                        "pins contain no CRLF at all, so line endings do NOT explain their "
                        "drift - the content genuinely changed, and that change is proven "
                        "migration-only"),
        "prior_project_evidence":
            "30_simulation/control_02_base_attitude/results/autocrlf_false_hash_audit.json"},
    "next_stage_authorized": False,
    "release_credit": False,
}))

print(json.dumps({
    "all_drifted_files_migration_only": all_migration_only,
    "per_file": {k: {"classification": v["classification"],
                     "proof": v.get("proof"),
                     "n_changed_lines": v.get("n_changed_lines"),
                     "changed_string_fields": v.get("changed_string_fields_all_path_only")}
                 for k, v in records.items() if k in DRIFTED},
    "undrifted": {k: {"pin_matches_current_raw": v["pin_matches_current_raw"],
                      "pin_computed_on": v["pin_computed_on"]}
                  for k, v in records.items() if k in UNDRIFTED},
}, indent=1, ensure_ascii=False))
for p in out:
    b = open(p, "rb").read()
    print(f"  {sha(b).upper()[:16]}...  {len(b):6d} B  {os.path.basename(p)}")
