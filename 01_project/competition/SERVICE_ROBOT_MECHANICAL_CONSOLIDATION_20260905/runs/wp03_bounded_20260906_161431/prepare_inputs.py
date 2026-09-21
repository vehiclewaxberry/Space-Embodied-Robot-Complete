from pathlib import Path
import json,hashlib,shutil,datetime
RUN=Path(__file__).resolve().parent
ROOT=Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
WP=ROOT/"20_engineering/service_robot_wp03_spacecraft_body_r1"
names=["spacecraft_model.py","root_structure.py","kinematics.py","wing_kinematics.py","design_parameters.json","dynamics_handoff.py","export_parts_and_bom.py","pose_screen.py","geometry_checks.py","integrate_checks.py","servicer_service.step.py","servicer_parking.step.py","servicer_released.step.py","interface_drawings.py","wp03_interfaces.dxf.py"]
rows=[]
for name in names:
    p=WP/name
    for target in [RUN/"inputs"/name,RUN/"candidate"/name]:
        if target.exists():raise RuntimeError("Refuse duplicate setup "+str(target))
        shutil.copy2(p,target)
    rows.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,kind="MINIMUM_EDITABLE_SOURCE_SNAPSHOT"))
deps=[ROOT/"01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json",ROOT/"01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/run_manifest.json",ROOT/"01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/dependency_manifest.json"]
for name in ["parts_model.py","design_parameters.json","motion_analysis.py","results/CONTACT_REGISTRATION.json","results/HARNESS_ANALYSIS.json","inputs/m3r_a.step","inputs/m3r_b.step"]:deps.append(ROOT/"20_engineering/service_robot_wp02_20260905"/name)
for name in ["kinematics.py","design_parameters.json","LAYOUT_COMPARISON.json","results/stowed_build_receipt.json","results/FINGER_INTERFACE_CHECK.json"]:deps.append(ROOT/"20_engineering/service_robot_wp01_20260905"/name)
deps.extend((WP/"results"/f"{s}_instances.json") for s in ["parking","released","service"])
deps.extend([WP/"results/DYNAMICS_HANDOFF.json",WP/"BOM.csv"])
arm=ROOT/"20_engineering/cad/spacecraft_layout/arm_b601_v1"
deps.append(arm/"arm_b601_v1.urdf")
import xml.etree.ElementTree as ET
for link in ET.parse(arm/"arm_b601_v1.urdf").getroot().findall("link"):
    deps.append(arm/link.find("visual/geometry/mesh").get("filename"))
for p in deps:
    rows.append(dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,kind="READ_ONLY_DEPENDENCY"))
for d in ["results","parts"]: (RUN/"candidate"/d).mkdir(exist_ok=True)
manifest=dict(run_id=RUN.name,created_local=datetime.datetime.now().astimezone().isoformat(),user_authorization="现在按照规划帮助我执行下一步机械设计现在开始，就按照你规划的来",work_mode="BOUNDED_CANDIDATE_DESIGN_EXECUTION",original_sources_read_only=True,full_workspace_backup=False,source_snapshot=rows,write_whitelist=[str(RUN),str(ROOT/"01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json"),str(ROOT/"01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/run_manifest.json"),str(ROOT/"01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/dependency_manifest.json")],current_pointer_promotion=False,historical_gate_changes=False)
(RUN/"inputs/INPUT_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
for name in ["issues.json","run_manifest.json","dependency_manifest.json"]:
    shutil.copy2(ROOT/"01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905"/name,RUN/"inputs"/name)
print(json.dumps(dict(run_id=RUN.name,editable_source_count=len(names),read_only_dependencies=len(deps),source_entries=len(rows))))

