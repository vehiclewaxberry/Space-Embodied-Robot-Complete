from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


TEXT_SUFFIXES = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".py", ".ps1",
    ".sh", ".bat", ".cmd", ".toml", ".ini", ".cfg", ".html", ".htm",
    ".js", ".ts", ".css", ".xml", ".rst", ".tex", ".bib",
}
TEXT_NAMES = {".gitignore", ".gitattributes", "Dockerfile", "Makefile"}

GLOBAL_TABLES = {
    "competition_claim_evidence_matrix.csv",
    "embodied_grasping_gap_matrix.csv",
    "existing_grasping_assets_audit.csv",
    "five_figure_readiness.csv",
    "gate_status_20260711.csv",
    "grasping_experiment_plan.csv",
    "paper01_literature_scan.csv",
    "paper_claim_evidence_matrix.csv",
    "report_section_evidence_map.csv",
}

# Ordered longest/specific first. These map the pre-REORG04 repository paths to
# the physical post-REORG04 paths. They are path-only transformations.
PREFIX_MAP = [
    ("sim/asm_00_interface_preflight/README.md", "30_simulation/asm_00_interface_preflight/MIGRATION_NOTICE.md"),
    ("assembly_research/ASM-00_interface_ssot/", "30_simulation/asm_00_interface_preflight/"),
    ("src/sim_09_grasp_evaluator/", "30_simulation/sim_09_grasp_evaluator/src/"),
    ("tests/sim_09_grasp_evaluator/", "30_simulation/sim_09_grasp_evaluator/tests/"),
    ("results/sim_09_grasp_evaluator/", "30_simulation/sim_09_grasp_evaluator/results/"),
    ("figures/sim_09_grasp_evaluator/", "30_simulation/sim_09_grasp_evaluator/figures/"),
    ("tables/sim_09_grasp_evaluator/", "30_simulation/sim_09_grasp_evaluator/tables/"),
    ("src/visualization/", "70_tools/project_visualization/src/"),
    ("tests/visualization/", "70_tools/project_visualization/tests/"),
    ("figures/visualization/", "40_evidence/artifacts/visualization/figures/"),
    ("tables/visualization/", "40_evidence/artifacts/visualization/tables/"),
    ("videos/visualization/", "40_evidence/artifacts/visualization/videos/"),
    ("docs/00_project_governance/", "01_project/governance/"),
    ("docs/90_competition/", "01_project/competition/"),
    ("docs/95_inbox/", "01_project/inbox/"),
    ("docs/00_references/", "50_literature/references/"),
    ("docs/20_system_design/", "20_engineering/system_design/"),
    ("docs/stage1_spacecraft_layout/", "20_engineering/stage1_spacecraft_layout/"),
    ("e15_ancf_certification/", "30_simulation/e15_ancf_certification/"),
    ("e15_core_coverage/", "30_simulation/e15_core_coverage/"),
    ("e16_sync_capture/", "30_simulation/e16_sync_capture/"),
    ("knowledge_base/", "10_research/knowledge_base/"),
    ("artifacts/", "40_evidence/artifacts/"),
    ("research/", "10_research/"),
    ("tools/", "70_tools/"),
    ("external/", "80_third_party/external/"),
    ("vendor/", "80_third_party/vendor/"),
    ("pdf/", "50_literature/pdf/"),
    ("cad/", "20_engineering/cad/"),
    ("sim/", "30_simulation/"),
]

CONFIG_PREFIX_MAP = [
    (f"config/{name}/", f"20_engineering/config/{name}/")
    for name in (
        "attitude_stab", "control_scene", "coupled_scene", "geometry",
        "grasp_evaluator", "mission_feasibility", "safety_gate",
        "strategy_feasibility", "visualization",
    )
]

SPECIAL_EXACT = {
    "空间机械臂.docx": "01_project/inbox/source_documents/空间机械臂.docx",
    "补充论文/README.md": "50_literature/legacy_supplemental/README.md",
}

