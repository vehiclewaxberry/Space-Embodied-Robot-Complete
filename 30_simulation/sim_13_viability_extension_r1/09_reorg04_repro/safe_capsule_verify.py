"""safe_capsule_verify.py —— 受保护结果目录的非破坏性验证夹具。

背景：control_01 / control_02 的 run_all.py 会直接写入 `results/`；一次失败运行
曾把 Gate JSON 截断。因此禁止再在活动工作树中直接运行这些 runner。

本夹具保证：
  1. 运行前对**活动工作树**全部受保护 results/Gate 文件取 SHA-256；
  2. capsule 只在隔离 worktree（或其临时副本）中运行；
  3. 运行前先把隔离 worktree 的 results/ 冻结快照留存，供候选对比；
  4. 采集 stdout / stderr / 返回码 / 候选结果；
  5. 候选结果与冻结结果逐文件对比；
  6. 运行后重新对活动工作树受保护文件取哈希；
  7. 活动工作树任何受保护文件变化 -> 整体 FAIL（fail-closed）；
  8. 绝不把候选输出自动复制回权威目录。

用法：
    python safe_capsule_verify.py            # 运行全部已登记 capsule
    python safe_capsule_verify.py sim_05     # 只运行一个
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ACTIVE_REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
ISOLATED = r"F:\_SEI_RESEARCH_WORKTREES\reorg04_current_tree_repro_r1"

# 受保护范围：活动工作树中任何 30_simulation/*/results/ 下的文件
PROTECTED_GLOB_ROOT = os.path.join(ACTIVE_REPO, "30_simulation")

CAPSULES = {
    "sim_05": {"module": "30_simulation/sim_05_free_floating_arm",
               "cmd": [sys.executable, "-B", "tests/run_all.py"],
               "expected_tests": 22},
    "sim_11": {"module": "30_simulation/sim_11_coupled_dynamics",
               "cmd": [sys.executable, "-B", "tests/run_all.py"],
               "expected_tests": 27},
    "ctrl_01": {"module": "30_simulation/control_01_end_effector_tracking",
                "cmd": [sys.executable, "-B", "tests/run_all.py"],
                "expected_tests": 22},
    "ctrl_02": {"module": "30_simulation/control_02_base_attitude",
                "cmd": [sys.executable, "-B", "tests/run_all.py"],
                "expected_tests": 24},
}
TIMEOUT_S = 1800


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def snapshot_protected(root):
    """所有 30_simulation/*/results/** 文件的 path -> sha256。"""
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", ".pytest_cache")
                       and not d.startswith(".pytest-tmp")]
        if os.path.basename(dirpath) != "results":
            continue
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                snap[os.path.relpath(fp, root).replace("\\", "/")] = sha(fp)
            except (PermissionError, OSError):
                pass
    return snap


def run_capsule(name, spec, out_dir):
    mod_abs = os.path.join(ISOLATED, spec["module"].replace("/", os.sep))
    res_dir = os.path.join(mod_abs, "results")

    # --- 3. 隔离树内 results/ 冻结快照（候选对比基线）----------------------
    frozen_dir = os.path.join(out_dir, f"{name}__frozen_results")
    if os.path.isdir(res_dir):
        shutil.copytree(res_dir, frozen_dir, dirs_exist_ok=True)
    frozen = {f: sha(os.path.join(frozen_dir, f))
              for f in os.listdir(frozen_dir)} if os.path.isdir(frozen_dir) else {}

    # --- 4. 只在隔离树中运行 ----------------------------------------------
    t0 = time.time()
    try:
        proc = subprocess.run(spec["cmd"], cwd=mod_abs, capture_output=True,
                              timeout=TIMEOUT_S, text=True, errors="replace")
        rc, so, se, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        rc, so, se, timed_out = None, (e.stdout or ""), (e.stderr or ""), True
    dt = time.time() - t0

    with open(os.path.join(out_dir, f"{name}__stdout.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(so or "")
    with open(os.path.join(out_dir, f"{name}__stderr.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(se or "")

    # --- 5. 候选 vs 冻结 ---------------------------------------------------
    cand = {f: sha(os.path.join(res_dir, f)) for f in os.listdir(res_dir)} \
        if os.path.isdir(res_dir) else {}
    changed = sorted(f for f in set(frozen) & set(cand) if frozen[f] != cand[f])
    added = sorted(set(cand) - set(frozen))
    removed = sorted(set(frozen) - set(cand))

    # 解析测试计数
    passed = total = None
    for line in (so or "").splitlines():
        if line.strip().startswith("TOTAL:"):
            try:
                frac = line.split("TOTAL:")[1].split("PASS")[0].strip()
                passed, total = (int(x) for x in frac.split("/"))
            except Exception:
                pass
    return {
        "capsule": name, "module": spec["module"],
        "return_code": rc, "timed_out": timed_out, "elapsed_s": round(dt, 2),
        "tests_passed": passed, "tests_total": total,
        "expected_tests": spec["expected_tests"],
        "matches_expected_count": (passed is not None and total is not None
                                   and passed == total == spec["expected_tests"]),
        "isolated_results_changed_by_run": changed,
        "isolated_results_added_by_run": added,
        "isolated_results_removed_by_run": removed,
        "n_isolated_results_mutated": len(changed) + len(added) + len(removed),
        "stdout_path": f"{name}__stdout.txt", "stderr_path": f"{name}__stderr.txt",
        "candidate_outputs_copied_to_authority": False,
    }


def main(selected=None):
    out_dir = os.path.join(HERE, "verification_run")
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isdir(ISOLATED):
        raise RuntimeError(f"isolated worktree missing: {ISOLATED}")

    # --- 1. 运行前：活动工作树受保护快照 -----------------------------------
    pre = snapshot_protected(PROTECTED_GLOB_ROOT)
    results = []
    for name, spec in CAPSULES.items():
        if selected and name not in selected:
            continue
        print(f"[run] {name} ... ", end="", flush=True)
        r = run_capsule(name, spec, out_dir)
        print(f"rc={r['return_code']} tests={r['tests_passed']}/{r['tests_total']} "
              f"({r['elapsed_s']}s) isolated_results_mutated={r['n_isolated_results_mutated']}")
        results.append(r)

    # --- 6/7. 运行后：活动工作树受保护复核 ---------------------------------
    post = snapshot_protected(PROTECTED_GLOB_ROOT)
    active_changed = sorted(f for f in set(pre) & set(post) if pre[f] != post[f])
    active_added = sorted(set(post) - set(pre))
    active_removed = sorted(set(pre) - set(post))
    active_intact = not (active_changed or active_added or active_removed)

    gate = {
        "schema": "SAFE_CAPSULE_VERIFY_RECEIPT_V1",
        "generated_date_local": "2026-08-30",
        "review_status": "PENDING_OWNER_REVIEW",
        "active_worktree": ACTIVE_REPO,
        "isolated_worktree": ISOLATED,
        "protected_file_count": len(pre),
        "active_tree_protected_files_changed": active_changed,
        "active_tree_protected_files_added": active_added,
        "active_tree_protected_files_removed": active_removed,
        "active_tree_intact": bool(active_intact),
        "candidate_outputs_copied_to_authority": False,
        "capsules": results,
        "harness_verdict": ("SAFE_CAPSULE_VERIFY_PASS__ACTIVE_TREE_INTACT"
                            if active_intact else
                            "SAFE_CAPSULE_VERIFY_FAIL__ACTIVE_TREE_MUTATED"),
        "note": ("Test counts are software reproducibility only. They never change a "
                 "scientific verdict: CTRL-01 remains REPEAT, CTRL-02 remains "
                 "PASS_WITH_PROVISIONAL_SCOPE."),
    }
    p = os.path.join(HERE, "SAFE_CAPSULE_VERIFY_RECEIPT_V1.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(gate, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: gate[k] for k in
                      ("active_tree_intact", "protected_file_count", "harness_verdict")},
                     indent=1))
    return 0 if active_intact else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
