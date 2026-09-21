#!/usr/bin/env python3
"""Materialize the decisive M3R interface-evidence inventory.

The bounded exhaustive search is preserved separately in
``M3R_EXHAUSTIVE_LOCAL_SEARCH_RECEIPT.json``.  This script does not repeat that
expensive scan; it inventories the decisive source evidence and all additive
M3R products, with content hashes.  It never alters source evidence.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
F3R2 = PROJECT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
OUT = F3R2 / "03_native_cad/M3_interface_authority/M3R_INTERFACE_EVIDENCE_INVENTORY.csv"
SCOPE_MANIFEST = (
    F3R2 / "03_native_cad/M3_interface_authority/"
    "M3R_SCOPE_MANIFEST_SHA256.txt"
)

ROOTS = (
    ("PROJECT_ROOT", PROJECT),
    ("MIGRATED_WORKTREE", Path(
        "F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/"
        "WORKTREE_RECONCILIATION/20_engineering")),
    ("WORKTREE_SAFETY_SNAPSHOT", Path(
        "F:/_SEI_PROJECT_CONSOLIDATION_20260807/12_WAVE4/"
        "WORKTREE_SAFETY_SNAPSHOT")),
    ("ROBOTIC_ARM_DONOR", Path("F:/Robotic arm")),
    ("REFERENCE_LIBRARY", Path("F:/SPACE_ROBOTICS_REFERENCE_LIBRARY")),
)

EXTENSIONS = {
    ".step", ".stp", ".sldprt", ".sldasm", ".fcstd", ".pdf", ".dwg",
    ".dxf", ".png", ".jpg", ".jpeg", ".yaml", ".yml", ".json",
    ".csv", ".md", ".txt", ".urdf", ".xml", ".html", ".py",
}
TEXT_EXTENSIONS = {
    ".step", ".stp", ".yaml", ".yml", ".json", ".csv", ".md", ".txt",
    ".urdf", ".xml", ".html", ".py",
}
SKIP_PARTS = {".git", "__pycache__", "node_modules", "mesh", "RAW"}

PATTERNS = {
    "contains_B601": re.compile(r"(?i)\bB601\b|reBot[_ -]?B601"),
    "contains_M3": re.compile(r"(?i)(?<![A-Z0-9])(?:H|K)?M3(?:[-x* ]|\b)"),
    "contains_M6": re.compile(r"(?i)(?<![A-Z0-9])M6(?:[-x* ]|\b)|(?:diameter|[Ø⌀])\s*6\.6"),
    "contains_M8": re.compile(r"(?i)(?<![A-Z0-9])M8(?:[-x* ]|\b)|(?:diameter|[Ø⌀])\s*9(?:\.0)?\b"),
    "contains_PCD90": re.compile(r"(?i)PCD\s*=?\s*90(?:\.5\d*)?|R\s*=?\s*45\.25|90\.509|45\.254"),
    "contains_BCD130": re.compile(r"(?i)BCD\s*=?\s*130|bolt.{0,20}(?:circle|diameter).{0,12}130"),
    "contains_140x140": re.compile(r"(?i)140\s*[x×]\s*140|(?:[-+±]?70(?:\.0)?)\s*[,/ ]+\s*(?:[-+±]?70(?:\.0)?)"),
}

PATH_CONTEXT = re.compile(
    r"(?i)B601|B106|B51|reBot|arm_b601|base[_ -]?(?:plate|link|adapter)|"
    r"flange|interface|adapter|mounting|installation|ICD|datasheet|manual|"
    r"drawing|G30|G31|TSM"
)
CONTENT_CONTEXT = re.compile(
    r"(?i)B601|reBot|base\s*(?:plate|link|adapter)|flange|interface|adapter|"
    r"mounting|load\s*bridge|central[_ ]boss|HM4-75"
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def read_searchable(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
    if suffix == ".pdf" and PATH_CONTEXT.search(str(path)):
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    return ""


def classify(path: Path, combined: str, flags: dict[str, bool]) -> tuple[str, str, str]:
    low = str(path).replace("\\", "/").lower()
    name = path.name.lower()
    if name == "m3r_b601_brep_interface_measurement.json":
        return "AS_BUILT_BREP_MEASUREMENT", "B2", "post-M2 independent analytic B-rep evidence"
    if name.startswith("m3r_oem_") and "brep" in name:
        return "VENDOR_GEOMETRY_MEASUREMENT", "A2", "analytic measurement of vendor product geometry; not a released ICD"
    if name.startswith("m3r_legacy_adapter_brep"):
        return "LEGACY_PROJECT_ADAPTER_MEASUREMENT", "C1", "analytic measurement of standalone legacy project geometry"
    if "m3_interface_authority/cad/" in low:
        return "M3R_COMPETITION_ADAPTER_CANDIDATE", "C1", "new project prototype geometry; not OEM or flight-released"
    if name.startswith("m3r_"):
        return "M3R_DECISION_OR_RECEIPT", "C1", "additive M3R decision, search receipt, SSOT or verification evidence"
    if "brep_probe" in name or "tsm_cad_measurement" in name:
        if "f3r2" in low:
            return "PROJECT_BREP_MEASUREMENT", "B2", "check for face/axis double counting before reuse"
    if "80_third_party/vendor/rebot-devarm" in low:
        if path.suffix.lower() in {".step", ".stp"}:
            return "VENDOR_GEOMETRY", "A2", "vendor product geometry; not a released interface ICD"
        if path.suffix.lower() in {".md", ".txt", ".csv", ".pdf"}:
            return "VENDOR_BOM_OR_INSTRUCTION", "A2", "vendor product documentation; no flight-interface claim"
        return "VENDOR_VISUAL_REFERENCE", "C2", "visual corroboration only"
    if "freecad_authoritative" in low and "b601_base_adapter" in low:
        return "LEGACY_PROJECT_ADAPTER_GEOMETRY", "C1", "real standalone project geometry; absent from active top"
    if "f3r2_b601_base_interface" in name or "r3a_g30" in name or "r3b_g31" in name:
        return "SUPERSEDED_PROJECT_INTERPRETATION", "D", "8xM3 claim invalidated by unique-axis remeasurement"
    if "accepted" in low and "interface" in low:
        return "PROJECT_ACCEPTED_INTERFACE_CONTRACT", "B1", "scope must be checked for physical mounting applicability"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return "VISUAL_REFERENCE", "C2", "image only; not dimensional authority"
    if any(flags.values()):
        return "PROJECT_INTERFACE_REFERENCE", "C1", "project interpretation or supporting evidence"
    return "GENERAL_REFERENCE", "C2", "path-name context only"


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if path == OUT or path.suffix.lower() not in EXTENSIONS:
                continue
            yield path


def main() -> int:
    vendor = PROJECT / "80_third_party/vendor/reBot-DevArm/hardware/reBot_B601_DM"
    curated = [
        vendor / "reBot_B601_DM_v1.1_20260425.step",
        vendor / "readme.md",
        vendor / "3D_Printed_Parts/01_BASE_Plate.step",
        vendor / "3D_Printed_Parts/01_BASE_Link.step",
        vendor / "Metal_Parts/02_Base_Reinforcement_Part.step",
        F3R2 / "05_clearance/mesh/BREP_PROBE_MOUNT2.json",
        F3R2 / "03_native_cad/F3R2_TSM_CAD_MEASUREMENT.json",
        F3R2 / "03_native_cad/F3R2_TSM_INTERFACE_STACK.yaml",
        F3R2 / "03_native_cad/F3R2_B601_BASE_INTERFACE_DEFINITION.json",
        F3R2 / "99_tools/r3a_g30_tsm_stack.py",
        F3R2 / "99_tools/r3b_g31_base_interface.py",
        PROJECT / "20_engineering/cad/freecad_authoritative/"
                  "JOINT_INTERFACE_CONTROL_DOCUMENTS.yaml",
        PROJECT / "20_engineering/cad/B5_1_B601_interface_closure_candidate/"
                  "01_REQUIREMENTS/B51_INTERFACE_CONTROL_DRAWING.md",
        PROJECT / "20_engineering/system_design/legacy_root_structure/DOC_ACQUISITION.md",
        PROJECT / "20_engineering/system_design/legacy_root_structure/INTERFACE_ARM_BUS.yaml",
        PROJECT / "20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/"
                  "00_BASELINE/PARENT_LOCKED_INPUTS/PARENT_INITIAL_INPUT_LOCK/"
                  "B51_INPUT_LOCK.json",
        PROJECT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        PROJECT / "20_engineering/cad/freecad_authoritative/"
                  "B51R1_FREECAD_SSOT_PARAMETERS.csv",
        PROJECT / "20_engineering/cad/freecad_authoritative/"
                  "B601_BASE_ADAPTER_BOM.csv",
        PROJECT / "20_engineering/cad/freecad_authoritative/F3_BOM_PLAN.csv",
        PROJECT / "20_engineering/cad/freecad_authoritative/B601_BASE_ADAPTER.FCStd",
        PROJECT / "20_engineering/cad/freecad_authoritative/B601_BASE_ADAPTER.step",
        PROJECT / "40_evidence/c1_evidence/build_base_adapter.py",
        F3R2 / "03_native_cad/SPACECRAFT_V2_2_NATIVE_COPY/"
               "02_B601_Mount_and_Load_Path/parts/Adapter_Plate.SLDPRT",
    ]
    m3_root = F3R2 / "03_native_cad/M3_interface_authority"
    curated.extend(
        p for p in m3_root.rglob("*")
        if p.is_file()
        and p not in {OUT, SCOPE_MANIFEST}
        and p.suffix.lower() in EXTENSIONS
    )
    curated.extend([
        F3R2 / "99_tools/f3r2_path_resolver.py",
        F3R2 / "99_tools/test_f3r2_path_resolver.py",
        F3R2 / "99_tools/m3r_build_adapter_freecad.py",
        F3R2 / "99_tools/m3r_solidworks_native.py",
    ])
    rows = []
    seen = set()
    for path in curated:
        if not path.is_file():
            continue
        key = os.path.normcase(str(path.resolve()))
        if key in seen:
            continue
        seen.add(key)
        path_text = str(path).replace("\\", "/")
        content = read_searchable(path)
        combined = path_text + "\n" + content
        flags = {name: bool(regex.search(combined))
                 for name, regex in PATTERNS.items()}
        evidence_type, authority, notes = classify(path, combined, flags)
        stat = path.stat()
        source_root = ("PROJECT_ROOT" if PROJECT in path.parents
                       else "EXTERNAL_SEARCH_ROOT")
        rows.append({
            "path": str(path.resolve()).replace("\\", "/"),
            "file_type": path.suffix.lower().lstrip(".") or "none",
            "sha256": digest(path),
            "modified_time": datetime.fromtimestamp(
                stat.st_mtime, timezone.utc).isoformat(),
            "source_root": source_root,
            **{name: str(value).lower() for name, value in flags.items()},
            "evidence_type": evidence_type,
            "authority_level": authority,
            "notes": notes,
        })
    rows.sort(key=lambda r: (r["authority_level"], r["path"].lower()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "path", "file_type", "sha256", "modified_time", "source_root",
        "contains_B601", "contains_M3", "contains_M6", "contains_M8",
        "contains_PCD90", "contains_BCD130", "contains_140x140",
        "evidence_type", "authority_level", "notes",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    counts = {}
    for row in rows:
        counts[row["authority_level"]] = counts.get(row["authority_level"], 0) + 1
    print(f"inventory={OUT}")
    print(f"evidence_files={len(rows)} authority_counts={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
