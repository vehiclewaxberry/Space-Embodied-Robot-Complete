import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
REL = ROOT/"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
now = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
entries = []
for f in sorted(REL.iterdir()):
    if f.is_file():
        entries.append({"file": f.name, "bytes": f.stat().st_size, "sha256": sha(f)})
manifest = {
 "schema":"BASELINE_MANIFEST_V1","generated_utc":now,
 "release_directory":"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2",
 "owner_directive":"TERMINAL MECHANICAL ONE-SHOT CLOSURE (2026-08-25)",
 "entry_rule":"all current mechanical state is read only from this directory and the hash-bound upstream artifacts it pins; M3-M7 history is lineage, not active design",
 "loop_a_truth_reports":"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_a (A1-A6 extraction evidence)",
 "files":entries,
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
}
(REL/"01_BASELINE_MANIFEST.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("manifest written with", len(entries), "files")
