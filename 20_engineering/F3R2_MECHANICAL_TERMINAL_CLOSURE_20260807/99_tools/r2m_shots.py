# -*- coding: utf-8 -*-
"""F3R2 witness shots: build the scene description, then render it.

Each shot is the geometry that was actually measured, posed by the same
relative transform the clearance analysis used.  Colours carry meaning:
  arm       steel blue
  bus       light grey
  wings     amber
  saddles   red  (placeholders -- deliberately alarming)
  reference translucent violet (never physical evidence)
"""
import json
import subprocess
import sys
import traceback

import numpy as np

import r2_common as C
import r2_pose as P

SCENE = C.SHOT2 / "F3R2_SCENE.json"
RAW = C.SHOT2 / "RAW"
FC = r"G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe"

COL = {"arm": [0.25, 0.45, 0.75], "bus": [0.78, 0.78, 0.80],
       "wing": [0.90, 0.68, 0.20], "saddle": [0.85, 0.20, 0.20],
       "mount": [0.55, 0.60, 0.68], "ref": [0.65, 0.45, 0.85]}
Q = {}


def load_q():
    ev = json.loads((C.CFG2 / "F3R2_POSE_EVALUATION.json")
                    .read_text(encoding="utf-8"))["poses"]
    se = json.loads((C.CFG2 / "F3R2_POSE_SEARCH.json")
                    .read_text(encoding="utf-8"))["results"]
    q = {"Q_AS_BUILT_REFERENCE": ev["Q_AS_BUILT_REFERENCE"]["q_deg"],
         "Q_STOW_ENGINEERING_CANDIDATE":
             ev["Q_STOW_ENGINEERING_CANDIDATE"]["q_deg"]}
    for k in ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"):
        q[k] = se[k]["chosen"]["evaluation"]["q_deg"]
    return q


def role_colour(role):
    return {"SOLAR_WING": COL["wing"], "SADDLE_PLACEHOLDER": COL["saddle"],
            "REFERENCE_ONLY": COL["ref"],
            "ARM_MOUNT_INTERFACE": COL["mount"]}.get(role, COL["bus"])


def scene_for(pose_name, tag, wings, view="Isometric", include=None,
              caption="", q_override=None):
    arms = P.arm_parts(tag)
    envs = P.env_parts(tag, wings=wings)
    q = q_override if q_override is not None else [0.0] * 6
    meshes = []
    for cad, a in arms.items():
        T = P.rel_transform(a["link"], q)
        meshes.append({"name": a["link"], "path": a["path"],
                       "color": COL["arm"],
                       "transform": [[float(x) for x in row]
                                     for row in T.tolist()]})
    for name, e in envs.items():
        if include and not any(t in name for t in include):
            continue
        meshes.append({"name": name, "path": e["path"],
                       "color": role_colour(e["role"]),
                       "transparency": 60 if e["role"] == "REFERENCE_ONLY"
                       else 0})
    return {"id": pose_name, "view": view, "caption": caption,
            "meshes": meshes}