GENERATED_DUPLICATE_MAP = [
    ('"config\\\\coupled_scene\\\\', '"20_engineering\\\\config\\\\coupled_scene\\\\'),
    ('"config/safety_gate"', '"20_engineering/config/safety_gate"'),
    ("assembly_research/ASM-00_interface_ssot/", "30_simulation/asm_00_interface_preflight/"),
    ("assembly_research/asm_00_interface_preflight/", "30_simulation/asm_00_interface_preflight/"),
    ("assembly_10_research/ASM-00_interface_ssot/", "30_simulation/asm_00_interface_preflight/"),
    ("assembly_10_research/ASM-01_contact_dynamics/", "30_simulation/asm_01_contact_dynamics/"),
    ("assembly_10_research/ASM-02_phased_control/", "30_simulation/asm_02_phased_control/"),
    ("assembly_10_research/ASM-06_ground_validation/", "30_simulation/asm_06_ground_validation/"),
    ("assembly_10_research/waveA_results/", "40_evidence/artifacts/on_orbit_assembly/waveA_results/"),
    ("assembly_10_research/", "30_simulation/"),
    ("01_project/inbox/source_documents/01_project/inbox/source_documents/", "01_project/inbox/source_documents/"),
    ("10_10_research/", "10_research/"),
    ("10_research/10_research/", "10_research/"),
    ("20_engineering/20_engineering/", "20_engineering/"),
    ("30_simulation/30_simulation/", "30_simulation/"),
    ("40_evidence/40_evidence/", "40_evidence/"),
    ("50_literature/50_literature/", "50_literature/"),
    ("70_70_tools/", "70_tools/"),
    ("70_tools/70_tools/", "70_tools/"),
    ("80_third_party/80_third_party/", "80_third_party/"),
]


def normalize_rel(value: str) -> str:
    value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return str(PurePosixPath(value)) if value else value


def map_old_rel_to_new(value: str) -> str:
    value = normalize_rel(value)
    if value in SPECIAL_EXACT:
        return SPECIAL_EXACT[value]
    if value.startswith("tables/") and value.count("/") == 1:
        name = value.split("/", 1)[1]
        if name in GLOBAL_TABLES:
            return f"40_evidence/tables/{name}"
    for old, new in PREFIX_MAP + CONFIG_PREFIX_MAP:
        old_base = old.rstrip("/")
        new_base = new.rstrip("/")
        if value == old_base:
            return new_base
        if value.startswith(old):
            return new + value[len(old):]
    exact_dirs = {
        "docs/00_project_governance": "01_project/governance",
        "docs/90_competition": "01_project/competition",
        "docs/95_inbox": "01_project/inbox",
        "docs/00_references": "50_literature/references",
        "docs/20_system_design": "20_engineering/system_design",
        "docs/stage1_spacecraft_layout": "20_engineering/stage1_spacecraft_layout",
        "config": "20_engineering/config",
        "cad": "20_engineering/cad",
        "research": "10_research",
        "sim": "30_simulation",
        "artifacts": "40_evidence/artifacts",
        "pdf": "50_literature/pdf",
        "tools": "70_tools",
        "external": "80_third_party/external",
        "vendor": "80_third_party/vendor",
        "knowledge_base": "10_research/knowledge_base",
        "tables": "40_evidence/tables",
    }
    return exact_dirs.get(value, value)


def map_new_source_to_old(value: str) -> str:
    value = normalize_rel(value)
    if value == "30_simulation/asm_00_interface_preflight/MIGRATION_NOTICE.md":
        return "sim/asm_00_interface_preflight/README.md"
    if value.startswith("30_simulation/asm_00_interface_preflight/"):
        return "assembly_research/ASM-00_interface_ssot/" + value.split("/", 2)[2]
    special = [
        ("10_research/knowledge_base/", "knowledge_base/"),
        ("30_simulation/sim_09_grasp_evaluator/src/", "src/sim_09_grasp_evaluator/"),
        ("30_simulation/sim_09_grasp_evaluator/tests/", "tests/sim_09_grasp_evaluator/"),
        ("30_simulation/sim_09_grasp_evaluator/results/", "results/sim_09_grasp_evaluator/"),
        ("30_simulation/sim_09_grasp_evaluator/figures/", "figures/sim_09_grasp_evaluator/"),
        ("30_simulation/sim_09_grasp_evaluator/tables/", "tables/sim_09_grasp_evaluator/"),
        ("40_evidence/artifacts/visualization/figures/", "figures/visualization/"),
        ("40_evidence/artifacts/visualization/tables/", "tables/visualization/"),
        ("40_evidence/artifacts/visualization/videos/", "videos/visualization/"),
        ("70_tools/project_visualization/src/", "src/visualization/"),
        ("70_tools/project_visualization/tests/", "tests/visualization/"),
        ("01_project/governance/", "docs/00_project_governance/"),
        ("01_project/competition/", "docs/90_competition/"),
        ("01_project/inbox/", "docs/95_inbox/"),
        ("50_literature/references/", "docs/00_references/"),
        ("20_engineering/system_design/", "docs/20_system_design/"),
        ("20_engineering/stage1_spacecraft_layout/", "docs/stage1_spacecraft_layout/"),
        ("30_simulation/e15_ancf_certification/", "e15_ancf_certification/"),
        ("30_simulation/e15_core_coverage/", "e15_core_coverage/"),
        ("30_simulation/e16_sync_capture/", "e16_sync_capture/"),
        ("40_evidence/artifacts/", "artifacts/"),
        ("40_evidence/tables/", "tables/"),
        ("50_literature/pdf/", "pdf/"),
        ("50_literature/legacy_supplemental/", "补充论文/"),
        ("80_third_party/external/", "external/"),
        ("80_third_party/vendor/", "vendor/"),
        ("20_engineering/cad/", "cad/"),
        ("20_engineering/config/", "config/"),
        ("10_research/", "research/"),
        ("30_simulation/", "sim/"),
        ("70_tools/", "tools/"),
    ]
    for new, old in special:
        if value.startswith(new):
            return old + value[len(new):]
    if value == "01_project/inbox/source_documents/空间机械臂.docx":
        return "空间机械臂.docx"
    return value


