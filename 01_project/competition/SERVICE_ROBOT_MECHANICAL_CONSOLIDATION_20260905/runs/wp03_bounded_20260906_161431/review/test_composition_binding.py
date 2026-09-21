"""Independent stdlib-only controls for the new compositional receipt validator.

All STEP-like fixture files below contain explicit synthetic marker bytes. They
test file identity and assembly metadata; no fixture is CAD or geometric evidence.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import traceback

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parents[1]
CANDIDATE = RUN / "candidate"
RESULTS = []

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")

def ref(p):
    return dict(path=str(p.resolve()), sha256=sha(p))

def fixture(root):
    here = root / "candidate"
    oldhome = root / "upstream"
    here.mkdir()
    oldhome.mkdir()
    names = ["base_link", *[f"link{i}" for i in range(1, 7)], "gripper_link", "gripper_left", "gripper_right"]
    deps = ["design_parameters.json", "root_structure.py", "wing_kinematics.py", "kinematics.py", "r01_design.py", "candidate_context.py"]
    for home in (here, oldhome):
        for name in ["spacecraft_model.py", *deps, "compose_receipts.py", "composition_binding.py", "provenance_binding.py"]:
            (home / name).write_text("SYNTHETIC_SOURCE_" + home.name + "_" + name, encoding="utf-8")
    matrix = [[1, 0, 0, 90], [0, 1, 0, 0], [0, 0, 1, 125.15], [0, 0, 0, 1]]
    def row(i, arm_link=None):
        return dict(id="A_" + arm_link if arm_link else "BODY", arm_link=arm_link,
                    configuration="service", product_role="ONBOARD_CANDIDATE",
                    representation_role="PHYSICAL_GEOMETRY", mass_owner="OWNER_" + str(i),
                    mass_source="UNKNOWN" if arm_link else "CAD_ESTIMATE",
                    mass_kg=None if arm_link else 1.0, source_revision="INDEPENDENT_FIXTURE",
                    shape_valid=False if arm_link else True, solid_count=1,
                    center_of_mass_S_mm=[i + .5, .5, .5], inertia_about_COM_S_kg_mm2=None,
                    volume_mm3=1.0, T_S_local=copy.deepcopy(matrix),
                    bounds=dict(min_mm=[i, 0, 0], max_mm=[i+1, 1, 1], size_mm=[1, 1, 1]))
    arms = [row(i + 2, n) for i, n in enumerate(names)]
    body = row(0)
    base = dict(configuration="INDEPENDENT_COMPOSITE", state="service", view="complete",
                q_deg=[0, -80, -70, 30, 0, 0], finger_mm=15, T_S_arm_base=matrix,
                link_transforms={n: copy.deepcopy(matrix) for n in names})
    old = dict(copy.deepcopy(base), source_sha256=sha(oldhome / "spacecraft_model.py"),
               dependency_sha256={n: sha(oldhome / n) for n in deps}, instances=copy.deepcopy(arms),
               interfaces=[dict(instance=r["id"]) for r in arms])
    fresh = dict(copy.deepcopy(base), source_sha256=sha(here / "spacecraft_model.py"),
                 dependency_sha256={n: sha(here / n) for n in deps}, instances=[body],
                 interfaces=[dict(instance="BODY")])
    op = oldhome / "results/service_instances.json"
    fp = here / "results/service_structure_instances.json"
    ip = here / "results/service_COMPOSITE_ASSEMBLY_INDEX.json"
    write(op, old)
    write(fp, fresh)
    step = here / "servicer_structure_service.step"
    step.write_bytes(b"SYNTHETIC_NONARM_GEOMETRY_IDENTITY_ONLY")
    sources = {}
    for name in names:
        path = oldhome / "inputs" / (name + ".step")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(("SYNTHETIC_ARM_GEOMETRY_IDENTITY_" + name).encode())
        sources[name] = ref(path)
    mp = root / "inputs/INPUT_MANIFEST.json"
    write(mp, dict(source_snapshot=[dict(path=str(op.resolve()), sha256=sha(op))]))
    ep = root / "inputs/ARM_REUSE_INPUT_EXTENSION.json"
    write(ep, dict(initial_manifest_sha256=sha(mp), source_sha256={r["path"]: r["sha256"] for r in sources.values()}))
    d = copy.deepcopy(fresh)
    for arm in arms:
        arm["geometry_reuse"] = copy.deepcopy(sources[arm["arm_link"]])
    d["instances"] += arms
    d["interfaces"] += copy.deepcopy(old["interfaces"])
    d["bounds"] = dict(min_mm=[0, 0, 0], max_mm=[12, 1, 1], size_mm=[12, 1, 1])
    d["composition_mode"] = "FRESH_NONARM_PLUS_HASH_LOCKED_UNCHANGED_ARM"
    d["monolithic_complete_step_generated"] = False
    # A complete binding includes the original receipt as well as local shapes.
    d["geometry_sha256"] = {str(step.resolve()): sha(step), str(op.resolve()): sha(op), **{r["path"]: r["sha256"] for r in sources.values()}}
    index = dict(configuration=d["configuration"], state="service", composition_mode=d["composition_mode"],
                 nonarm_step=ref(step), nonarm_instance_ids=["BODY"],
                 arm_occurrences=[dict(id=r["id"], arm_link=r["arm_link"], geometry=copy.deepcopy(sources[r["arm_link"]]), T_S_local=copy.deepcopy(r["T_S_local"])) for r in arms])
    write(ip, index)
    d["composition"] = dict(builder=ref(here / "compose_receipts.py"), input_extension=ref(ep),
                            original_receipt=ref(op), fresh_nonarm_receipt=ref(fp),
                            fresh_nonarm_step=ref(step), arm_sources=copy.deepcopy(sources), assembly_index=ref(ip))
    d["dependency_sha256"].update({n: sha(here / n) for n in ("compose_receipts.py", "composition_binding.py", "provenance_binding.py")})
    return dict(here=here, oldhome=oldhome, old=old, fresh=fresh, d=d, index=index, op=op, fp=fp, ip=ip, ep=ep)

def run_case(name, mutator, expected):
    with tempfile.TemporaryDirectory(prefix="composition_fixture_", dir=RUN / "review") as directory:
        x = fixture(Path(directory))
        if mutator:
            mutator(x)
        write(x["fp"], x["fresh"])
        write(x["ip"], x["index"])
        if "composition" in x["d"]:
            x["d"]["composition"]["fresh_nonarm_receipt"] = ref(x["fp"])
            x["d"]["composition"]["assembly_index"] = ref(x["ip"])
        try:
            VALIDATE(x["d"], x["here"])
            accepted = True
            error = None
        except (ValueError, KeyError, FileNotFoundError, TypeError) as exc:
            accepted = False
            error = type(exc).__name__ + ": " + str(exc)
        RESULTS.append(dict(case=name, expected_accept=expected, accepted=accepted, passed=accepted == expected, rejection=error))

def strip_mode_and_rows(x):
    x["d"].pop("composition_mode")
    for row in x["d"]["instances"]:
        row.pop("geometry_reuse", None)

def add_duplicate_arm(x):
    row = copy.deepcopy(x["d"]["instances"][1])
    row["id"] = "DUPLICATED_ARM_FAKE_ID"
    row["mass_owner"] = "DUPLICATED_ARM_FAKE_OWNER"
    x["d"]["instances"].insert(1, row)
    x["d"]["interfaces"].append(dict(instance=row["id"]))

def main():
    global VALIDATE
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RUN / "review/COMPOSITION_CONTROLS.json")
    args = parser.parse_args()
    sys.path.insert(0, str(CANDIDATE))
    import provenance_binding
    VALIDATE = provenance_binding.validate_receipt_source
    paths = [Path(__file__).resolve(), CANDIDATE / "composition_binding.py", CANDIDATE / "provenance_binding.py", CANDIDATE / "compose_receipts.py", CANDIDATE / "prepare_arm_extension.py"]
    before = {str(p): sha(p) for p in paths}
    run_case("valid_independent_ten_arm_composite", None, True)
    cases = {
        "old_model_drift": lambda x: (x["oldhome"] / "spacecraft_model.py").write_text("DRIFT"),
        "old_dependency_drift": lambda x: (x["oldhome"] / "root_structure.py").write_text("DRIFT"),
        "missing_arm_mapping": lambda x: x["d"]["composition"]["arm_sources"].pop("link2"),
        "missing_arm_geometry_hash": lambda x: x["d"]["geometry_sha256"].pop(x["d"]["composition"]["arm_sources"]["link2"]["path"]),
        "missing_original_receipt_geometry_hash": lambda x: x["d"]["geometry_sha256"].pop(str(x["op"].resolve())),
        "altered_reused_COM": lambda x: x["d"]["instances"][1]["center_of_mass_S_mm"].__setitem__(0, 1234),
        "promoted_invalid_shape": lambda x: x["d"]["instances"][1].__setitem__("shape_valid", True),
        "pose_drift": lambda x: x["d"].__setitem__("finger_mm", 0),
        "missing_interface": lambda x: x["d"]["interfaces"].pop(),
        "duplicate_interface": lambda x: x["d"]["interfaces"].append(copy.deepcopy(x["d"]["interfaces"][0])),
        "missing_nonarm_index_ID": lambda x: x["index"].__setitem__("nonarm_instance_ids", []),
        "duplicate_index_arm": lambda x: x["index"]["arm_occurrences"].append(copy.deepcopy(x["index"]["arm_occurrences"][0])),
        "index_transform_drift": lambda x: x["index"]["arm_occurrences"][0]["T_S_local"][0].__setitem__(3, 999),
        "extra_duplicate_arm_link_hidden_by_dict": add_duplicate_arm,
        "incorrect_complete_bounds": lambda x: x["d"]["bounds"]["max_mm"].__setitem__(0, 1),
        "strip_mode_and_row_lineage_bypass": strip_mode_and_rows,
        "fresh_dependency_not_equal_to_composite": lambda x: x["fresh"]["dependency_sha256"].__setitem__("root_structure.py", "0" * 64),
        "false_monolithic_step_claim": lambda x: x["d"].__setitem__("monolithic_complete_step_generated", True),
    }
    for name, mutation in cases.items():
        run_case(name, mutation, False)
    after = {str(p): sha(p) for p in paths}
    result = dict(schema="WP03_INDEPENDENT_COMPOSITION_PROTOCOL_CONTROLS_V1", geometry_executed=False,
                  scope="Actual candidate validator with synthetic stdlib file fixtures; no CAD or source asset modifications",
                  cases=RESULTS, all_passed=all(r["passed"] for r in RESULTS) and before == after,
                  source_sha256_before=before, source_sha256_after=after, source_unchanged=before == after)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(cases=len(RESULTS), all_passed=result["all_passed"], failed=[r["case"] for r in RESULTS if not r["passed"]], output=str(args.output))))
    raise SystemExit(0 if result["all_passed"] else 1)

if __name__ == "__main__":
    main()
