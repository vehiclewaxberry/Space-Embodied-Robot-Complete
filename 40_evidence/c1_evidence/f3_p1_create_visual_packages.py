# -*- coding: utf-8 -*-
"""F3-P1: Create 10 link visual packages from HAG-A3 ownership + donor FCStd.

Each link gets an independent FCStd containing only its assigned objects.
Records AuthorityRole, DynamicsMassAuthority, JointAuthority, etc.
"""
from __future__ import print_function
import faulthandler
import csv
import json
import hashlib
import os
import sys
import time
import traceback

faulthandler.enable()
faulthandler.dump_traceback_later(300, repeat=True)

WS = r"F:\Space-Embodied-Robot-HAG_A_20260804"
DONOR_FCSTD = os.path.join(WS, r"03_import_headless\B601_HIFI_HEADLESS_IMPORT.FCStd")
OWNERSHIP_CSV = os.path.join(WS, r"05_link_ownership\B601_HIFI_LINK_OWNERSHIP.csv")
FRAME_MAPPING = os.path.join(WS, r"06_frame_mapping\B601_HIFI_FRAME_MAPPING.json")
OUT_DIR = os.path.join(WS, r"12_f3_p1_hifi_attachment\01_visual_packages")
OUT_REGISTER = os.path.join(OUT_DIR, "B601_HIFI_VISUAL_PACKAGE_REGISTER.csv")

LOG_PATH = os.path.join(WS, r"12_f3_p1_hifi_attachment\hag_f3p1_visual_packages.log")

LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]


def mark(stage, **data):
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pid": os.getpid(),
        "stage": stage,
    }
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
    }

    try:
        mark("SCRIPT_START")
        mark("BEFORE_FREECAD_IMPORT")
        import FreeCAD as App
        import Part
        mark("AFTER_FREECAD_IMPORT", version=str(App.Version()))

        # Load ownership
        ownership = {}
        with open(OWNERSHIP_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["ownership_class"] == "EXACTLY_ONE_LINK":
                    link = row["assigned_link"]
                    if link not in ownership:
                        ownership[link] = []
                    ownership[link].append(row["donor_object_id"])

        mark("OWNERSHIP_LOADED", links=list(ownership.keys()))

        # Load frame mapping
        with open(FRAME_MAPPING, "r", encoding="utf-8") as f:
            frame_map = json.load(f)

        # Open donor
        mark("BEFORE_OPEN_DONOR", path=DONOR_FCSTD)
        donor_doc = App.openDocument(DONOR_FCSTD)
        mark("AFTER_OPEN_DONOR", object_count=len(donor_doc.Objects))

        donor_sha = sha256_file(DONOR_FCSTD)
        mark("DONOR_SHA256", sha256=donor_sha)

        # Create visual package for each link
        register_rows = []
        for link in LINKS:
            mark("PACKAGE_START", link=link)
            obj_ids = ownership.get(link, [])
            if not obj_ids:
                mark("PACKAGE_SKIP", link=link, reason="no_objects")
                continue

            # Create new document
            doc_name = "B601_HIFI_VISUAL_" + link.upper()
            pkg_doc = App.newDocument(doc_name)

            # Copy objects
            copied = 0
            for obj_id in obj_ids:
                try:
                    donor_obj = donor_doc.getObject(obj_id)
                    if donor_obj is None:
                        mark("OBJECT_NOT_FOUND", link=link, obj_id=obj_id)
                        continue
                    # Copy object to new document
                    new_obj = pkg_doc.addObject("Part::Feature", obj_id)
                    new_obj.Shape = donor_obj.Shape.copy()
                    new_obj.Label = donor_obj.Label
                    new_obj.Placement = donor_obj.Placement.copy()

                    # Set custom properties using addProperty
                    new_obj.addProperty("App::PropertyString", "AuthorityRole", "HIFI", "Authority role").AuthorityRole = "HIFI_VISUAL_GEOMETRY"
                    new_obj.addProperty("App::PropertyString", "DynamicsMassAuthority", "HIFI", "Dynamics mass authority").DynamicsMassAuthority = "EXCLUDED"
                    new_obj.addProperty("App::PropertyString", "JointAuthority", "HIFI", "Joint authority").JointAuthority = "EXCLUDED"
                    new_obj.addProperty("App::PropertyString", "ManufacturingAuthority", "HIFI", "Manufacturing authority").ManufacturingAuthority = "DONOR_REFERENCE_ONLY"
                    new_obj.addProperty("App::PropertyString", "SourceDonorSHA256", "HIFI", "Source donor SHA256").SourceDonorSHA256 = donor_sha
                    new_obj.addProperty("App::PropertyString", "AssignedLink", "HIFI", "Assigned link").AssignedLink = link
                    new_obj.addProperty("App::PropertyString", "RepairBoundary", "HIFI", "Repair boundary").RepairBoundary = "NO_REPAIR"

                    copied += 1
                except Exception as e:
                    mark("OBJECT_COPY_ERROR", link=link, obj_id=obj_id, error=str(e))

            # Save package
            pkg_path = os.path.join(OUT_DIR, doc_name + ".FCStd")
            pkg_doc.saveAs(pkg_path)
            pkg_sha = sha256_file(pkg_path)
            App.closeDocument(pkg_doc.Name)

            register_rows.append({
                "link": link,
                "package_name": doc_name,
                "package_path": pkg_path,
                "package_sha256": pkg_sha,
                "object_count": copied,
                "source_donor_sha256": donor_sha,
                "authority_role": "HIFI_VISUAL_GEOMETRY",
                "dynamics_mass_authority": "EXCLUDED",
                "joint_authority": "EXCLUDED",
                "manufacturing_authority": "DONOR_REFERENCE_ONLY",
                "status": "CREATED",
            })

            mark("PACKAGE_COMPLETE", link=link, objects=copied, path=pkg_path)

            result["packages"][link] = {
                "path": pkg_path,
                "objects": copied,
                "sha256": pkg_sha,
            }

        App.closeDocument(donor_doc.Name)

        # Write register
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(OUT_REGISTER, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["link", "package_name", "package_path", "package_sha256",
                         "object_count", "source_donor_sha256", "authority_role",
                         "dynamics_mass_authority", "joint_authority",
                         "manufacturing_authority", "status"]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in register_rows:
                w.writerow(row)

        result["status"] = "PASS"
        result["elapsed_s"] = round(time.time() - t0, 3)
        result["packages_created"] = len(register_rows)
        mark("SCRIPT_PASS", packages=len(register_rows), elapsed_s=result["elapsed_s"])

    except Exception as exc:
        mark("SCRIPT_EXCEPTION", error=str(exc), traceback=traceback.format_exc())
        result["status"] = "FAIL"
        result["exceptions"].append({"error": str(exc), "trace": traceback.format_exc()})

    # Write result
    out_json = os.path.join(OUT_DIR, "F3_P1_VISUAL_PACKAGES_RESULT.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


main()
