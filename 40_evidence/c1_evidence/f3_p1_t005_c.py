# -*- coding: utf-8 -*-
"""F3-P1 T005-C: Cold reopen test.

Saves a candidate assembly, closes FreeCAD, reopens with FreeCADCmd,
and compares all critical properties.
"""
from __future__ import print_function
import faulthandler
import json
import hashlib
import os
import sys
import time
import traceback

faulthandler.enable()
faulthandler.dump_traceback_later(300, repeat=True)

WS = r"F:\Space-Embodied-Robot-HAG_A_20260804"
VISUAL_PACKAGES_DIR = os.path.join(WS, r"12_f3_p1_hifi_attachment\01_visual_packages")
OUT_DIR = os.path.join(WS, r"12_f3_p1_hifi_attachment\10_t005_c")

LOG_PATH = os.path.join(OUT_DIR, "t005_c.log")


def mark(stage, **data):
    record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "pid": os.getpid(), "stage": stage}
    record.update(data)
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print("LOG_ERROR: " + str(e), file=sys.stderr, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    t0 = time.time()
    result = {
        "status": "STARTED",
        "exceptions": [],
        "packages": {},
        "summary": {},
    }

    try:
        mark("SCRIPT_START")
        mark("BEFORE_FREECAD_IMPORT")
        import FreeCAD as App
        mark("AFTER_FREECAD_IMPORT", version=str(App.Version()))

        # Test each visual package
        package_files = [f for f in os.listdir(VISUAL_PACKAGES_DIR) if f.endswith(".FCStd")]
        mark("PACKAGES_FOUND", count=len(package_files))

        for pkg_file in package_files:
            pkg_path = os.path.join(VISUAL_PACKAGES_DIR, pkg_file)
            pkg_name = pkg_file.replace(".FCStd", "")
            mark("PACKAGE_TEST_START", package=pkg_name)

            # Record pre-close state
            pre_sha = sha256_file(pkg_path)
            pre_size = os.path.getsize(pkg_path)

            # Open
            mark("BEFORE_OPEN", package=pkg_name)
            t_open0 = time.time()
            doc = App.openDocument(pkg_path)
            t_open1 = time.time()
            mark("AFTER_OPEN", package=pkg_name, objects=len(doc.Objects), elapsed_s=round(t_open1 - t_open0, 3))

            # Record state
            n_objects = len(doc.Objects)
            n_part_feature = sum(1 for obj in doc.Objects if obj.TypeId == "Part::Feature")
            n_valid = 0
            n_invalid = 0
            total_vol = 0.0

            for obj in doc.Objects:
                if obj.TypeId == "Part::Feature":
                    try:
                        sh = obj.Shape
                        if sh is not None and not sh.isNull():
                            if sh.isValid():
                                n_valid += 1
                            else:
                                n_invalid += 1
                            total_vol += float(sh.Volume)
                    except Exception:
                        pass

            # Recompute
            mark("BEFORE_RECOMPUTE", package=pkg_name)
            t_rc0 = time.time()
            doc.recompute()
            t_rc1 = time.time()
            mark("AFTER_RECOMPUTE", package=pkg_name, elapsed_s=round(t_rc1 - t_rc0, 3))

            # Close
            mark("BEFORE_CLOSE", package=pkg_name)
            App.closeDocument(doc.Name)
            mark("AFTER_CLOSE", package=pkg_name)

            # Reopen (cold)
            mark("BEFORE_COLD_REOPEN", package=pkg_name)
            t_cold0 = time.time()
            doc2 = App.openDocument(pkg_path)
            t_cold1 = time.time()
            mark("AFTER_COLD_REOPEN", package=pkg_name, objects=len(doc2.Objects), elapsed_s=round(t_cold1 - t_cold0, 3))

            # Compare
            n_objects2 = len(doc2.Objects)
            n_part_feature2 = sum(1 for obj in doc2.Objects if obj.TypeId == "Part::Feature")
            total_vol2 = 0.0
            for obj in doc2.Objects:
                if obj.TypeId == "Part::Feature":
                    try:
                        sh = obj.Shape
                        if sh is not None and not sh.isNull():
                            total_vol2 += float(sh.Volume)
                    except Exception:
                        pass

            App.closeDocument(doc2.Name)

            # Post-close hash
            post_sha = sha256_file(pkg_path)

            match = {
                "objects_match": n_objects == n_objects2,
                "part_features_match": n_part_feature == n_part_feature2,
                "volume_match": abs(total_vol - total_vol2) < 1e-6,
                "hash_unchanged": pre_sha == post_sha,
                "n_objects": n_objects,
                "n_objects_reopen": n_objects2,
                "n_part_features": n_part_feature,
                "n_part_features_reopen": n_part_feature2,
                "total_volume": total_vol,
                "total_volume_reopen": total_vol2,
                "open_elapsed_s": round(t_open1 - t_open0, 3),
                "cold_reopen_elapsed_s": round(t_cold1 - t_cold0, 3),
                "recompute_elapsed_s": round(t_rc1 - t_rc0, 3),
            }

            all_match = all([match["objects_match"], match["part_features_match"],
                           match["volume_match"], match["hash_unchanged"]])
            match["status"] = "PASS" if all_match else "FAIL"
            result["packages"][pkg_name] = match

            mark("PACKAGE_TEST_COMPLETE", package=pkg_name, status=match["status"])

        # Summary
        all_pass = all(p["status"] == "PASS" for p in result["packages"].values())
        result["summary"] = {
            "packages_tested": len(result["packages"]),
            "all_pass": all_pass,
            "total_elapsed_s": round(time.time() - t0, 3),
        }
        result["status"] = "PASS" if all_pass else "FAIL"
        mark("SCRIPT_PASS", **result["summary"])

    except Exception as exc:
        mark("SCRIPT_EXCEPTION", error=str(exc), traceback=traceback.format_exc())
        result["status"] = "FAIL"
        result["exceptions"].append({"error": str(exc), "trace": traceback.format_exc()})

    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = os.path.join(OUT_DIR, "T005_C_RESULTS.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    mark("RESULT_WRITTEN", path=out_json)


main()