def main():
    rep = {"schema": "F3R2_SHOTS_V1"}
    try:
        C.check_protected2("SHOTS_PRE")
        q = load_q()
        DW = ("WING_L_DEPLOYED", "WING_R_DEPLOYED")
        SW = ("WING_L_STOWED", "WING_R_STOWED")
        shots = [
            scene_for("S01_DEPLOYED_NOMINAL_ISO", "DEPLOYED", DW,
                      "Isometric",
                      caption="DEPLOYED_NOMINAL, arm at as-built pose"),
            scene_for("S02_Q_DEPLOYED_HOME", "DEPLOYED", DW, "Isometric",
                      caption="Q_DEPLOYED_HOME -- control initialisation pose",
                      q_override=q["Q_DEPLOYED_HOME"]),
            scene_for("S03_Q_DEPLOYED_HOME_TOP", "DEPLOYED", DW, "Top",
                      caption="Q_DEPLOYED_HOME, top view",
                      q_override=q["Q_DEPLOYED_HOME"]),
            scene_for("S04_Q_SERVICE_READY", "DEPLOYED", DW, "Isometric",
                      caption="Q_SERVICE_READY -- pre-service staging",
                      q_override=q["Q_SERVICE_READY"]),
            scene_for("S05_Q_RELEASE_CLEAR", "DEPLOYED", DW, "Isometric",
                      caption="Q_RELEASE_CLEAR -- first safe pose after release",
                      q_override=q["Q_RELEASE_CLEAR"]),
            scene_for("S06_STOW_CANDIDATE_ISO", "STOWED", SW, "Isometric",
                      caption=("STOWED_ENGINEERING_CANDIDATE (q_stow, "
                               "PROVISIONAL hold)")),
            scene_for("S07_STOW_SADDLE_CONTACT", "STOWED", SW, "Front",
                      include=("Saddle", "Launch_Lock", "Release_Clearance"),
                      caption=("stow contact zone: the three RED blocks are "
                               "placeholders, not supports")),
            scene_for("S08_ARM_BUS_CRITICAL_CLEARANCE", "DEPLOYED", DW,
                      "Front",
                      include=("Central_Boss", "Adapter_Plate",
                               "Spacecraft_Flange", "Load_"),
                      caption="arm mount interface, critical clearance region",
                      q_override=q["Q_DEPLOYED_HOME"]),
            scene_for("S09_WING_ROOT_LEFT", "DEPLOYED", DW, "Right",
                      include=("Hinge", "Torsion", "Hard_Stop", "Root_",
                               "WING_L"),
                      caption=("LEFT wing root: real pin r=4.000 and ears "
                               "r=4.200 exist; the wing has NO lug (30.0 mm "
                               "gap, D-F3R1-06 open)")),
            scene_for("S10_WING_ROOT_RIGHT", "DEPLOYED", DW, "Left",
                      include=("Hinge", "Torsion", "Hard_Stop", "Root_",
                               "WING_R"),
                      caption="RIGHT wing root, mirrored and independent"),
            scene_for("S11_STOW_SIDE", "STOWED", SW, "Right",
                      caption="stow configuration, side view"),
            scene_for("S12_DEPLOYED_FRONT", "DEPLOYED", DW, "Front",
                      caption="DEPLOYED_NOMINAL, front view"),
        ]
        SCENE.parent.mkdir(parents=True, exist_ok=True)
        C.write_json(SCENE, {"shots": shots})
        rep["scene"] = str(SCENE)
        rep["n_shots"] = len(shots)

        env = dict(**{"F3R2_SCENE": str(SCENE), "F3R2_SHOTDIR": str(RAW)})
        import os
        e = os.environ.copy()
        e.update(env)
        r = subprocess.run([FC, str(C.F3R2 / "99_tools" / "fc_render_scene.py")],
                           capture_output=True, text=True, timeout=2400, env=e)
        (C.LOGS2 / "fc_render.txt").write_text(
            (r.stdout or "") + "\n---STDERR---\n" + (r.stderr or ""),
            encoding="utf-8")
        idx = RAW / "F3R2_RENDER_INDEX.json"
        if idx.is_file():
            got = json.loads(idx.read_text(encoding="utf-8"))
            rep["rendered"] = sum(1 for s in got["shots"] if s["ok"])
            rep["shots"] = got["shots"]
        else:
            rep["rendered"] = 0
            rep["render_stdout_tail"] = (r.stdout or "")[-1500:]
            rep["render_stderr_tail"] = (r.stderr or "")[-1500:]
        rep["verdict"] = ("SHOTS_RENDERED" if rep["rendered"] == len(shots)
                          else "SHOTS_INCOMPLETE")
        rep["protected_post"] = C.check_protected2("SHOTS_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "SHOTS_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_json(C.SHOT2 / "F3R2_SHOT_REPORT.json", rep)
    print("verdict:", rep["verdict"], "| rendered", rep.get("rendered"),
          "/", rep.get("n_shots"))
    for s in rep.get("shots", []):
        print("   %-34s %-5s %8s B  %s" % (s["id"], s["ok"], s["bytes"],
                                           s["caption"][:52]))
    if rep["verdict"] != "SHOTS_RENDERED":
        print(rep.get("render_stderr_tail") or rep.get("traceback") or "")
    sys.exit(0 if rep["verdict"] == "SHOTS_RENDERED" else 1)


if __name__ == "__main__":
    main()
