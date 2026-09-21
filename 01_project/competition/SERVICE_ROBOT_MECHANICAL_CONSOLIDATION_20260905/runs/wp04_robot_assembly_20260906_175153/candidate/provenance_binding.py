"""Fail-closed final receipt/geometry identities; stdlib only."""
from pathlib import Path
import hashlib,json,math
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def instance_identity_sha256(rows):
    keys=("id","mass_owner","product_role","representation_role","mass_source","mass_kg","arm_link")
    return digest(sorted(({k:r.get(k) for k in keys} for r in rows),key=lambda r:r["id"]))
def verify_hashes(hashes):
    if not isinstance(hashes,dict) or not hashes:raise ValueError("MISSING_INPUT_HASHES")
    for p,h in hashes.items():
        if not isinstance(h,str) or len(h)!=64 or not Path(p).is_file() or sha(p)!=h:raise ValueError("SOURCE_HASH_MISMATCH:"+str(p))
def receipt_binding(receipt,path):
    return dict(configuration=receipt["configuration"],view=receipt["view"],receipt_path=str(Path(path).resolve()),receipt_sha256=sha(path),instance_identity_sha256=instance_identity_sha256(receipt["instances"]))
def validate_receipt_source(receipt,here):
    here=Path(here)
    if receipt.get("view")!="complete" or receipt.get("state") not in ("parking","released","service"):raise ValueError("NONPHYSICAL_OR_WRONG_STATE")
    if not isinstance(receipt.get("configuration"),str) or not receipt["configuration"]:raise ValueError("MISSING_CONFIGURATION")
    if receipt.get("source_sha256")!=sha(here/"spacecraft_model.py"):raise ValueError("STALE_MODEL_SOURCE")
    deps=receipt.get("dependency_sha256");required={"design_parameters.json","root_structure.py","wing_kinematics.py","kinematics.py","r01_design.py","candidate_context.py"}
    required.add('r07_design.py')
    if not isinstance(deps,dict) or not required<=set(deps):raise ValueError("MISSING_REQUIRED_SOURCE_DEPENDENCY")
    for name,h in deps.items():
        p=(here/name).resolve()
        if not p.is_relative_to(here.resolve()) or not p.is_file() or sha(p)!=h:raise ValueError("RECEIPT_DEPENDENCY_MISMATCH:"+name)
    if not receipt.get("geometry_sha256"):raise ValueError("MISSING_FINAL_GEOMETRY_BINDING")
    verify_hashes(receipt["geometry_sha256"]);ids=set();owners=set()
    for r in receipt["instances"]:
        if not r.get("id") or r["id"] in ids:raise ValueError("DUPLICATE_OR_MISSING_INSTANCE_ID")
        if not r.get("mass_owner") or r["mass_owner"] in owners:raise ValueError("DUPLICATE_OR_MISSING_OWNER")
        if r.get("configuration")!=receipt["state"]:raise ValueError("INSTANCE_CONFIGURATION_MISMATCH")
        if r.get("product_role")!="ONBOARD_CANDIDATE":raise ValueError("NON_ONBOARD_INSTANCE_IN_COMPLETE_RECEIPT")
        if r.get("mass_source")=="UNKNOWN" and r.get("mass_kg") is not None and not r.get("arm_link"):raise ValueError("UNKNOWN_MASS_BECAME_NUMBER")
        m=r.get("mass_kg")
        if m is not None and (type(m) not in (int,float) or not math.isfinite(m) or m<0):raise ValueError("INVALID_MASS")
        ids.add(r["id"]);owners.add(r["mass_owner"])
    if receipt.get('composition') or receipt.get('composition_mode') or any(r.get('geometry_reuse') for r in receipt['instances']) or ((here/'compose_receipts.py').is_file() and any(r.get('arm_link') for r in receipt['instances'])):
        from composition_binding import validate_composition
        validate_composition(receipt,here)
    return True