def is_historical(rel: str) -> bool:
    if rel.startswith("01_project/competition/archive/"):
        return True
    if rel.startswith("01_project/governance/"):
        name = PurePosixPath(rel).name.lower()
        if name.startswith(("reorg02", "reorg03", "reorg04_directory_mapping", "reorg04_move", "reorg04_rewrite_paths")):
            return True
    return False


def split_target(raw: str) -> tuple[str, str, bool]:
    raw = raw.strip()
    if raw.startswith("<"):
        end = raw.find(">")
        if end >= 0:
            return raw[1:end], raw[end + 1 :], True
    match = re.match(r"([^\s]+)(.*)$", raw, flags=re.S)
    if not match:
        return raw, "", False
    return match.group(1), match.group(2), False


def rewrite_markdown_links(text: str, current_rel: str, root: Path) -> tuple[str, int]:
    old_source_rel = map_new_source_to_old(current_rel)
    old_source = root / Path(old_source_rel)
    new_source = root / Path(current_rel)
    pattern = re.compile(r"(!?\[[^\]\n]*\]\()([^\)\n]+)(\))")
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        target, suffix, was_angle = split_target(match.group(2))
        lower = target.lower()
        if (
            not target
            or target.startswith("#")
            or lower.startswith(("http://", "https://", "mailto:", "data:", "javascript:", "tel:"))
        ):
            return match.group(0)

        path_part = target
        fragment = ""
        query = ""
        if "#" in path_part:
            path_part, fragment_value = path_part.split("#", 1)
            fragment = "#" + fragment_value
        if "?" in path_part:
            path_part, query_value = path_part.split("?", 1)
            query = "?" + query_value
        decoded = unquote(path_part).replace("\\", "/")
        if not decoded:
            return match.group(0)

        windows_abs = bool(re.match(r"^[A-Za-z]:/", decoded))
        if windows_abs:
            old_target_abs = Path(decoded)
        elif decoded.startswith("/"):
            old_target_abs = root / decoded.lstrip("/")
        else:
            old_target_abs = Path(os.path.normpath(str(old_source.parent / decoded)))

        try:
            old_target_rel = old_target_abs.relative_to(root).as_posix()
        except ValueError:
            return match.group(0)

        new_target_rel = map_old_rel_to_new(old_target_rel)
        new_target_abs = root / Path(new_target_rel)
        if windows_abs:
            new_path = new_target_abs.as_posix()
        else:
            new_path = os.path.relpath(new_target_abs, new_source.parent).replace("\\", "/")
            if new_path == ".":
                new_path = "./"
            elif not new_path.startswith("."):
                new_path = "./" + new_path
        if decoded.endswith("/") and not new_path.endswith("/"):
            new_path += "/"
        rebuilt_target = new_path + query + fragment
        rendered = f"<{rebuilt_target}>" if was_angle or " " in rebuilt_target else rebuilt_target
        replacement = match.group(1) + rendered + suffix + match.group(3)
        if replacement != match.group(0):
            count += 1
        return replacement

    return pattern.sub(replace, text), count


def replace_outside_urls(
    text: str,
    old: str,
    new: str,
    protected_prefix: str = "",
) -> tuple[str, int]:
    start = 0
    pieces: list[str] = []
    count = 0
    while True:
        index = text.find(old, start)
        if index < 0:
            pieces.append(text[start:])
            break
        token_start = index
        while token_start > 0 and text[token_start - 1] not in " \t\r\n\"'`<>()[]{}":
            token_start -= 1
        token_prefix = text[token_start:index]
        pieces.append(text[start:index])
        if "://" in token_prefix or (
            protected_prefix and token_prefix.endswith(protected_prefix)
        ):
            pieces.append(old)
        else:
            pieces.append(new)
            count += 1
        start = index + len(old)
    return "".join(pieces), count


