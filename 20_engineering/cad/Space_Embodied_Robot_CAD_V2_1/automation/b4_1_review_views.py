"""Export claim-limited V2.1 review snapshots from the native top assembly."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import b3_lib.sw_core as core
from b3_lib.sw_core import (B3FailClosed, BuildLog, activate_configuration,
                            connect, open_document, rebuild_or_fail)

V21 = Path(
    r"F:/China Graduate Future Flight Vehicle Innovation Competition/"
    r"20_engineering/cad/Space_Embodied_Robot_CAD_V2_1")
core.V2_ROOT = V21
core.LOG_DIR = V21 / "evidence/build_logs"
TOP = V21 / "Assembly/Spacecraft_Service_Vehicle_V2_1.SLDASM"
RAW = V21 / "evidence/review_views/raw"
ANN = V21 / "evidence/review_views/annotated"

ISO, FRONT, TOP_VIEW, RIGHT = 7, 1, 5, 4
VIEWS = [
    ("V21-VIEW-01", "deployed_nominal_isometric", "DEPLOYED_NOMINAL", ISO,
     "reference geometry; no deployment or collision clearance claim"),
    ("V21-VIEW-02", "stowed_proposal_isometric", "STOWED", ISO,
     "C5 open: 238.3>226.3; no deployer compliance claim"),
    ("V21-VIEW-03", "left_deployment_failure", "L_FAIL", ISO,
     "scenario entry only; no failure analysis completion claim"),
    ("V21-VIEW-04", "right_deployment_failure", "R_FAIL", ISO,
     "scenario entry only; no failure analysis completion claim"),
    ("V21-VIEW-05", "partial_reference", "PARTIAL", ISO,
     "wing representations intentionally suppressed because angle is UNKNOWN"),
    ("V21-VIEW-06", "service_reference", "SERVICE", RIGHT,
     "maintenance reference only; tool and connector clearances not evaluated"),
    ("V21-VIEW-07", "three_bay_top_reference", "DEPLOYED_NOMINAL", TOP_VIEW,
     "frame/deck/panel layout intent; no strength or stiffness claim"),
    ("V21-VIEW-08", "task_face_front_reference", "DEPLOYED_NOMINAL", FRONT,
     "q0 static reference is not B601 workspace or vision clearance"),
]


def annotate(src, dst, view_id, name, config, note):
    image = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(image)
    bar_h = 112
    draw.rectangle(
        [0, image.height - bar_h, image.width, image.height],
        fill=(18, 24, 30))
    lines = [
        f"{view_id}  {name}  |  CONFIG={config}",
        f"claim limit: {note}",
        "B4-1 SEMANTIC REFERENCE CAD | PHYSICAL MECHANISM HOLD | "
        "NON_FLIGHT_DISPLAY_ONLY",
        f"generated {datetime.now(timezone.utc).isoformat()}",
    ]
    y = image.height - bar_h + 8
    for line in lines:
        draw.text((12, y), line, fill=(242, 242, 242))
        y += 25
    image.save(dst)


def main():
    log = BuildLog("b4_1_review_views")
    RAW.mkdir(parents=True, exist_ok=True)
    ANN.mkdir(parents=True, exist_ok=True)
    sw = connect(log, visible=True)
    sw.CloseAllDocuments(True)
    model = open_document(sw, log, TOP, read_only=True)
    manifest = []
    for view_id, name, config, orientation, note in VIEWS:
        activate_configuration(model, log, config)
        rebuild_or_fail(model, log, view_id)
        model.ShowNamedView2("", orientation)
        model.ViewZoomtofit2()
        raw = RAW / f"{view_id}_{name}.bmp"
        if not model.SaveBMP(str(raw), 1600, 1200):
            log.fail("截图失败", view=view_id)
        annotated = ANN / f"{view_id}_{name}_annotated.png"
        annotate(raw, annotated, view_id, name, config, note)
        manifest.append({
            "view": view_id,
            "name": name,
            "configuration": config,
            "raw": str(raw.relative_to(V21)).replace("\\", "/"),
            "annotated": str(annotated.relative_to(V21)).replace("\\", "/"),
            "claim_limit": note,
        })
        log.event("VIEW_EXPORTED", view=view_id, config=config)
    activate_configuration(model, log, "DEPLOYED_NOMINAL")
    sw.CloseAllDocuments(True)
    (V21 / "evidence/review_views/review_view_manifest.json").write_text(
        json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "verdict": "REVIEW_SNAPSHOTS_COMPLETE_WITH_PHYSICAL_LIMITATIONS",
            "views": manifest,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("B4_1_REVIEW_VIEWS_OK", len(manifest))


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as exc:
        print(f"FAIL_CLOSED: {exc}")
        sys.exit(1)
