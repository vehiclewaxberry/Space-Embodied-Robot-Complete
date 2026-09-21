"""Read-only independent audit of WP05 source/import/cold-open receipts.

No COM, CAD runtime, or source mutation. Evidence that a producer did not record
is INCOMPLETE, never a fabricated successful check. The CLI prints JSON to stdout;
the caller owns saving that result. Only explicit field maps adapt cold receipts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

STATES = ("service", "parking", "released")
CLAIM_KEYS = {
    "all_mechanical_design_complete", "full_mechanical_design_complete",
    "manufacturing_release", "flight_qualified", "hardware_qualified",
    "physical_assembly_completed", "continuous_motion_verified",
    "full_assembly_collision_free", "all_interferences_cleared",
    "full_digital_assembly_collision_pass", "hardware_command_authorized",
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def norm(path):
    return str(Path(path).resolve()).replace("\\", "/").casefold()


class Audit:
    def __init__(self):
        self.checks = []

    def add(self, name, result, *, required=True, **detail):
        status = "INCOMPLETE" if result is None else "PASS" if result else "FAIL"
        self.checks.append(dict(check=name, status=status, required=required, **detail))
        return result is True

    def missing(self, name, detail):
        return self.add(name, None, reason=detail)

    def summary(self):
        counts = dict(Counter(r["status"] for r in self.checks if r["required"]))
        diagnostics = dict(Counter(r["status"] for r in self.checks if not r["required"]))
        status = "FAIL" if counts.get("FAIL") else "INCOMPLETE" if counts.get("INCOMPLETE") else "PASS_RECORDED_NATIVE_DELIVERY_EVIDENCE_ONLY"
        return dict(status=status, counts=counts, diagnostic_counts=diagnostics, checks=self.checks)


def check_file(audit, name, path, expected_sha=None, package_root=None, suffix=None):
    if not isinstance(path, (str, Path)) or not str(path):
        audit.missing(name, "No explicit file path")
        return None
    p = Path(path).resolve()
    if package_root is not None and not p.is_relative_to(Path(package_root).resolve()):
        audit.add(name, False, path=str(p), reason="Dependency escapes the delivery package")
        return None
    if not p.is_file():
        audit.add(name, False, path=str(p), reason="File is absent")
        return None
    if suffix and p.suffix.lower() != suffix.lower():
        audit.add(name, False, path=str(p), reason="File extension differs from contract")
        return None
    digest = sha256(p)
    if expected_sha is None:
        audit.missing(name + ":hash_binding", "Expected SHA-256 was not recorded")
    else:
        audit.add(name + ":hash_binding", digest.lower() == str(expected_sha).lower(),
                  path=str(p), actual_sha256=digest, expected_sha256=expected_sha)
    return dict(path=str(p), sha256=digest, bytes=p.stat().st_size)


def matrix4(value, encoding):
    """Return column-vector T in mm; reject malformed/nonrigid matrices."""
    if encoding == "sw16_m_column_rotation":
        if not isinstance(value, list) or len(value) != 16:
            raise ValueError("SW transform must contain exactly 16 entries")
        v = [float(x) for x in value]
        if abs(v[12] - 1) > 1e-10 or max(abs(x) for x in v[13:]) > 1e-10:
            raise ValueError("SW scale/reserved entries do not match [1,0,0,0]")
        t = [[v[i], v[i + 3], v[i + 6], v[i + 9] * 1000] for i in range(3)] + [[0., 0., 0., 1.]]
    elif encoding == "matrix4_mm":
        if not isinstance(value, list) or len(value) != 4 or any(not isinstance(r, list) or len(r) != 4 for r in value):
            raise ValueError("Source transform must be 4 by 4")
        t = [[float(x) for x in row] for row in value]
    else:
        raise ValueError("Unsupported transform encoding: " + str(encoding))
    if not all(math.isfinite(x) for r in t for x in r):
        raise ValueError("Nonfinite transform")
    if max(abs(t[3][i] - (1 if i == 3 else 0)) for i in range(4)) > 1e-10:
        raise ValueError("Invalid homogeneous bottom row")
    if max(abs(sum(t[k][i] * t[k][j] for k in range(3)) - (1 if i == j else 0)) for i in range(3) for j in range(3)) > 1e-8:
        raise ValueError("Rotation is not orthonormal")
    det = (t[0][0]*(t[1][1]*t[2][2]-t[1][2]*t[2][1])
           - t[0][1]*(t[1][0]*t[2][2]-t[1][2]*t[2][0])
           + t[0][2]*(t[1][0]*t[2][1]-t[1][1]*t[2][0]))
    if abs(det - 1) > 1e-8:
        raise ValueError("Rotation includes a reflection")
    return t


def world_basis_error_mm(source_T_S_local, actual_world_points_mm):
    """Compare actual SW MathPoint transforms against frozen column-vector T.

    This deliberately does not decode native Transform2 or reuse the producer's
    reported error. The four fixed local points are expressed in millimetres.
    """
    t = matrix4(source_T_S_local, "matrix4_mm")
    if (not isinstance(actual_world_points_mm, list) or len(actual_world_points_mm) != 4
            or any(not isinstance(p, list) or len(p) != 3 for p in actual_world_points_mm)):
        raise ValueError("Actual world basis points must be a 4 by 3 array")
    if not all(type(x) in (int, float) and math.isfinite(x) for p in actual_world_points_mm for x in p):
        raise ValueError("Actual world basis coordinates must be finite numeric millimetres")
    local_points_mm = ((0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10))
    expected = [[sum(t[i][j] * point[j] for j in range(3)) + t[i][3]
                 for i in range(3)] for point in local_points_mm]
    error = max(abs(actual_world_points_mm[k][i] - expected[k][i])
                for k in range(4) for i in range(3))
    return error, expected


def check_state_rows(expected_rows, actual_rows, *, field_map=None,
                     transform_encoding="sw16_m_column_rotation", expected_count=585,
                     translation_tolerance_mm=1e-3, rotation_tolerance=1e-8,
                     audit=None, state="unspecified"):
    """Pure receipt comparison. Explicit map keys: id, part_key, transform, role,
    fixed, solid_count, world_basis. Missing native role/body/fixed/basis fields
    remain INCOMPLETE. World basis tolerance is fixed at 1e-5 mm independently
    of Transform2 entry tolerances.
    """
    a = audit if audit is not None else Audit()
    mapping = dict(id="id", part_key="part_key", transform="transform_sw16",
                   role="representation_role", fixed="fixed", solid_count="resolved_solid_count",
                   world_basis="world_basis_points_mm")
    mapping.update(field_map or {})
    prefix = "state:" + state
    if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
        a.missing(prefix + ":instances", "Expected and actual instance arrays must both exist")
        return a.summary()
    a.add(prefix + ":instance_count", len(expected_rows) == len(actual_rows) == expected_count,
          expected_source=len(expected_rows), actual=len(actual_rows), required=expected_count)
    ids = [r.get("id") for r in expected_rows]
    actual_ids = [r.get(mapping["id"]) for r in actual_rows]
    a.add(prefix + ":id_multiset", Counter(ids) == Counter(actual_ids) and None not in ids and None not in actual_ids)
    a.add(prefix + ":id_uniqueness", len(set(ids)) == len(ids) and len(set(actual_ids)) == len(actual_ids))
    by_id = {r.get(mapping["id"]): r for r in actual_rows}
    for expected in expected_rows:
        ident = expected.get("id")
        actual = by_id.get(ident)
        if actual is None:
            continue
        label = prefix + ":" + str(ident)
        for key, source_field in (("part_key", "part_key"), ("role", "representation_role")):
            if mapping[key] not in actual:
                a.missing(label + ":" + key, "Native receipt omits " + mapping[key])
            else:
                a.add(label + ":" + key, actual[mapping[key]] == expected.get(source_field),
                      expected=expected.get(source_field), actual=actual[mapping[key]])
        if mapping["transform"] not in actual:
            a.missing(label + ":transform", "No actual cold-open transform recorded")
        else:
            try:
                e = matrix4(expected["T_S_local"], "matrix4_mm")
                t = matrix4(actual[mapping["transform"]], transform_encoding)
                dt = max(abs(e[i][3] - t[i][3]) for i in range(3))
                dr = max(abs(e[i][j] - t[i][j]) for i in range(3) for j in range(3))
                a.add(label + ":transform", dt <= translation_tolerance_mm and dr <= rotation_tolerance,
                      max_translation_error_mm=dt, max_rotation_entry_error=dr)
            except (KeyError, TypeError, ValueError) as error:
                a.add(label + ":transform", False, reason=str(error))
        if mapping["world_basis"] not in actual:
            a.missing(label + ":world_basis_points", "No actual SolidWorks IMathPoint.MultiplyTransform basis witness")
        else:
            try:
                basis_error, expected_points = world_basis_error_mm(
                    expected["T_S_local"], actual[mapping["world_basis"]])
                a.add(label + ":world_basis_points", basis_error <= 1e-5,
                      max_coordinate_error_mm=basis_error, tolerance_mm=1e-5,
                      expected_world_points_mm=expected_points,
                      actual_world_points_mm=actual[mapping["world_basis"]],
                      basis_local_points_mm=[[0,0,0],[10,0,0],[0,10,0],[0,0,10]],
                      method="Frozen T_S_local direct point multiplication versus recorded native IMathPoint results; producer max_error ignored")
            except (KeyError, TypeError, ValueError) as error:
                a.add(label + ":world_basis_points", False, reason=str(error))
        for key, test in (("fixed", lambda x: x is True),
                          ("solid_count", lambda x: type(x) is int and x > 0)):
            if mapping[key] not in actual:
                a.missing(label + ":" + key, "Native receipt omits " + mapping[key])
            else:
                a.add(label + ":" + key, test(actual[mapping[key]]), actual=actual[mapping[key]])
    return a.summary()


def no_release_upgrade(audit, data, location="root"):
    if isinstance(data, dict):
        for key, value in data.items():
            here = location + "/" + str(key)
            if key in CLAIM_KEYS:
                audit.add("claim_boundary:" + here, value in (False, None), actual=value)
            no_release_upgrade(audit, value, here)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            no_release_upgrade(audit, value, location + "/" + str(i))


def import_rows(data):
    """Recognize actual sw_actions receipts, including sw_worker envelopes."""
    if isinstance(data, dict):
        if all(k in data for k in ("source", "source_sha256", "target", "native_save", "facts")):
            yield data
            return
        for value in data.values():
            yield from import_rows(value)
    elif isinstance(data, list):
        for value in data:
            yield from import_rows(value)


def assembly_rows(data):
    """Recognize only explicit state + components cold receipts; no inference."""
    if isinstance(data, dict):
        if data.get("state") in STATES and isinstance(data.get("components"), list):
            yield data
            return
        for value in data.values():
            yield from assembly_rows(value)
    elif isinstance(data, list):
        for value in data:
            yield from assembly_rows(value)


def check_roundtrip_evidence(audit, part, row, package_root, label):
    """Accept a scalar mismatch only through a hash-bound actual OCC comparison.

    This function audits a recorded execution; it never performs an OCC Boolean.
    The original cross-kernel scalar failure is retained by the caller. A naked
    PASS label, a copied number, or a missing source/native/roundtrip/script hash
    cannot satisfy this independent receipt check.
    """
    start = len(audit.checks)
    evidence = row.get("source_comparison", {}).get("roundtrip_validation")
    if not isinstance(evidence, dict):
        audit.missing(label + ":roundtrip_evidence", "Cross-kernel volume mismatch requires an executed, fully hash-bound same-kernel source/native STEP comparison")
        return None
    if "status" not in evidence:
        audit.missing(label + ":roundtrip_status", "Validation status is not recorded")
    else:
        audit.add(label + ":roundtrip_status", evidence["status"] == "PASS", actual=evidence["status"])
    for field, expected in (("source_sha256", part.get("sha256")),
                            ("native_sha256", row.get("native_save", {}).get("sha256"))):
        if field not in evidence:
            audit.missing(label + ":" + field, "Roundtrip validation omits a required source/native binding")
        else:
            audit.add(label + ":" + field, isinstance(expected, str) and str(evidence[field]).lower() == expected.lower(),
                      actual=evidence[field], expected=expected)
    check_file(audit, label + ":roundtrip_source_file", part.get("path"), evidence.get("source_sha256"), package_root, ".step")
    check_file(audit, label + ":roundtrip_native_file", row.get("target"), evidence.get("native_sha256"), package_root, ".sldprt")
    roundtrip = check_file(audit, label + ":roundtrip_step", evidence.get("roundtrip_path"), evidence.get("roundtrip_sha256"), package_root, ".step")
    check_file(audit, label + ":roundtrip_validator", evidence.get("validation_script_path"), evidence.get("validation_script_sha256"), package_root, ".py")
    saved_roundtrip = row.get("roundtrip")
    if not isinstance(saved_roundtrip, dict):
        audit.missing(label + ":native_roundtrip_export_binding", "No original SolidWorks roundtrip export receipt")
    elif roundtrip:
        saved = saved_roundtrip.get("save", {})
        try:
            path_match = norm(saved_roundtrip["path"]) == norm(roundtrip["path"])
        except (KeyError, TypeError):
            path_match = False
        audit.add(label + ":native_roundtrip_export_binding",
                  path_match and saved.get("ok") is True and saved.get("errors") == 0
                  and str(saved.get("sha256", "")).lower() == roundtrip["sha256"].lower(),
                  original_export=saved_roundtrip)
    for field, limit in (("symmetric_difference_mm3", 1e-5),
                         ("bbox_max_difference_mm", 1e-4),
                         ("volume_difference_mm3", 1e-5)):
        if field not in evidence:
            audit.missing(label + ":roundtrip_" + field, "Same-kernel numeric execution result missing")
            continue
        number = evidence[field]
        valid = type(number) in (int, float) and math.isfinite(number) and 0 <= number <= limit
        audit.add(label + ":roundtrip_" + field, valid,
                  actual=number if type(number) not in (float,) or math.isfinite(number) else repr(number),
                  tolerance=limit)
    new_checks = audit.checks[start:]
    if any(c["status"] == "FAIL" for c in new_checks):
        return False
    if any(c["status"] == "INCOMPLETE" for c in new_checks):
        return None
    return True


def check_imports(audit, manifest, receipts, package_root,
                  bounds_tolerance_mm=1e-3, relative_volume_tolerance=1e-7):
    parts = manifest.get("parts", [])
    by_source = {}
    for row in receipts:
        by_source.setdefault(norm(row["source"]), []).append(row)
    targets = {}
    for part in parts:
        key = part["part_key"]
        label = "import:" + key
        rows = by_source.get(norm(part["path"]), [])
        if len(rows) != 1:
            audit.add(label + ":receipt", None if not rows else False, matches=len(rows), reason="Exactly one accepted import receipt per source is required")
            continue
        row = rows[0]
        audit.add(label + ":producer_status", row.get("status") == "NATIVE_PART_SAVED_AND_REOPENED", actual=row.get("status"))
        audit.add(label + ":source_binding", row["source_sha256"].lower() == part["sha256"].lower())
        native = check_file(audit, label + ":native", row.get("target"), row.get("native_save", {}).get("sha256"), package_root, ".sldprt")
        if native:
            targets[key] = native["path"]
        facts = row.get("facts", {})
        audit.add(label + ":solid_count", facts.get("solid_count") == part.get("expected_solid_count") and facts.get("solid_count", 0) > 0,
                  actual=facts.get("solid_count"), expected=part.get("expected_solid_count"))
        if "sheet_count" not in facts:
            audit.missing(label + ":sheet_count", "No native sheet-body count")
        else:
            audit.add(label + ":sheet_count", facts["sheet_count"] == 0, actual=facts["sheet_count"])
        try:
            source_volume, native_volume = float(part["expected_volume_mm3"]), float(facts["volume_mm3"])
            limit = max(1e-4, abs(source_volume) * relative_volume_tolerance)
            finite = math.isfinite(source_volume) and math.isfinite(native_volume)
            difference = abs(native_volume - source_volume) if finite else None
            scalar_pass = finite and difference <= limit
            audit.add(label + ":cross_kernel_scalar_volume", scalar_pass, required=False,
                      source_volume_mm3=source_volume if finite else repr(source_volume),
                      native_volume_mm3=native_volume if finite else repr(native_volume),
                      highest_accuracy_native_volume_mm3=facts.get("highest_accuracy_volume_mm3"),
                      error_mm3=difference, tolerance_mm3=limit,
                      policy="Original scalar check preserved with unchanged tolerance; alternate acceptance requires actual same-kernel material roundtrip evidence")
            expected_bounds = part["local_bounds_mm"]
            bb = facts["bounds_mm"]
            delta = max(abs(float(bb[k][i])-float(expected_bounds[side][i]))
                        for k, side in enumerate(("min_mm", "max_mm")) for i in range(3))
            audit.add(label + ":local_bounds", math.isfinite(delta) and delta <= bounds_tolerance_mm,
                      max_error_mm=delta, tolerance_mm=bounds_tolerance_mm)
            geometry_basics = (finite and facts.get("solid_count") == part.get("expected_solid_count")
                               and facts.get("solid_count", 0) > 0 and facts.get("sheet_count") == 0
                               and math.isfinite(delta) and delta <= bounds_tolerance_mm)
            if scalar_pass:
                transfer = geometry_basics
                route = "SOURCE_NATIVE_SCALAR_FACTS_MATCH"
            elif not finite:
                transfer = False
                route = "INVALID_NONFINITE_GEOMETRY_FACT"
            else:
                transfer = check_roundtrip_evidence(audit, part, row, package_root, label)
                if not geometry_basics:
                    transfer = False
                route = "ACTUAL_SAME_KERNEL_SOURCE_NATIVE_ROUNDTRIP"
            audit.add(label + ":geometry_transfer_acceptance", transfer, route=route,
                      scalar_volume_pass=scalar_pass,
                      preserved_scalar_difference_mm3=difference)
        except (KeyError, TypeError, ValueError, IndexError) as error:
            audit.missing(label + ":geometry_facts", str(error))
        for field in ("external_reference_count", "auxiliary_reference_count", "interconnect_feature_count"):
            if field not in row:
                audit.missing(label + ":" + field, "Importer did not record this separate witness")
            else:
                audit.add(label + ":" + field, row[field] == 0, actual=row[field])
        audit.add(label + ":save_status", row.get("native_save", {}).get("ok") is True and row.get("native_save", {}).get("errors") == 0)
        for field in ("import_error", "reopen_warning"):
            if field not in row:
                audit.missing(label + ":" + field, "Native API error/warning witness missing")
            else:
                audit.add(label + ":" + field, row[field] == 0, actual=row[field])
    return targets


def check_manifest(audit, manifest, package_root):
    audit.add("manifest:schema", manifest.get("schema") == "WP05_SW_PART_SOURCE_V1")
    audit.add("manifest:full_export", manifest.get("smoke") is False and manifest.get("status") == "PASS_SOURCE_GEOMETRY_EXPORT_ONLY")
    audit.add("manifest:coordinate_contract", (manifest.get("units"), manifest.get("frame"), manifest.get("transform_units")) == ("mm", "S", "mm"))
    before, after = manifest.get("source_sha256_before"), manifest.get("source_sha256_after")
    audit.add("manifest:source_before_after", isinstance(before, dict) and bool(before) and before == after)
    for path, digest in (before or {}).items():
        check_file(audit, "frozen_source:" + str(path), path, digest)
    parts = manifest.get("parts", [])
    audit.add("manifest:unique_part_keys", bool(parts) and len({p.get("part_key") for p in parts}) == len(parts))
    for part in parts:
        check_file(audit, "source_part:" + str(part.get("part_key")), part.get("path"), part.get("sha256"), package_root, ".step")
    keyset = {p.get("part_key") for p in parts}
    role_sets = []
    for state in STATES:
        rows = manifest.get("states", {}).get(state, {}).get("instances")
        if not isinstance(rows, list):
            audit.missing("manifest:" + state, "Required state is absent")
            continue
        audit.add("manifest:" + state + ":585_instances", len(rows) == 585 and len({r.get("id") for r in rows}) == 585)
        audit.add("manifest:" + state + ":part_mapping", all(r.get("part_key") in keyset for r in rows))
        role_sets.append({r.get("id"):r.get("representation_role") for r in rows})
        source_candidate = manifest.get("source_candidate")
        if source_candidate:
            source_path = Path(source_candidate) / "results" / (state + "_instances.json")
            if source_path.is_file() and str(source_path.resolve()) in (before or {}):
                source_rows = read_json(source_path).get("instances", [])
                source = {r.get("id"):r for r in source_rows}
                good = len(source) == 585 and set(source) == {r.get("id") for r in rows}
                fields = (("T_S_local", "T_S_local"), ("representation_role", "representation_role"),
                          ("source_mass_kg", "mass_kg"), ("qualification_status", "qualification_status"),
                          ("product_role", "product_role"), ("arm_link", "arm_link"))
                mismatches = []
                for row in rows:
                    original = source.get(row.get("id"), {})
                    mismatches.extend(dict(id=row.get("id"), field=a) for a,b in fields if row.get(a) != original.get(b))
                audit.add("manifest:" + state + ":frozen_metadata", good and not mismatches, mismatches=mismatches)
            else:
                audit.missing("manifest:" + state + ":frozen_metadata", "Frozen instance receipt absent or not hash-bound")
    audit.add("manifest:cross_state_id_roles", len(role_sets) == 3 and role_sets[0] == role_sets[1] == role_sets[2])


def check_assemblies(audit, manifest, records, native_targets, package_root, field_map=None,
                     transform_encoding="sw16_m_column_rotation"):
    for state in STATES:
        matches = [r for r in records if r.get("state") == state]
        if len(matches) != 1:
            audit.add("assembly:" + state + ":receipt", None if not matches else False, matches=len(matches))
            continue
        rec = matches[0]
        expected = manifest.get("states", {}).get(state, {}).get("instances", [])
        check_state_rows(expected, rec["components"], field_map=field_map,
                         transform_encoding=transform_encoding, audit=audit, state=state)
        check_file(audit, "assembly:" + state + ":file", rec.get("target"), rec.get("target_sha256"), package_root, ".sldasm")
        for field in ("open_errors", "open_warnings"):
            if field not in rec:
                audit.missing("assembly:" + state + ":" + field, "Cold-open API evidence omitted")
            else:
                audit.add("assembly:" + state + ":" + field, rec[field] == 0, actual=rec[field])
        dependencies = rec.get("dependencies")
        if not isinstance(dependencies, list):
            audit.missing("assembly:" + state + ":dependencies", "Actual cold-open dependency list missing")
            continue
        paths = []
        for item in dependencies:
            path = item.get("path") if isinstance(item, dict) else item
            expected_hash = item.get("sha256") if isinstance(item, dict) else None
            fact = check_file(audit, "assembly:" + state + ":dependency", path, expected_hash, package_root)
            if fact:
                paths.append(norm(fact["path"]))
        expected_paths = {norm(native_targets[r["part_key"]]) for r in expected if r["part_key"] in native_targets}
        audit.add("assembly:" + state + ":dependency_set", set(paths) == expected_paths and bool(expected_paths))
        id_key = (field_map or {}).get("id", "id")
        actual = {r.get(id_key):r for r in rec["components"]}
        bad_paths, missing_paths = [], []
        for source in expected:
            row = actual.get(source.get("id"), {})
            if "path" not in row or source["part_key"] not in native_targets:
                missing_paths.append(source.get("id"))
            elif norm(row["path"]) != norm(native_targets[source["part_key"]]):
                bad_paths.append(source.get("id"))
        audit.add("assembly:" + state + ":instance_dependency_mapping", None if missing_paths else not bad_paths,
                  missing_ids=missing_paths, mismatched_ids=bad_paths)


def run_audit(manifest_path, import_paths, assembly_paths, package_root, *, field_map=None,
              transform_encoding="sw16_m_column_rotation"):
    audit = Audit()
    inputs = []
    def load(path):
        doc = read_json(path)
        inputs.append(dict(path=str(Path(path).resolve()), sha256=sha256(path)))
        no_release_upgrade(audit, doc, str(path))
        return doc
    manifest = load(manifest_path)
    check_manifest(audit, manifest, package_root)
    imports = [row for p in import_paths for row in import_rows(load(p))]
    assemblies = [row for p in assembly_paths for row in assembly_rows(load(p))]
    targets = check_imports(audit, manifest, imports, package_root)
    check_assemblies(audit, manifest, assemblies, targets, package_root, field_map, transform_encoding)
    for item in inputs:
        audit.add("receipt_unchanged_during_audit:" + item["path"], sha256(item["path"]) == item["sha256"])
    return dict(schema="WP05_INDEPENDENT_NATIVE_RECEIPT_AUDIT_V1", generated_utc=datetime.now(timezone.utc).isoformat(),
                checker_sha256=sha256(__file__), inputs=inputs,
                source_part_count=len(manifest.get("parts", [])), recognized_import_receipts=len(imports),
                recognized_cold_assembly_receipts=len(assemblies), **audit.summary(),
                audit_method="Filesystem hashes and explicit producer receipt comparison; this checker never executes COM or CAD",
                limitations=["A passing receipt audit is not an independent CAD-kernel import or a physical assembly test",
                             "Fixed poses do not prove native mates, load capacity, tolerances, or continuous collision freedom"],
                manufacturing_release=False, all_mechanical_design_complete=False,
                physical_assembly_completed=False, continuous_motion_verified=False,
                hardware_command_authorized=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--imports", type=Path, action="append", default=[])
    ap.add_argument("--assembly", type=Path, action="append", default=[])
    ap.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--field-map", type=Path, help="Explicit JSON mapping for native instance fields")
    ap.add_argument("--transform-encoding", choices=("sw16_m_column_rotation", "matrix4_mm"), default="sw16_m_column_rotation")
    args = ap.parse_args(argv)
    try:
        result = run_audit(args.manifest, args.imports, args.assembly, args.package_root,
                           field_map=read_json(args.field_map) if args.field_map else None,
                           transform_encoding=args.transform_encoding)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result = dict(schema="WP05_INDEPENDENT_NATIVE_RECEIPT_AUDIT_V1", status="INCOMPLETE",
                      reason="Evidence could not be parsed", error=repr(error), manufacturing_release=False)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if result["status"] == "FAIL" else 2 if result["status"] == "INCOMPLETE" else 0


if __name__ == "__main__":
    sys.exit(main())