def generic_rewrite(text: str) -> tuple[str, int]:
    count = 0
    mappings = list(PREFIX_MAP) + list(CONFIG_PREFIX_MAP)
    for name in sorted(GLOBAL_TABLES):
        mappings.insert(0, (f"tables/{name}", f"40_evidence/tables/{name}"))
    mappings.insert(0, ("补充论文/README.md", "50_literature/legacy_supplemental/README.md"))
    mappings.insert(0, ("空间机械臂.docx", "01_project/inbox/source_documents/空间机械臂.docx"))
    # Use placeholders so a newly generated path cannot be matched again by a
    # later rule (for example, ``src/visualization`` -> ``70_tools/...`` must
    # not subsequently trigger the generic ``tools/`` rule).
    replacements: list[tuple[str, str]] = []
    for index, (old, new) in enumerate(mappings):
        protected_prefix = ""
        embedded_at = new.find(old)
        if embedded_at > 0:
            protected_prefix = new[:embedded_at]
        placeholder = f"__REORG04_PATH_{index:04d}_FWD__"
        text, delta = replace_outside_urls(
            text, old, placeholder, protected_prefix=protected_prefix
        )
        count += delta
        if delta:
            replacements.append((placeholder, new))

        old_back = old.replace("/", "\\")
        new_back = new.replace("/", "\\")
        protected_prefix_back = protected_prefix.replace("/", "\\")
        placeholder_back = f"__REORG04_PATH_{index:04d}_BACK__"
        text, delta = replace_outside_urls(
            text,
            old_back,
            placeholder_back,
            protected_prefix=protected_prefix_back,
        )
        count += delta
        if delta:
            replacements.append((placeholder_back, new_back))

    for placeholder, replacement in replacements:
        text = text.replace(placeholder, replacement)
    return text, count


def repair_generated_duplicates(text: str) -> tuple[str, int]:
    count = 0
    for old, new in GENERATED_DUPLICATE_MAP:
        delta = text.count(old)
        if delta:
            text = text.replace(old, new)
            count += delta
        old_back = old.replace("/", "\\")
        new_back = new.replace("/", "\\")
        delta = text.count(old_back)
        if delta:
            text = text.replace(old_back, new_back)
            count += delta
    return text, count


def read_text_preserve(path: Path) -> tuple[str, str] | None:
    data = path.read_bytes()
    if b"\x00" in data:
        return None
    encoding = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            return handle.read(), encoding
    except UnicodeDecodeError:
        return None


def write_text_preserve(path: Path, text: str, encoding: str) -> None:
    with path.open("w", encoding=encoding, newline="") as handle:
        handle.write(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--repair-generated-duplicates", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    log_path = Path(args.log).resolve()
    changes: list[dict[str, str | int]] = []
    skipped_non_utf8: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = PurePosixPath(rel).parts
        if not parts:
            continue
        if parts[0] in {".git", "80_third_party"}:
            continue
        if args.repair_generated_duplicates and rel.startswith(
            "01_project/governance/reorg04_"
        ):
            continue
        if rel.startswith("50_literature/pdf/"):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        loaded = read_text_preserve(path)
        if loaded is None:
            skipped_non_utf8.append(rel)
            continue
        text, encoding = loaded
        before = text
        link_count = 0
        generic_count = 0
        if args.repair_generated_duplicates:
            text, generic_count = repair_generated_duplicates(text)
        else:
            if path.suffix.lower() == ".md":
                text, link_count = rewrite_markdown_links(text, rel, root)
            if not is_historical(rel):
                text, generic_count = generic_rewrite(text)
        if text == before:
            continue
        before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        write_text_preserve(path, text, encoding)
        after_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        changes.append(
            {
                "path": rel,
                "old_path": map_new_source_to_old(rel),
                "markdown_links_rewritten": link_count,
                "path_tokens_rewritten": generic_count,
                "before_sha256": before_hash,
                "after_sha256": after_hash,
            }
        )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path", "old_path", "markdown_links_rewritten", "path_tokens_rewritten",
                "before_sha256", "after_sha256",
            ],
        )
        writer.writeheader()
        writer.writerows(changes)

    print(f"REWRITE_FILES={len(changes)}")
    print(f"MARKDOWN_LINKS_REWRITTEN={sum(int(row['markdown_links_rewritten']) for row in changes)}")
    print(f"PATH_TOKENS_REWRITTEN={sum(int(row['path_tokens_rewritten']) for row in changes)}")
    print(f"SKIPPED_NON_UTF8={len(skipped_non_utf8)}")
    for rel in skipped_non_utf8:
        print(f"SKIPPED={rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
