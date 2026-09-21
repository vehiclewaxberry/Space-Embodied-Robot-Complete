# -*- coding: utf-8 -*-
"""G2 Phase -1: uniquely resolve the project + assembly paths by SHA-256.

Refuses to assume the current directory is right. Searches the repo for every
candidate with the expected names, hashes each, and requires that EXACTLY ONE
matches the G1 report's POST hash prefix (E752FFC4CEFAC1D8) and that the G0
frozen original still carries 5F1CB650F1E88ABF. Also rejects anything living
under backup / failed_builds / temp / old-version directories, and confirms all
dependencies of the chosen assembly sit inside the F3R1 isolation tree.

Emits G2_RESOLVED_PATHS.json. On ambiguity: G2_HOLD_PROJECT_OR_ASSEMBLY_PATH_AMBIGUOUS.
No SolidWorks needed -- pure filesystem + hash resolution.
"""
import json
import sys

from f3r1_env import F3R1, REPO, JLog, check_protected, sha256_file

log = JLog("g2_resolve")
NC = F3R1 / "03_native_cad"
G2 = F3R1 / "04_configurations" / "G2"
OUT = G2 / "F3R1_G2_RESOLVED_PATHS.json"

G1_POST_PREFIX = "E752FFC4CEFAC1D8"
G0_FROZEN_PREFIX = "5F1CB650F1E88ABF"
BAD_DIR_TOKENS = ("backup", "failed_build", "failed_builds", "temp", "tmp",
                  "archive", "old", "_bak", "recycle")

TARGETS = {
    "g1_v2_mated": "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM",
    "g0_frozen": "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM",
    "g1_report": "F3R1_P5_REPORT_01_G0_G1_20260806.md",
    "mate_attempt_log": "F3R1_MATE_ATTEMPT_LOG.json",
}


def find_all(name):
    return [p for p in REPO.rglob(name) if p.is_file()
            and not p.name.startswith("~$")]


def suspect(path):
    """Flag only when a DIRECTORY SEGMENT is a reject token. A plain substring
    test false-positives (e.g. 'temp' inside 'MATE_ATTEMPT_LOG'), which would
    silently drop a legitimate artifact."""
    hits = []
    for seg in path.parts[:-1]:            # directories only, not the filename
        s = seg.lower()
        for t in BAD_DIR_TOKENS:
            if t == s or s.startswith(t + "_") or s.endswith("_" + t):
                hits.append("%s(%s)" % (t, seg))
    return hits


def main():
    check_protected("G2_RESOLVE_PRE")
    rep = {"schema": "F3R1_G2_RESOLVED_PATHS_V1", "repo": str(REPO),
           "expected": {"g1_post_sha_prefix": G1_POST_PREFIX,
                        "g0_frozen_sha_prefix": G0_FROZEN_PREFIX},
           "candidates": {}, "resolved": {}, "problems": []}

    for key, name in TARGETS.items():
        hits = find_all(name)
        recs = []
        for p in hits:
            r = {"path": str(p), "suspect_dir_tokens": suspect(p)}
            if p.suffix.lower() in (".sldasm", ".sldprt", ".json", ".md"):
                try:
                    r["sha256"] = sha256_file(p)
                except Exception as e:
                    r["sha256"] = "UNREADABLE:%s" % str(e)[:50]
            recs.append(r)
        rep["candidates"][key] = recs
        if not recs:
            rep["problems"].append("MISSING:%s" % name)

    # --- choose the assembly whose SHA matches the G1 report POST hash ---
    v2 = [r for r in rep["candidates"].get("g1_v2_mated", [])
          if not r["suspect_dir_tokens"]
          and str(r.get("sha256", "")).startswith(G1_POST_PREFIX)]
    if len(v2) == 1:
        rep["resolved"]["g1_v2_mated"] = v2[0]
    else:
        rep["problems"].append(
            "G1_V2_MATED_NOT_UNIQUELY_RESOLVED count=%d" % len(v2))

    g0 = [r for r in rep["candidates"].get("g0_frozen", [])
          if not r["suspect_dir_tokens"]
          and str(r.get("sha256", "")).startswith(G0_FROZEN_PREFIX)]
    if len(g0) == 1:
        rep["resolved"]["g0_frozen"] = g0[0]
    else:
        rep["problems"].append(
            "G0_FROZEN_NOT_UNIQUELY_RESOLVED count=%d" % len(g0))

    for key in ("g1_report", "mate_attempt_log"):
        clean = [r for r in rep["candidates"].get(key, [])
                 if not r["suspect_dir_tokens"]]
        if len(clean) == 1:
            rep["resolved"][key] = clean[0]
        else:
            rep["problems"].append("%s_NOT_UNIQUE count=%d" % (key.upper(),
                                                               len(clean)))

    # --- dependency ownership: every referenced CAD file under F3R1 ---
    own = F3R1 / "03_native_cad" / "F3R1_COMPONENT_OWNERSHIP.csv"
    rep["ownership_register"] = str(own)
    outside = []
    if own.is_file():
        import csv
        with open(own, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if row.get("inside_f3r1", "").strip().lower() != "true":
                    outside.append(row.get("path", ""))
    else:
        rep["problems"].append("OWNERSHIP_REGISTER_MISSING")
    rep["dependencies_outside_f3r1"] = sorted(set(p for p in outside if p))
    if rep["dependencies_outside_f3r1"]:
        rep["problems"].append("DEPENDENCIES_OUTSIDE_F3R1 n=%d"
                               % len(rep["dependencies_outside_f3r1"]))

    # --- G2 output target (must not overwrite G1) ---
    v3 = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM"
    rep["g2_output_assembly"] = str(v3)
    rep["g2_output_exists_already"] = v3.is_file()
    rep["g2_output_dir"] = str(G2)

    rep["verdict"] = ("G2_PATHS_RESOLVED" if not rep["problems"]
                      else "G2_HOLD_PROJECT_OR_ASSEMBLY_PATH_AMBIGUOUS")
    check_protected("G2_RESOLVE_POST")
    G2.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("verdict:", rep["verdict"])
    for k, v in rep["resolved"].items():
        print("  %-18s %s" % (k, v["path"]))
        if "sha256" in v:
            print("  %-18s sha=%s" % ("", v["sha256"][:24]))
    print("  deps outside F3R1:", len(rep["dependencies_outside_f3r1"]))
    print("  G2 output:", rep["g2_output_assembly"],
          "(exists=%s)" % rep["g2_output_exists_already"])
    if rep["problems"]:
        print("  PROBLEMS:")
        for p in rep["problems"]:
            print("    -", p)
    sys.exit(0 if rep["verdict"] == "G2_PATHS_RESOLVED" else 1)


if __name__ == "__main__":
    main()
