"""Independent candidate protocol controls; stdlib only, no CAD or VTK.

The records created here are synthetic software probes. Passing these controls
does not certify geometry, continuous motion, strength, flight readiness, or an
existing project Gate. Source and output hashes distinguish this run from older
isolated-prototype tests.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import csv
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from types import SimpleNamespace

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parents[1]
CANDIDATE = RUN / "candidate"
CASES = []
FORBIDDEN_IMPORT_ATTEMPTS = []


class RejectHeavyImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"spacecraft_model", "vtk", "OCP", "OCC", "cadquery", "build123d", "numpy", "scipy"}:
            FORBIDDEN_IMPORT_ATTEMPTS.append(fullname)
            raise ImportError("Independent stdlib test forbids heavy import: " + fullname)
        return None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(name, action, expected, scope="synthetic_protocol"):
    try:
        actual = action()
        passed = actual == expected
        CASES.append(dict(case=name, scope=scope, expected=expected, actual=actual, passed=passed))
    except Exception as exc:
        CASES.append(dict(case=name, scope=scope, expected=expected, actual=None,
                          passed=False, error=f"{type(exc).__name__}: {exc}",
                          traceback=traceback.format_exc(limit=3)))


def strict_fixture():
    # Independently construct a ten-link tree with two fingers. Do not consume
    # expected rows or PASS flags from the earlier prototype result JSON.
    chain = ["base_link", *[f"link{i}" for i in range(1, 7)], "gripper_link"]
    names = [*chain, "gripper_left", "gripper_right"]
    adjacent = {frozenset(p) for p in zip(chain[:-1], chain[1:])}
    adjacent |= {frozenset(("gripper_link", f)) for f in names[-2:]}
    pairs = [list(p) for p in itertools.combinations(names, 2) if frozenset(p) not in adjacent]
    assert len(pairs) == 36
    snapshot = {"independent_fixture.urdf": hashlib.sha256(b"independent source A").hexdigest(),
                "independent_parameters.json": hashlib.sha256(b"independent source B").hexdigest()}
    config = dict(pose_id="INDEPENDENT_CONTROL", q_deg=[0, -30, -60, 40, 0, 0],
                  finger_mm=15, root_transform_mm=[90, 0, 125.15])
    contract = dict(run_id="INDEPENDENT_CANDIDATE_PROTOCOL_TEST", configuration=config,
                    input_sha256=snapshot, expected_nonadjacent_pairs=pairs,
                    explicit_unknown_pairs=[["gripper_left", "gripper_right"]])
    identity = dict(run_id=contract["run_id"], pose_id=config["pose_id"],
                    snapshot_digest=canonical_sha(snapshot))
    rows = []
    for pair in pairs:
        unknown = set(pair) == {"gripper_left", "gripper_right"}
        rows.append(dict(identity, links=pair, surface_intersection=None if unknown else False,
                         unknown_reason="FINGER_SOURCE_PAIR_NOT_EVALUATED" if unknown else None))
    evidence = dict(run_id=contract["run_id"], configuration=copy.deepcopy(config),
                    input_sha256_before=copy.deepcopy(snapshot), input_sha256_after=copy.deepcopy(snapshot),
                    worker_returncode=0, worker_error=None, timed_out=False,
                    completion=dict(identity, completed=True, expected_pair_count=36), records=rows)
    return contract, evidence


def strict_controls(module, aggregate=None, prefix="aggregator"):
    aggregate = aggregate or module.aggregate
    success = "DECLARED_NONADJACENT_BODY_PAIR_SURFACES_DISJOINT_ONLY"
    invalid = "INCOMPLETE_OR_INVALID_EVIDENCE"

    def evaluate(mutator=None):
        contract, evidence = strict_fixture()
        if mutator:
            mutator(contract, evidence)
        result = aggregate(contract, evidence)
        if result.get("full_geometry_pass") is not None or result.get("geometry_executed") is not False:
            raise AssertionError("Software aggregation must not claim geometry execution or full PASS")
        return result["status"]

    record(prefix + ":valid_bounded_surface_record", evaluate, success)
    record(prefix + ":order_invariance", lambda: evaluate(lambda c, e: e["records"].reverse()), success)
    record(prefix + ":pair_orientation_invariance", lambda: evaluate(lambda c, e: [r["links"].reverse() for r in e["records"]]), success)
    edits = {
        "duplicate_pair_same_count": lambda c, e: e["records"].__setitem__(1, copy.deepcopy(e["records"][0])),
        "missing_pair": lambda c, e: e["records"].pop(1),
        "wrong_pair_identity": lambda c, e: e["records"][0].__setitem__("links", ["fake_link", "link3"]),
        "malformed_self_pair": lambda c, e: e["records"][0].__setitem__("links", ["link1", "link1"]),
        "missing_boolean": lambda c, e: e["records"][0].__setitem__("surface_intersection", None),
        "integer_not_boolean": lambda c, e: e["records"][0].__setitem__("surface_intersection", 0),
        "worker_nonzero": lambda c, e: e.__setitem__("worker_returncode", 2),
        "worker_false_not_zero": lambda c, e: e.__setitem__("worker_returncode", False),
        "worker_return_missing": lambda c, e: e.pop("worker_returncode"),
        "worker_error": lambda c, e: e.__setitem__("worker_error", "independent fault"),
        "worker_timeout": lambda c, e: e.__setitem__("timed_out", True),
        "worker_timeout_unknown": lambda c, e: e.__setitem__("timed_out", None),
        "missing_completion": lambda c, e: e.pop("completion"),
        "completion_false": lambda c, e: e["completion"].__setitem__("completed", False),
        "completion_wrong_run": lambda c, e: e["completion"].__setitem__("run_id", "OTHER_RUN"),
        "completion_wrong_pose": lambda c, e: e["completion"].__setitem__("pose_id", "OTHER_POSE"),
        "completion_wrong_count": lambda c, e: e["completion"].__setitem__("expected_pair_count", 35),
        "wrong_run": lambda c, e: e.__setitem__("run_id", "OTHER_RUN"),
        "wrong_configuration": lambda c, e: e["configuration"].__setitem__("finger_mm", 0),
        "old_before_hash": lambda c, e: e["input_sha256_before"].__setitem__("independent_fixture.urdf", "0" * 64),
        "changed_after_hash": lambda c, e: e["input_sha256_after"].__setitem__("independent_fixture.urdf", "1" * 64),
        "missing_after_hash": lambda c, e: e.pop("input_sha256_after"),
        "row_other_run": lambda c, e: e["records"][0].__setitem__("run_id", "OTHER_RUN"),
        "row_other_snapshot": lambda c, e: e["records"][0].__setitem__("snapshot_digest", "f" * 64),
        "unknown_finger_promoted": lambda c, e: next(r for r in e["records"] if r["surface_intersection"] is None).__setitem__("surface_intersection", False),
        "unknown_finger_no_reason": lambda c, e: next(r for r in e["records"] if r["surface_intersection"] is None).__setitem__("unknown_reason", None),
        "duplicate_expected_pair": lambda c, e: c["expected_nonadjacent_pairs"].append(copy.deepcopy(c["expected_nonadjacent_pairs"][0])),
        "empty_source_contract": lambda c, e: c.__setitem__("input_sha256", {}),
    }
    for name, mutator in edits.items():
        record(prefix + ":" + name, lambda f=mutator: evaluate(f), invalid)
    record(prefix + ":positive_surface_hit_retained", lambda: evaluate(lambda c, e: e["records"][0].__setitem__("surface_intersection", True)), "SCOPED_SURFACE_INTERSECTION_RECORDED")


def pose_entry_controls(candidate, strict):
    path = candidate / "pose_screen.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    helper = functions.get("classify_self_surface")
    record("pose_entry:classify_helper_exists", lambda: helper is not None, True, "actual_source_binding")
    main_calls = [n for n in ast.walk(functions["main"]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    record("pose_entry:main_calls_classify_helper", lambda: any(n.func.id == "classify_self_surface" for n in main_calls), True, "actual_source_binding")
    if helper is None:
        return
    # Compile only this actual production helper. Importing pose_screen itself
    # would load geometry dependencies and is intentionally outside this run.
    namespace = {"aggregate": strict.aggregate, "strict_aggregate": strict.aggregate,
                 "strict_surface_aggregator": strict, "require_physical_view": strict.require_physical_view}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(path), "exec"), namespace)
    strict_controls(strict, namespace["classify_self_surface"], prefix="actual_pose_classify_helper")


def parent_main_protocol_controls(candidate, strict):
    """Exercise the actual parent parser/main with a mocked subprocess only.

    No worker, VTK import, mesh or geometry job is started. The mock emits the
    documented worker's pair/complete wire format using independent records.
    Input reading is stubbed here; actual hash and CSV handling is tested by
    exporter_controls separately.
    """
    path = candidate / "pose_screen.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    nodes = [functions[name] for name in ("classify_self_surface", "main")]

    def execute(mode):
        contract, evidence = strict_fixture()
        events = [dict(event="pair", record=row) for row in evidence["records"]]
        complete = dict(event="complete", completion=evidence["completion"], input_sha256_after=evidence["input_sha256_after"], vtk_version="MOCK_NO_VTK")
        events.append(complete)
        code = 0
        stderr = ""
        if mode == "duplicate_completion":
            events.append(copy.deepcopy(complete))
        elif mode == "missing_completion":
            events.pop()
        elif mode == "json_null":
            events = [None]
        elif mode == "json_list":
            events = [["malformed event"]]
        elif mode == "unknown_event":
            events = [dict(event="wrong")]
        elif mode in ("empty_worker_failure", "timeout_before_geometry"):
            events = []
            code = 1
            stderr = "MOCK_IMPORT_FAILED_BEFORE_GEOMETRY"
        stdout = "\n".join(json.dumps(e) for e in events) + "\n"
        def fake_run(command, **kwargs):
            if mode == "timeout_before_geometry":
                raise subprocess.TimeoutExpired(command, 1, output=b"", stderr=b"MOCK_TIMEOUT")
            return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)
        with tempfile.TemporaryDirectory(prefix="parent_protocol_", dir=RUN / "review") as temp:
            here = Path(temp)
            (here / "results").mkdir()
            namespace = dict(__file__=str(path), Path=Path, argparse=argparse, json=json, sys=sys,
                             aggregate=strict.aggregate, HERE=here, RUN_ID=contract["run_id"], STATES=("service",),
                             input_snapshot=lambda: copy.deepcopy(contract["input_sha256"]),
                             make_contract=lambda state, hashes: copy.deepcopy(contract),
                             verify_hashes=lambda hashes: None,
                             subprocess=SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired))
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
            with contextlib.redirect_stdout(io.StringIO()):
                namespace["main"]([])
            result = json.loads((here / "results/POSE_SCREEN.json").read_text(encoding="utf-8"))
            pose = result["poses"][0]
            return dict(status=pose["classification"]["status"], geometry_executed=pose["evidence"]["geometry_executed"])
    success = "DECLARED_NONADJACENT_BODY_PAIR_SURFACES_DISJOINT_ONLY"
    invalid = "INCOMPLETE_OR_INVALID_EVIDENCE"
    record("actual_parent_main_mock_worker:wire_format_valid", lambda: execute("valid"), dict(status=success, geometry_executed=True), "actual_main_mock_worker_no_geometry")
    for mode in ("duplicate_completion", "missing_completion"):
        record("actual_parent_main_mock_worker:" + mode, lambda m=mode: execute(m), dict(status=invalid, geometry_executed=True), "actual_main_mock_worker_no_geometry")
    for mode in ("json_null", "json_list", "unknown_event", "empty_worker_failure", "timeout_before_geometry"):
        record("actual_parent_main_mock_worker:" + mode, lambda m=mode: execute(m), dict(status=invalid, geometry_executed=False), "actual_main_mock_worker_no_geometry")


def view_controls(strict):
    def allowed(receipt):
        try:
            strict.require_physical_view(receipt)
            return True
        except ValueError:
            return False
    for state in ("parking", "released", "service"):
        record("view:" + state + "_complete", lambda s=state: allowed(dict(state=s, view="complete")), True)
    for view in ("exploded", "cutaway", "module", None):
        record("view:reject_" + str(view), lambda v=view: allowed(dict(state="service", view=v)), False)
    record("view:reject_unknown_state", lambda: allowed(dict(state="other", view="complete")), False)
    record("view:reject_missing_state", lambda: allowed(dict(view="complete")), False)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False), encoding="utf-8")


def receipt_identity(receipt):
    keys = ("id", "mass_owner", "product_role", "representation_role", "mass_source", "mass_kg", "arm_link")
    rows = [{key: row.get(key) for key in keys} for row in sorted(receipt["instances"], key=lambda r: r["id"])]
    return canonical_sha(rows)


def exporter_fixture(here, exporter):
    for name in ("spacecraft_model.py", "design_parameters.json", "root_structure.py", "wing_kinematics.py", "kinematics.py", "dynamics_handoff.py", "project_paths.py", "r01_design.py", "candidate_context.py", "provenance_binding.py"):
        (here / name).write_text("independent fixture file: " + name, encoding="utf-8")
    (here / "parts").mkdir()
    geometry_path = here / "independent_final_geometry.step"
    geometry_path.write_bytes(b"SYNTHETIC_GEOMETRY_IDENTITY_ONLY_NOT_CAD")
    known = dict(id="INDEPENDENT_PART", pn="P-TEST", configuration="service", mass_owner="OWNER_A",
                 product_role="ONBOARD_CANDIDATE", representation_role="PHYSICAL_GEOMETRY",
                 mass_source="CAD_ESTIMATE", mass_kg=1.25, arm_link=None, source_revision="TEST_R1",
                 parent_assembly="TEST_STRUCTURE", mount_interface="TEST_MOUNT", mass_basis="SYNTHETIC_CONTROL")
    unknown = dict(known, id="INDEPENDENT_UNKNOWN", pn="U-TEST", mass_owner="OWNER_UNKNOWN",
                   representation_role="FUNCTIONAL_ENVELOPE", mass_source="UNKNOWN", mass_kg=None)
    matrix = [[1., 0., 0., 90.], [0., 1., 0., 0.], [0., 0., 1., 125.15], [0., 0., 0., 1.]]
    receipt = dict(configuration="WP03_SERVICER_ONBOARD_R1", state="service", view="complete",
                   q_deg=[0, -80, -70, 30, 0, 0], finger_mm=15, T_S_arm_base=matrix,
                   source_sha256=sha(here / "spacecraft_model.py"),
                   dependency_sha256={name: sha(here / name) for name in ("design_parameters.json", "root_structure.py", "wing_kinematics.py", "kinematics.py", "r01_design.py", "candidate_context.py")},
                   geometry_sha256={str(geometry_path.resolve()): sha(geometry_path)},
                   instances=[known, unknown], interfaces=[dict(id="TEST_INTERFACE", status="SYNTHETIC_ONLY")])
    group = dict(instance_count=2, known_mass_kg=1.25, mass_atoms=[copy.deepcopy(known)],
                 unknown_mass_instances=[dict(unknown, reason="MASS_UNKNOWN_NOT_ZERO")], known_mass_missing_properties=[])
    state = dict(state="service", q_deg=receipt["q_deg"], finger_mm=15, T_S_arm_base_mm=matrix,
                 groups={"ONBOARD_CANDIDATE": group}, mass_owner_values={"OWNER_A": 1.25},
                 mass_owner_values_by_role={"ONBOARD_CANDIDATE": {"OWNER_A": 1.25}})
    handoff = dict(schema="WP03_DYNAMICS_HANDOFF_V1", source_files_unchanged=True, states=[state],
                   receipt_model_source_checks=[], receipt_bindings={}, input_sha256={})
    for label in ("parking", "released", "service"):
        item = copy.deepcopy(receipt)
        item["state"] = label
        for row in item["instances"]:
            row["configuration"] = label
        path = here / "results" / (label + "_instances.json")
        write_json(path, item)
        handoff["input_sha256"][str(path.resolve())] = sha(path)
        handoff["receipt_model_source_checks"].append(dict(receipt=str(path.resolve()), recorded_model_sha256=item["source_sha256"], matches_current_model_source=True))
        handoff["receipt_bindings"][label] = dict(configuration=item["configuration"], view=item["view"],
                receipt_path=str(path.resolve()), receipt_sha256=sha(path), instance_identity_sha256=receipt_identity(item))
    for path in here.iterdir():
        if path.is_file():
            handoff["input_sha256"][str(path.resolve())] = sha(path)
    # External immutable source paths remain readable, but are not copied or
    # changed by these fixtures. The required set is adjusted to the published
    # candidate API, not inferred from old validation PASS records.
    for value in vars(exporter).values():
        if isinstance(value, Path) and value.is_file():
            handoff["input_sha256"][str(value.resolve())] = sha(value)
    project = next(p for p in RUN.parents if (p / "PROJECT_MAP.md").is_file())
    for rel in ("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
                "20_engineering/service_robot_wp01_20260905/kinematics.py"):
        path = project / rel
        handoff["input_sha256"][str(path.resolve())] = sha(path)
    return receipt, handoff


def persist_export_fixture(here, receipt, handoff, refresh=True):
    path = here / "results/service_instances.json"
    write_json(path, receipt)
    if refresh:
        handoff["input_sha256"][str(path.resolve())] = sha(path)
        if "service" in handoff["receipt_bindings"]:
            handoff["receipt_bindings"]["service"]["receipt_sha256"] = sha(path)
            handoff["receipt_bindings"]["service"]["instance_identity_sha256"] = receipt_identity(receipt)
    write_json(here / "results/DYNAMICS_HANDOFF.json", handoff)


def exporter_controls(candidate):
    exporter = load_module("independent_candidate_exporter", candidate / "export_parts_and_bom.py")
    original_here = exporter.HERE

    def exercise(mutator=None, reject=False, refresh=True, no_handoff=False):
        with tempfile.TemporaryDirectory(prefix="protocol_fixture_", dir=RUN / "review") as temp:
            here = Path(temp).resolve()
            assert here.is_relative_to((RUN / "review").resolve())
            receipt, handoff = exporter_fixture(here, exporter)
            if mutator:
                mutator(receipt, handoff, here)
            persist_export_fixture(here, receipt, handoff, refresh=refresh)
            if no_handoff:
                (here / "results/DYNAMICS_HANDOFF.json").unlink()
            marker = b"INDEPENDENT_PRIOR_BOM_MUST_SURVIVE_FAILURE\n"
            (here / "BOM.csv").write_bytes(marker)
            (here / "INTERFACES.csv").write_bytes(marker)
            exporter.HERE = here
            raised = None
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    exporter.main(["--bom-only"])
            except (ValueError, RuntimeError, KeyError, FileNotFoundError) as exc:
                raised = f"{type(exc).__name__}: {exc}"
            finally:
                exporter.HERE = original_here
            if reject:
                if raised is None:
                    return {"rejected": False, "prior_outputs_unchanged": False}
                return {"rejected": True, "prior_outputs_unchanged": all((here / name).read_bytes() == marker for name in ("BOM.csv", "INTERFACES.csv"))}
            if raised:
                raise AssertionError("Valid independent fixture rejected: " + raised)
            rows = list(csv.DictReader(io.StringIO((here / "BOM.csv").read_text(encoding="utf-8-sig"))))
            by_id = {r["id"]: r for r in rows}
            return {"rows": len(rows), "known": by_id["INDEPENDENT_PART"]["allocated_dynamics_mass_kg"],
                    "unknown": by_id["INDEPENDENT_UNKNOWN"]["allocated_dynamics_mass_kg"]}

    record("export_main:valid_fixture_known_and_unknown", exercise, {"rows": 2, "known": "1.25", "unknown": ""}, "actual_main_synthetic_fixture")
    expected = {"rejected": True, "prior_outputs_unchanged": True}
    # The owner selected a final-BOM-only command for this bounded run:
    # HANDOFF must precede final BOM. Earlier exploratory results are retained;
    # this test records that explicit policy rather than requesting a separate
    # unallocated/initial BOM feature in the production final export entry.
    record("export_main:final_bom_missing_handoff_rejected", lambda: exercise(no_handoff=True, reject=True), expected, "actual_main_synthetic_fixture")
    mutations = {
        "same_total_stale_receipt": (lambda r, d, h: r["instances"][0].__setitem__("pn", "SAME_MASS_DIFFERENT_SOURCE"), False),
        "wrong_source_hash": (lambda r, d, h: r.__setitem__("source_sha256", "0" * 64), True),
        "missing_required_input_hash": (lambda r, d, h: d["input_sha256"].pop(str((h / "results/parking_instances.json").resolve())), True),
        "wrong_dependency_hash": (lambda r, d, h: r["dependency_sha256"].__setitem__("root_structure.py", "1" * 64), True),
        "wrong_owner_with_refreshed_receipt_hash": (lambda r, d, h: r["instances"][0].__setitem__("mass_owner", "OTHER_OWNER"), True),
        "missing_owner_with_refreshed_receipt_hash": (lambda r, d, h: r["instances"][0].pop("mass_owner"), True),
        "duplicate_owner_with_refreshed_receipt_hash": (lambda r, d, h: r["instances"][1].__setitem__("mass_owner", "OWNER_A"), True),
        "known_owner_deleted_from_handoff": (lambda r, d, h: d["states"][0]["mass_owner_values"].pop("OWNER_A"), True),
        "duplicate_mass_atom_hidden_by_dictionary": (lambda r, d, h: d["states"][0]["groups"]["ONBOARD_CANDIDATE"]["mass_atoms"].append(copy.deepcopy(d["states"][0]["groups"]["ONBOARD_CANDIDATE"]["mass_atoms"][0])), True),
        "unknown_coverage_deleted": (lambda r, d, h: d["states"][0]["groups"]["ONBOARD_CANDIDATE"].__setitem__("unknown_mass_instances", []), True),
        "unknown_owner_mismatch": (lambda r, d, h: d["states"][0]["groups"]["ONBOARD_CANDIDATE"]["unknown_mass_instances"][0].__setitem__("mass_owner", "OTHER_UNKNOWN_OWNER"), True),
        "role_specific_mass_mapping_mismatch": (lambda r, d, h: d["states"][0].__setitem__("mass_owner_values_by_role", {"ONBOARD_CANDIDATE": {}, "GSE": {"OWNER_A": 1.25}}), True),
        "mass_atom_source_revision_mismatch": (lambda r, d, h: d["states"][0]["groups"]["ONBOARD_CANDIDATE"]["mass_atoms"][0].__setitem__("source_revision", "OTHER_SOURCE_REVISION"), True),
        "unknown_silently_zero_filled": (lambda r, d, h: d["states"][0]["mass_owner_values"].__setitem__("OWNER_UNKNOWN", 0.0), True),
        "unknown_receipt_changed_to_zero": (lambda r, d, h: r["instances"][1].__setitem__("mass_kg", 0.0), True),
        "gse_role_in_onboard_receipt": (lambda r, d, h: r["instances"][0].__setitem__("product_role", "GSE"), True),
        "wrong_row_configuration": (lambda r, d, h: r["instances"][0].__setitem__("configuration", "parking"), True),
        "exploded_view": (lambda r, d, h: r.__setitem__("view", "exploded"), True),
        "wrong_state": (lambda r, d, h: r.__setitem__("state", "parking"), True),
        "duplicate_service_state": (lambda r, d, h: d["states"].append(copy.deepcopy(d["states"][0])), True),
        "wrong_q_binding": (lambda r, d, h: d["states"][0].__setitem__("q_deg", [0] * 6), True),
        "missing_receipt_binding": (lambda r, d, h: d["receipt_bindings"].pop("service"), True),
        "source_changed_during_handoff": (lambda r, d, h: d.__setitem__("source_files_unchanged", False), True),
    }
    for name, (mutator, refresh) in mutations.items():
        record("export_main:" + name, lambda f=mutator, u=refresh: exercise(f, reject=True, refresh=u), expected, "actual_main_synthetic_fixture")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    parser.add_argument("--output", type=Path, default=RUN / "review/PROVENANCE_PROTOCOL_CONTROLS.json")
    parser.add_argument("--exporter-only", action="store_true")
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    sys.path.insert(0, str(candidate))
    sys.meta_path.insert(0, RejectHeavyImports())
    source_paths = [Path(__file__).resolve(), candidate / "export_parts_and_bom.py", candidate / "provenance_binding.py", candidate / "candidate_context.py"]
    if not args.exporter_only:
        source_paths += [candidate / "strict_surface_aggregator.py", candidate / "pose_screen.py"]
    before = {str(p): sha(p) for p in source_paths}
    if not args.exporter_only:
        strict = load_module("independent_candidate_strict", candidate / "strict_surface_aggregator.py")
        strict_controls(strict)
        view_controls(strict)
        pose_entry_controls(candidate, strict)
        parent_main_protocol_controls(candidate, strict)
    exporter_controls(candidate)
    record("stdlib_only:no_forbidden_import", lambda: FORBIDDEN_IMPORT_ATTEMPTS, [], "actual_import_guard")
    after = {str(p): sha(p) for p in source_paths}
    record("candidate_sources:unchanged_during_tests", lambda: before == after, True, "actual_source_hash_check")
    result = dict(schema="WP03_INDEPENDENT_CANDIDATE_PROTOCOL_CONTROLS_V1",
                  scope="Actual candidate software functions with independent synthetic records; no geometry or hardware validation",
                  candidate=str(candidate), geometry_executed=False, hardware_verified=False,
                  executed_subset="exporter_only" if args.exporter_only else "exporter_aggregator_and_actual_pose_helper",
                  final_bom_policy="HANDOFF_REQUIRED; missing handoff must reject before altering existing output. Unallocated initial BOM is outside this final export entry.",
                  historical_gate_changed=False, cases=CASES, case_count=len(CASES),
                  all_passed=all(c["passed"] for c in CASES),
                  source_sha256_before=before, source_sha256_after=after,
                  source_sha256=after)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"case_count": result["case_count"], "all_passed": result["all_passed"],
                      "failed": [c["case"] for c in CASES if not c["passed"]], "output": str(args.output)}, ensure_ascii=False))
    raise SystemExit(0 if result["all_passed"] else 1)


if __name__ == "__main__":
    main()
