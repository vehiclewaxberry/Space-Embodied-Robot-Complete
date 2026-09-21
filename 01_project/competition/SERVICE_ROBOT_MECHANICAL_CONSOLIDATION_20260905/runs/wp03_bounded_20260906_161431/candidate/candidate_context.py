"""Explicit read-only upstream resolver for this isolated candidate."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
RUN=HERE.parent
PROJECT_ROOT=Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING=PROJECT_ROOT/"20_engineering"
WP01=ENGINEERING/"service_robot_wp01_20260905"
WP02=ENGINEERING/"service_robot_wp02_20260905"
SOURCE_WP03=ENGINEERING/"service_robot_wp03_spacecraft_body_r1"
RUN_ID=RUN.name
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verify_upstream():
    data=json.loads((RUN/"inputs/INPUT_MANIFEST.json").read_text(encoding="utf-8"))
    # Shared ledgers can be appended only at final closeout, after this check.
    bad=[x["path"] for x in data["source_snapshot"] if sha(x["path"])!=x["sha256"]]
    if bad:raise ValueError("Protected source drift: "+str(bad))
    return {x["path"]:x["sha256"] for x in data["source_snapshot"]}

