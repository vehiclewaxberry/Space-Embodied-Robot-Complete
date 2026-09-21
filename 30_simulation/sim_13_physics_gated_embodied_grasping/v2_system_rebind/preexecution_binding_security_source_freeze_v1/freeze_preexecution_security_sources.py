#!/usr/bin/env python3
"""Print a deterministic hash manifest for this source-only package."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
EXCLUDED_DIRECTORIES = {"evidence", "results", "manifest", "__pycache__", ".pytest_cache"}
PROHIBITED_EXTENSIONS = {
    ".urdf", ".xacro", ".sdf",
    ".step", ".stp", ".iges", ".igs", ".brep", ".fcstd", ".dwg", ".dxf", ".sat", ".x_t", ".x_b",
    ".stl", ".obj", ".dae", ".ply", ".gltf", ".glb", ".3mf",
    ".inp", ".odb", ".pyc", ".pyo",
}
PROHIBITED_CACHE_DIRECTORIES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".hypothesis", ".tox", ".nox",
}
PROHIBITED_CALLS = {"gen_urdf", "_build_robot"}
PROHIBITED_IMPORT_FRAGMENT = "unified_r2_urdf_source_v2"
FIXED_OUTPUT_FILES = {
    "evidence/PREEXECUTION_BINDING_SECURITY_INDEPENDENT_AUDIT_V1.json",
    "evidence/PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_VALIDATION_V1.json",
    "evidence/PREEXECUTION_SECURITY_NEGATIVE_CONTROLS_V1.json",
    "evidence/PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1.json",
    "manifest/PREEXECUTION_BINDING_SECURITY_SOURCE_SHA256_V1.json",
    "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json",
    "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _included_files() -> list[Path]:
    output: list[Path] = []
    for path in HERE.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(HERE).parts):
            continue
        output.append(path)
    return sorted(output, key=lambda item: item.relative_to(HERE).as_posix())


def _source_static_findings(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        relative = path.relative_to(PROJECT).as_posix()
        if path.suffix.lower() in PROHIBITED_EXTENSIONS:
            findings.append(f"PROHIBITED_EXTENSION:{relative}")
        if path.suffix.lower() != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if PROHIBITED_IMPORT_FRAGMENT in alias.name:
                        findings.append(f"PROHIBITED_IMPORT:{relative}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if PROHIBITED_IMPORT_FRAGMENT in (node.module or ""):
                    findings.append(f"PROHIBITED_IMPORT:{relative}:{node.module}")
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if name in PROHIBITED_CALLS:
                    findings.append(f"PROHIBITED_CALL:{relative}:{name}")
    return findings


def package_asset_cache_findings() -> list[str]:
    """Scan the complete package, including excluded output directories."""

    findings: list[str] = []
    for path in sorted(HERE.rglob("*"), key=lambda item: item.relative_to(HERE).as_posix()):
        relative = path.relative_to(PROJECT).as_posix()
        if path.is_dir() and path.name.lower() in PROHIBITED_CACHE_DIRECTORIES:
            findings.append(f"PROHIBITED_CACHE_DIRECTORY:{relative}")
        elif path.is_file() and path.suffix.lower() in PROHIBITED_EXTENSIONS:
            findings.append(f"PROHIBITED_ASSET_OR_CACHE_FILE:{relative}")
    return findings


def package_inventory_findings(source_relative_paths: set[str] | None = None) -> list[str]:
    """Enforce the exact full-package file and directory allowlist.

    The extension blacklist is only defence in depth.  Authority comes from
    the precise union of source-manifest files and the seven fixed DAG outputs.
    """

    if source_relative_paths is None:
        manifest_path = HERE / "manifest/PREEXECUTION_BINDING_SECURITY_SOURCE_SHA256_V1.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            package_prefix = HERE.relative_to(PROJECT).as_posix() + "/"
            source_relative_paths = {
                item["path"][len(package_prefix):]
                for item in manifest["files"]
                if isinstance(item.get("path"), str)
                and item["path"].startswith(package_prefix)
            }
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return ["SOURCE_MANIFEST_UNAVAILABLE_FOR_FULL_PACKAGE_ALLOWLIST"]
    allowed_files = set(source_relative_paths) | FIXED_OUTPUT_FILES
    allowed_directories = {
        parent.as_posix()
        for relative in allowed_files
        for parent in PurePosixPath(relative).parents
        if parent.as_posix() != "."
    }
    actual_files = {
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.is_file()
    }
    actual_directories = {
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.is_dir()
    }
    findings = [f"UNEXPECTED_PACKAGE_FILE:{path}" for path in sorted(actual_files - allowed_files)]
    findings.extend(f"MISSING_PACKAGE_FILE:{path}" for path in sorted(allowed_files - actual_files))
    findings.extend(
        f"UNEXPECTED_PACKAGE_DIRECTORY:{path}"
        for path in sorted(actual_directories - allowed_directories)
    )
    findings.extend(
        f"MISSING_PACKAGE_DIRECTORY:{path}"
        for path in sorted(allowed_directories - actual_directories)
    )
    return findings


def build_manifest() -> dict[str, object]:
    files = _included_files()
    source_relative_paths = {path.relative_to(HERE).as_posix() for path in files}
    inventory_findings = package_inventory_findings(source_relative_paths)
    findings = package_asset_cache_findings() + inventory_findings + _source_static_findings(files)
    records = [
        {
            "path": path.relative_to(PROJECT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in files
    ]
    return {
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_MANIFEST_V1",
        "scope": "SOURCE_ONLY_NO_GENERATION_NO_CAD_NO_RUNTIME",
        "file_count": len(records),
        "files": records,
        "source_static_findings": findings,
        "source_static_pass": not findings,
        "full_package_allowed_file_count": len(source_relative_paths | FIXED_OUTPUT_FILES),
        "fixed_output_files": sorted(FIXED_OUTPUT_FILES),
        "package_inventory_findings": inventory_findings,
        "excluded_output_directories": sorted(EXCLUDED_DIRECTORIES),
        "prohibited_extension_count": len(PROHIBITED_EXTENSIONS),
        "prohibited_cache_directory_names": sorted(PROHIBITED_CACHE_DIRECTORIES),
    }


def main() -> int:
    manifest = build_manifest()
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if manifest["source_static_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
