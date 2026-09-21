# -*- coding: utf-8 -*-
"""FreeCADCmd: render witness views of a posed F3R2 scene.

Renders REAL geometry: the environment STL set plus the CAD arm links carried
to the requested pose by the same relative transform the clearance analysis
uses.  These are witness views of what was measured, not illustrations drawn
for the camera.

env: F3R2_SCENE (json produced by r2m_shots.py)  F3R2_SHOTDIR
"""
import json
import os

import FreeCAD
import FreeCADGui
import Mesh

SCENE = json.load(open(os.environ["F3R2_SCENE"], encoding="utf-8"))
SHOTDIR = os.environ["F3R2_SHOTDIR"]
W, H = 1600, 1000
os.makedirs(SHOTDIR, exist_ok=True)

FreeCADGui.showMainWindow()
out = {"schema": "F3R2_RENDER_INDEX_V1", "shots": []}

for shot in SCENE["shots"]:
    doc = FreeCAD.newDocument(shot["id"])
    for item in shot["meshes"]:
        m = Mesh.Mesh(item["path"])
        t = item.get("transform")
        if t:
            m.transform(FreeCAD.Matrix(*[v for row in t for v in row]))
        o = doc.addObject("Mesh::Feature", item["name"][:40])
        o.Mesh = m
        gui = FreeCADGui.getDocument(doc.Name).getObject(o.Name)
        col = item.get("color")
        if col:
            gui.ShapeColor = tuple(col)
        if item.get("transparency"):
            gui.Transparency = int(item["transparency"])
    doc.recompute()
    FreeCADGui.updateGui()
    v = FreeCADGui.activeDocument().activeView()
    getattr(v, "view" + shot.get("view", "Isometric"))()
    v.fitAll()
    FreeCADGui.updateGui()
    png = os.path.join(SHOTDIR, shot["id"] + ".png")
    v.saveImage(png, W, H, "White")
    ok = os.path.isfile(png)
    out["shots"].append({"id": shot["id"], "png": png, "ok": ok,
                         "bytes": os.path.getsize(png) if ok else 0,
                         "caption": shot.get("caption", ""),
                         "meshes": len(shot["meshes"]),
                         "view": shot.get("view", "Isometric")})
    print("%-38s %s" % (shot["id"], "OK" if ok else "FAILED"))
    FreeCAD.closeDocument(doc.Name)

with open(os.path.join(SHOTDIR, "F3R2_RENDER_INDEX.json"), "w",
          encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print("rendered:", sum(1 for s in out["shots"] if s["ok"]), "/",
      len(out["shots"]))
