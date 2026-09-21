"""Repair Python path constructors after the REORG04 physical move.

This is a mechanical namespace migration only.  It changes repository-root
path components and capsule depth calculations; it does not alter algorithms,
thresholds, numerical constants, or scientific verdict logic.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


ROOT_VARIABLES = ("REPO_ROOT", "PROJECT_ROOT", "ROOT", "REPO", "repo_root", "root")


def build_replacements() -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []

    # Reordered capsules must be handled before single root components.
    for var in ROOT_VARIABLES:
        replacements.extend(
            [
                (
                    f'{var} / "src" / "sim_09_grasp_evaluator"',
                    f'{var} / "30_simulation" / "sim_09_grasp_evaluator" / "src"',
                ),
                (
                    f'{var} / "results" / "sim_09_grasp_evaluator"',
                    f'{var} / "30_simulation" / "sim_09_grasp_evaluator" / "results"',
                ),
                (
                    f'{var} / "src" / "visualization"',
                    f'{var} / "70_tools" / "project_visualization" / "src"',
                ),
                (
                    f'{var} / "tests" / "visualization"',
                    f'{var} / "70_tools" / "project_visualization" / "tests"',
                ),
                (
                    f'{var} / "tables" / "visualization"',
                    f'{var} / "40_evidence" / "artifacts" / "visualization" / "tables"',
                ),
                (
                    f'{var} / "figures" / "visualization"',
                    f'{var} / "40_evidence" / "artifacts" / "visualization" / "figures"',
                ),
                (
                    f'{var} / "videos" / "visualization"',
                    f'{var} / "40_evidence" / "artifacts" / "visualization" / "videos"',
                ),
                (
                    f'{var} / "artifacts" / "visualization"',
                    f'{var} / "40_evidence" / "artifacts" / "visualization"',
                ),
                (
                    f'{var} / "docs" / "stage1_spacecraft_layout"',
                    f'{var} / "20_engineering" / "stage1_spacecraft_layout"',
                ),
            ]
        )

        for old, new in (
            ("research", '"10_research"'),
            ("knowledge_base", '"10_research" / "knowledge_base"'),
            ("sim", '"30_simulation"'),
            ("e15_ancf_certification", '"30_simulation" / "e15_ancf_certification"'),
            ("e15_core_coverage", '"30_simulation" / "e15_core_coverage"'),
            ("e16_sync_capture", '"30_simulation" / "e16_sync_capture"'),
            ("assembly_research", '"30_simulation"'),
            ("artifacts", '"40_evidence" / "artifacts"'),
            ("pdf", '"50_literature" / "pdf"'),
            ("tools", '"70_tools"'),
            ("external", '"80_third_party" / "external"'),
            ("vendor", '"80_third_party" / "vendor"'),
            ("cad", '"20_engineering" / "cad"'),
            ("config", '"20_engineering" / "config"'),
        ):
            replacements.append((f'{var} / "{old}"', f"{var} / {new}"))

        # os.path.join variants.  Specific reordered paths come first.
        for old_args, new_args in (
            ('"src", "sim_09_grasp_evaluator"', '"30_simulation", "sim_09_grasp_evaluator", "src"'),
            ('"results", "sim_09_grasp_evaluator"', '"30_simulation", "sim_09_grasp_evaluator", "results"'),
            ('"src", "visualization"', '"70_tools", "project_visualization", "src"'),
            ('"tests", "visualization"', '"70_tools", "project_visualization", "tests"'),
            ('"tables", "visualization"', '"40_evidence", "artifacts", "visualization", "tables"'),
            ('"figures", "visualization"', '"40_evidence", "artifacts", "visualization", "figures"'),
            ('"videos", "visualization"', '"40_evidence", "artifacts", "visualization", "videos"'),
            ('"artifacts", "visualization"', '"40_evidence", "artifacts", "visualization"'),
            ('"docs", "stage1_spacecraft_layout"', '"20_engineering", "stage1_spacecraft_layout"'),
        ):
            replacements.append(
                (f"os.path.join({var}, {old_args}", f"os.path.join({var}, {new_args}")
            )

        for old, new_args in (
            ("research", '"10_research"'),
            ("sim", '"30_simulation"'),
            ("e15_ancf_certification", '"30_simulation", "e15_ancf_certification"'),
            ("e15_core_coverage", '"30_simulation", "e15_core_coverage"'),
            ("e16_sync_capture", '"30_simulation", "e16_sync_capture"'),
            ("artifacts", '"40_evidence", "artifacts"'),
            ("pdf", '"50_literature", "pdf"'),
            ("tools", '"70_tools"'),
            ("external", '"80_third_party", "external"'),
            ("vendor", '"80_third_party", "vendor"'),
            ("cad", '"20_engineering", "cad"'),
            ("config", '"20_engineering", "config"'),
        ):
            replacements.append(
                (f'os.path.join({var}, "{old}",', f"os.path.join({var}, {new_args},")
            )

    # Longest first, then a placeholder pass prevents generated paths from
    # triggering a more general rule.
    return sorted(set(replacements), key=lambda item: len(item[0]), reverse=True)


FILE_REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "30_simulation/sim_09_grasp_evaluator/src/_bootstrap.py": [
        ('os.path.join(HERE, "..", "..")', 'os.path.join(HERE, "..", "..", "..")'),
    ],
    "30_simulation/sim_09_grasp_evaluator/tests/_helpers.py": [
        ('os.path.join(HERE, "..", "..")', 'os.path.join(HERE, "..", "..", "..")'),
    ],
    "30_simulation/e15_ancf_certification/src/model.py": [
        ("REPO_ROOT = CERT_ROOT.parent\n", "REPO_ROOT = CERT_ROOT.parents[1]\n"),
    ],
    "30_simulation/e15_ancf_certification/tests/run_tests.py": [
        ("REPO_ROOT = CERT_ROOT.parent\n", "REPO_ROOT = CERT_ROOT.parents[1]\n"),
    ],
    "30_simulation/e15_core_coverage/src/build_core_coverage.py": [
        ("REPO_ROOT = HERE.parents[2]", "REPO_ROOT = HERE.parents[3]"),
    ],
    "30_simulation/e15_core_coverage/tests/test_core_coverage.py": [
        ("ROOT = Path(__file__).resolve().parents[2]", "ROOT = Path(__file__).resolve().parents[3]"),
    ],
    "30_simulation/e15_core_coverage/tests/run_all.py": [
        ("ROOT = Path(__file__).resolve().parents[2]", "ROOT = Path(__file__).resolve().parents[3]"),
    ],
    "30_simulation/e16_sync_capture/src/sync_model.py": [
        ("REPO_ROOT = E16_ROOT.parent\n", "REPO_ROOT = E16_ROOT.parents[1]\n"),
    ],
    "30_simulation/e16_sync_capture/tests/run_all.py": [
        ("REPO_ROOT = E16_ROOT.parent\n", "REPO_ROOT = E16_ROOT.parents[1]\n"),
    ],
    "10_research/competition_convergence/src/run_competition_gate.py": [
        ('"ASM-00_interface_ssot"', '"asm_00_interface_preflight"'),
    ],
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once_pass(text: str, replacements: list[tuple[str, str]]) -> tuple[str, int]:
    restored: list[tuple[str, str]] = []
    count = 0
    for index, (old, new) in enumerate(replacements):
        delta = text.count(old)
        if not delta:
            continue
        placeholder = f"__REORG04_PY_PATH_{index:05d}__"
        text = text.replace(old, placeholder)
        restored.append((placeholder, new))
        count += delta
    for placeholder, new in restored:
        text = text.replace(placeholder, new)
    return text, count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    rows: list[dict[str, str | int]] = []
    general = build_replacements()

    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".git/", "80_third_party/", "50_literature/pdf/")):
            continue
        if rel.endswith("reorg04_rewrite_composed_python_paths.py"):
            continue
        data = path.read_bytes()
        encoding = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        before = text
        count = 0
        file_replacements = list(FILE_REPLACEMENTS.get(rel, []))
        if rel.startswith("70_tools/project_visualization/"):
            file_replacements.extend(
                [
                    (
                        'os.path.join(HERE, "..", "..")',
                        'os.path.join(HERE, "..", "..", "..")',
                    ),
                    (
                        'os.path.join(_HERE, "..", "..")',
                        'os.path.join(_HERE, "..", "..", "..")',
                    ),
                ]
            )
        text, delta = replace_once_pass(text, file_replacements)
        count += delta
        text, delta = replace_once_pass(text, general)
        count += delta
        if text == before:
            continue
        path.write_text(text, encoding=encoding, newline="")
        after = path.read_bytes()
        rows.append(
            {
                "path": rel,
                "replacement_count": count,
                "before_sha256": sha256(data),
                "after_sha256": sha256(after),
            }
        )

    log = Path(args.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("path", "replacement_count", "before_sha256", "after_sha256"),
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"PY_FILES_REWRITTEN={len(rows)}")
    print(f"PY_PATH_REPLACEMENTS={sum(int(row['replacement_count']) for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
