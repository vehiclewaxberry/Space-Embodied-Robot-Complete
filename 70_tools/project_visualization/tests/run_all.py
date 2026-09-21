"""VIZ-Gate 0 acceptance suite runner (no pytest).

Runs the five acceptance tests in-process, prints a PASS/FAIL table and
writes 70_tools/project_visualization/tests/viz_gate0_test_report.md. Exit code 0 only when
all five pass.
"""
import os
import sys
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "70_tools", "project_visualization", "src"))
sys.path.insert(0, _HERE)
import _viz_bootstrap as vb  # noqa: E402  (pins OMP/MKL=1 BEFORE numpy)

REPORT_MD = os.path.join(_HERE, "viz_gate0_test_report.md")

TESTS = (
    "test_asset_units",
    "test_scene_transforms",
    "test_fk_render_alignment",
    "test_replay_numeric_consistency",
    "test_status_semantics",
    "test_dashboard_contract",
)


def run():
    results = []
    for name in TESTS:
        t0 = time.time()
        try:
            mod = __import__(name)
            out = mod.main(verbose=False)
            ok, details, err = bool(out.get("pass")), out.get("details", []), ""
        except Exception:
            ok, details = False, []
            err = traceback.format_exc(limit=4)
        results.append({"name": name, "pass": ok, "wall_s": time.time() - t0,
                        "details": details, "error": err})

    # ---- console table ----------------------------------------------------
    print()
    print("=== VIZ-Gate 0 acceptance suite ===")
    width = max(len(r["name"]) for r in results) + 2
    for r in results:
        print(f"  {r['name']:<{width}} {'PASS' if r['pass'] else 'FAIL'}"
              f"   ({r['wall_s']:.1f} s)")
        for d in r["details"]:
            print(f"      - {d}")
        if r["error"]:
            print("      ! " + r["error"].strip().replace("\n", "\n      ! "))
    n_pass = sum(r["pass"] for r in results)
    print(f"  => {n_pass}/{len(results)} PASS")

    # ---- markdown report ---------------------------------------------------
    commit = vb.repo_commit_short()
    lines = [
        "# VIZ-Gate 0 acceptance test report",
        "",
        f"- repo commit at run: `{commit}`",
        f"- run time: {time.strftime('%Y-%m-%d %H:%M:%S')} (local)",
        f"- suite: 70_tools/project_visualization/tests ({len(TESTS)} tests, no pytest)",
        f"- result: **{n_pass}/{len(results)} PASS**",
        "",
        "| test | result | wall [s] |",
        "|---|---|---:|",
    ]
    for r in results:
        lines.append(f"| {r['name']} | "
                     f"{'PASS' if r['pass'] else '**FAIL**'} | "
                     f"{r['wall_s']:.1f} |")
    lines.append("")
    for r in results:
        lines.append(f"## {r['name']} — {'PASS' if r['pass'] else 'FAIL'}")
        lines.append("")
        for d in r["details"]:
            lines.append(f"- {d}")
        if r["error"]:
            lines += ["", "```", r["error"].rstrip(), "```"]
        lines.append("")
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  report written: {os.path.relpath(REPORT_MD, REPO)}")

    return n_pass == len(results)


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
