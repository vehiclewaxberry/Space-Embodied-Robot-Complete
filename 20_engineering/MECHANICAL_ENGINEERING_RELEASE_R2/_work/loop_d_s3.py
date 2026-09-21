import hashlib, shutil
from datetime import datetime, timezone
from pathlib import Path
import yaml, json
ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
REL = ROOT/"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
M7 = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
WP1 = M7+"/wp1_structure_cad"
now = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
# 02/03/04 master geometry + product structure
shutil.copy(ROOT/(WP1+"/PRODUCT_STRUCTURE_V1.yaml"), REL/"02_PRODUCT_STRUCTURE.yaml")
shutil.copy(ROOT/(WP1+"/DESIGN_FREEZE_ASSEMBLY_V1.FCStd"), REL/"03_MASTER_GEOMETRY.FCStd")
shutil.copy(ROOT/(WP1+"/DESIGN_FREEZE_ASSEMBLY_V1.step"), REL/"04_MASTER_GEOMETRY.step")
# 08 configuration library
(REL/"08_CONFIGURATION_LIBRARY.yaml").write_text(yaml.safe_dump({
 "schema":"CONFIGURATION_LIBRARY_REF_V1","generated_utc":now,
 "nine_configuration_mass_properties":{"path":M7+"/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml","sha256":sha(ROOT/(M7+"/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"))},
 "configuration_mass_inertia_csv":{"path":"20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/CONFIGURATION_MASS_INERTIA.csv","sha256":sha(ROOT/"20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/CONFIGURATION_MASS_INERTIA.csv")},
 "selected_configuration":"C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
 "class":"DESIGN_MODEL_NOT_AS_BUILT",
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
}, allow_unicode=True, sort_keys=False), encoding="utf-8")
# 19 open qualification holds
holds = [
 ("HOLD-01","launcher/deployer ICD","EXTERNAL","launcher authority"),
 ("HOLD-02","separation ICD","EXTERNAL","separation authority"),
 ("HOLD-03","flight material allowables","EXTERNAL","material qualification"),
 ("HOLD-04","as-built mass/CG/inertia metrology","EXTERNAL","hardware measurement"),
 ("HOLD-05","hardware contact calibration (CT01-CT05)","EXTERNAL","contact test"),
 ("HOLD-06","gripper closing-time measurement","EXTERNAL","hardware measurement (AGENTS.md todo-2)"),
 ("HOLD-07","F/T calibration","EXTERNAL","sensor calibration"),
 ("HOLD-08","qualification vibration","EXTERNAL","qualification test"),
 ("HOLD-09","TVAC","EXTERNAL","qualification test"),
 ("HOLD-10","flight HDRM reliability","EXTERNAL","HDRM qualification"),
 ("HOLD-11","full-range Route-C harness enhancement","DEFERRED_HOLD","ODR-42: reopen only if future mission needs states outside verified harness-rated mission envelope"),
 ("HOLD-12","SolidWorks native reintegration","EXTERNAL","native CAD toolchain"),
 ("HOLD-13","M3R as-installed mass properties","EXTERNAL","metrology"),
 ("HOLD-14","e15 ANCF legacy lineage certification","PRESERVED_HARD_NEGATIVE","legacy ANCF line superseded by R2 FE/ROM; E23 cross-solver recertification delivers current-line evidence"),
 ("HOLD-15","Route-C mission-first physical dress-pack design","INTERNAL_DESIGN_OPEN","TMG-4 blocker: ODR-42 approved; P01-P13 physical inputs + route design + CAD branch + evaluation required"),
 ("HOLD-16","Sim13 five NC backends (NC15/16/18/19/20)","INTERNAL_SOFTWARE_OPEN","TMG-6 blocker: SIM13_BACKEND_WORK_ORDERS_V1 registered"),
]
with open(REL/"19_OPEN_QUALIFICATION_HOLDS.csv","w",newline="",encoding="utf-8") as f:
    f.write("hold_id,item,class,authority_or_trigger\n")
    for h in holds: f.write(",".join('"%s"'%x if "," in x else x for x in h)+"\n")
print("s3 done")
