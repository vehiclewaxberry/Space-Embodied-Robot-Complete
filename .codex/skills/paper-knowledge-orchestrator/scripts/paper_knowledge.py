#!/usr/bin/env python3
"""Build and validate the project's derived paper-knowledge control layer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc


TOOL_VERSION = "1.0.0"
MANIFEST_REL = Path("50_literature/references/manifest.yaml")
REFS_BIB_REL = Path("50_literature/references/refs.bib")
NOTES_DIR_REL = Path("50_literature/references/notes")
NOTES_INDEX_REL = NOTES_DIR_REL / "INDEX.md"
PAPERS_DIR_REL = Path("10_research/knowledge_base/papers")
PAPER_INDEX_REL = PAPERS_DIR_REL / "paper_index.csv"
STATE_REL = PAPERS_DIR_REL / "controller_state.yaml"
QUEUE_REL = PAPERS_DIR_REL / "reading_queue.md"
CLAIM_LEDGER_REL = PAPERS_DIR_REL / "claim_evidence_ledger.csv"
VALIDATION_REPORT_REL = PAPERS_DIR_REL / "controller_validation.json"

INDEX_FIELDS = [
    "bibkey",
    "year",
    "category",
    "mission_line",
    "priority",
    "doi_status",
    "local_pdf",
    "reading_card",
]

CLAIM_LEDGER_FIELDS = [
    "claim_id",
    "claim_text",
    "claim_scope",
    "literature_keys",
    "literature_locators",
    "project_gate_json",
    "project_result_file",
    "figure",
    "commit",
    "confidence",
    "allowed_wording",
    "forbidden_wording",
    "status",
    "reviewed_on",
]

CARD_MARKERS = [
    "## 一句话结论",
    "## 与本项目的挂钩",
    "## 可复用内容",
    "## 边界与不适用条件",
    "## 不能据此声称什么",
]

LOCATOR_PATTERN = re.compile(
    r"第\s*\d+\s*页|p{1,2}\.\s*\d+|(?:Table|Fig(?:ure)?\.?)\s*\d+|式\s*\(?\d+",
    re.IGNORECASE,
)

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
MISSION_LINE_ORDER = ["debris_removal", "on_orbit_assembly", "both", "platform_common"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def resolve_root(value: str | None) -> Path:
    if value:
        root = Path(value).resolve()
    else:
        root = Path(__file__).resolve().parents[4]
    if not (root / MANIFEST_REL).is_file():
        raise SystemExit(f"Repository root not recognized: missing {MANIFEST_REL} under {root}")
    return root


def load_manifest(root: Path) -> dict[str, Any]:
    data = yaml.safe_load((root / MANIFEST_REL).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("papers"), list):
        raise SystemExit("Invalid manifest: expected a mapping with a papers list")
    return data


def claim_ledger_row_count(root: Path) -> int:
    path = root / CLAIM_LEDGER_REL
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def build_entries(root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for order, paper in enumerate(manifest["papers"], start=1):
        key = str(paper.get("key", "")).strip()
        local_pdf_rel = str(paper.get("local_pdf") or "")
        local_pdf_path = root / local_pdf_rel if local_pdf_rel else None
        local_pdf_present = bool(local_pdf_path and local_pdf_path.is_file())
        card_path = root / NOTES_DIR_REL / f"{key}.md"
        card_present = card_path.is_file()

        if card_present:
            reading_status = "READING_CARD_COMPLETE"
            next_action = "REUSE_CARD_AND_RECHECK_LOCATORS_FOR_ACTIVE_CLAIM"
        elif local_pdf_present:
            reading_status = "PDF_READY_FOR_READING"
            next_action = "DEEP_READ_AND_CREATE_CARD"
        elif local_pdf_rel:
            reading_status = "BLOCKED_REGISTERED_PDF_MISSING"
            next_action = "RESTORE_OR_ADJUDICATE_REGISTERED_PDF"
        else:
            reading_status = "BLOCKED_NO_LOCAL_PDF"
            next_action = "ACQUIRE_FULLTEXT_UNDER_SOURCE_POLICY"

        entries.append(
            {
                "manifest_order": order,
                "bibkey": key,
                "title": paper.get("title", ""),
                "year": paper.get("year", ""),
                "category": paper.get("category", ""),
                "section": paper.get("section", ""),
                "mission_line": paper.get("mission_line", ""),
                "grade": paper.get("grade", ""),
                "priority": paper.get("priority", ""),
                "reading_mode": paper.get("reading_mode", []),
                "doi": paper.get("doi", ""),
                "doi_status": paper.get("doi_status", ""),
                "archive_status": paper.get("archive_status", ""),
                "manifest_pdf_validation": paper.get("pdf_validation", ""),
                "local_pdf": local_pdf_rel,
                "local_pdf_status": "PRESENT" if local_pdf_present else "ABSENT",
                "reading_card": relative_posix(card_path, root) if card_present else "",
                "reading_status": reading_status,
                "next_action": next_action,
                "why_from_manifest": paper.get("why", ""),
                "figure_role_from_manifest": paper.get("figure_role", ""),
            }
        )
    return entries


def ordered_counter(values: list[str], preferred_order: list[str] | None = None) -> dict[str, int]:
    counts = Counter(values)
    result: dict[str, int] = {}
    for key in preferred_order or []:
        if key in counts:
            result[key] = counts.pop(key)
    for key in sorted(counts):
        result[key] = counts[key]
    return result


def render_paper_index(entries: list[dict[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=INDEX_FIELDS, lineterminator="\n")
    writer.writeheader()
    for entry in entries:
        writer.writerow(
            {
                "bibkey": entry["bibkey"],
                "year": entry["year"],
                "category": entry["category"],
                "mission_line": entry["mission_line"],
                "priority": entry["priority"],
                "doi_status": entry["doi_status"],
                "local_pdf": entry["local_pdf"],
                "reading_card": entry["reading_card"],
            }
        )
    return stream.getvalue()


def render_state(root: Path, manifest: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    manifest_path = root / MANIFEST_REL
    refs_bib_path = root / REFS_BIB_REL
    notes_index_path = root / NOTES_INDEX_REL

    reading_counts = ordered_counter([str(entry["reading_status"]) for entry in entries])
    doi_counts = ordered_counter(
        [str(entry["doi_status"]) or "NO_PRIMARY_DOI_STATUS" for entry in entries]
    )
    mission_counts = ordered_counter(
        [str(entry["mission_line"]) for entry in entries], MISSION_LINE_ORDER
    )
    blockers = [
        {
            "bibkey": entry["bibkey"],
            "status": entry["reading_status"],
            "next_action": entry["next_action"],
        }
        for entry in entries
        if str(entry["reading_status"]).startswith("BLOCKED_")
    ]

    state = {
        "schema_version": 1,
        "controller": "paper-knowledge-orchestrator",
        "controller_version": TOOL_VERSION,
        "authority": "DERIVED_NAVIGATION_ONLY",
        "verdict": "PAPER_KNOWLEDGE_STATE_BUILT",
        "generated_on": str(manifest.get("generated", "")),
        "integrity_scope": "MANIFEST_METADATA_CARD_STRUCTURE_AND_FILE_PRESENCE; PDF_SHA256_REQUIRES_VALIDATE_FLAG",
        "sources": {
            "manifest": MANIFEST_REL.as_posix(),
            "manifest_sha256": sha256_file(manifest_path),
            "refs_bib": REFS_BIB_REL.as_posix(),
            "refs_bib_sha256": sha256_file(refs_bib_path) if refs_bib_path.is_file() else "MISSING",
            "notes_index": NOTES_INDEX_REL.as_posix(),
            "notes_index_sha256": sha256_file(notes_index_path) if notes_index_path.is_file() else "MISSING",
            "latest_validation_report": VALIDATION_REPORT_REL.as_posix(),
        },
        "counts": {
            "manifest_entries": len(entries),
            "local_pdf_registered": sum(bool(entry["local_pdf"]) for entry in entries),
            "local_pdf_present": sum(entry["local_pdf_status"] == "PRESENT" for entry in entries),
            "reading_cards_complete": sum(
                entry["reading_status"] == "READING_CARD_COMPLETE" for entry in entries
            ),
            "pdf_ready_for_reading": sum(
                entry["reading_status"] == "PDF_READY_FOR_READING" for entry in entries
            ),
            "blocked_no_fulltext": len(blockers),
            "claim_evidence_rows": claim_ledger_row_count(root),
            "reading_status": reading_counts,
            "doi_status": doi_counts,
            "mission_line": mission_counts,
        },
        "blockers": blockers,
        "entries": entries,
    }
    return yaml.safe_dump(state, allow_unicode=True, sort_keys=False, width=120)


def md_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_queue(manifest: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    ready = [entry for entry in entries if entry["reading_status"] == "PDF_READY_FOR_READING"]
    ready.sort(key=lambda item: (PRIORITY_ORDER.get(str(item["priority"]), 99), item["manifest_order"]))
    blocked = [entry for entry in entries if str(entry["reading_status"]).startswith("BLOCKED_")]

    lines = [
        "# 论文阅读总控队列",
        "",
        "> 状态：`DERIVED_NAVIGATION_ONLY`。本文件由 `paper_knowledge.py build` 从 manifest、在盘 PDF 和 canonical 阅读卡机械生成；不得反向覆盖真值源。",
        "",
        "## 当前快照",
        "",
        f"- manifest 题录：**{len(entries)}**",
        f"- 完整阅读卡：**{sum(entry['reading_status'] == 'READING_CARD_COMPLETE' for entry in entries)}**",
        f"- PDF 在盘且待精读：**{len(ready)}**",
        f"- 缺全文或本地文件异常：**{len(blocked)}**",
        f"- manifest 快照日期：`{manifest.get('generated', '')}`",
        "",
        "## 选篇规则",
        "",
        "1. 先由当前研究问题选择类别和 mission_line，再比较 manifest 的 priority；不要把列表首项当成永久唯一优先项。",
        "2. 同一 priority 保持 manifest 原始顺序，不额外制造科学排序。",
        "3. 精读前对拍本地 PDF SHA-256；完成后按 canonical 模板落阅读卡并重新生成本文件。",
        "4. `why` 是 manifest 中的阅读动机，不是论文已经成立的结论。",
        "",
        "## 可立即精读",
        "",
    ]

    for priority in sorted({str(entry["priority"]) for entry in ready}, key=lambda p: PRIORITY_ORDER.get(p, 99)):
        group = [entry for entry in ready if str(entry["priority"]) == priority]
        lines.extend(
            [
                f"### {priority}（{len(group)} 篇）",
                "",
                "| manifest序号 | bibkey | 层级/类别 | mission_line | manifest 阅读动机 | PDF |",
                "|---:|---|---|---|---|---|",
            ]
        )
        for entry in group:
            lines.append(
                "| {order} | `{key}` | {section}/{category} | `{mission}` | {why} | `{pdf}` |".format(
                    order=entry["manifest_order"],
                    key=md_cell(entry["bibkey"]),
                    section=md_cell(entry["section"]),
                    category=md_cell(entry["category"]),
                    mission=md_cell(entry["mission_line"]),
                    why=md_cell(entry["why_from_manifest"]),
                    pdf=md_cell(entry["local_pdf"]),
                )
            )
        lines.append("")

    lines.extend(["## 阻塞项", ""])
    if not blocked:
        lines.append("无。")
    else:
        lines.extend(
            [
                "| bibkey | 状态 | DOI 状态 | 下一步 |",
                "|---|---|---|---|",
            ]
        )
        for entry in blocked:
            lines.append(
                f"| `{md_cell(entry['bibkey'])}` | `{md_cell(entry['reading_status'])}` | "
                f"`{md_cell(entry['doi_status'])}` | `{md_cell(entry['next_action'])}` |"
            )
    lines.extend(
        [
            "",
            "## 总控调用",
            "",
            "- 状态核验：`$paper-knowledge-orchestrator` + `STATE_AUDIT`",
            "- 指定精读：`$paper-knowledge-orchestrator` + bibkey + 当前研究问题",
            "- 横向综合：`$paper-knowledge-orchestrator` + bibkey 集合 + 明确的 synthesis question",
            "",
        ]
    )
    return "\n".join(lines)


def write_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def expected_outputs(root: Path, manifest: dict[str, Any], entries: list[dict[str, Any]]) -> dict[Path, str]:
    return {
        root / PAPER_INDEX_REL: render_paper_index(entries),
        root / STATE_REL: render_state(root, manifest, entries),
        root / QUEUE_REL: render_queue(manifest, entries),
    }


def build(root: Path) -> int:
    manifest = load_manifest(root)
    entries = build_entries(root, manifest)
    changed: list[str] = []
    for path, content in expected_outputs(root, manifest, entries).items():
        if write_if_changed(path, content):
            changed.append(relative_posix(path, root))

    result = {
        "verdict": "PAPER_KNOWLEDGE_STATE_BUILT",
        "manifest_entries": len(entries),
        "local_pdf_present": sum(entry["local_pdf_status"] == "PRESENT" for entry in entries),
        "reading_cards_complete": sum(
            entry["reading_status"] == "READING_CARD_COMPLETE" for entry in entries
        ),
        "pdf_ready_for_reading": sum(
            entry["reading_status"] == "PDF_READY_FOR_READING" for entry in entries
        ),
        "blocked_no_fulltext": sum(str(entry["reading_status"]).startswith("BLOCKED_") for entry in entries),
        "changed_files": changed,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def validate(root: Path, verify_pdf_sha256: bool, write_report: bool) -> int:
    manifest = load_manifest(root)
    entries = build_entries(root, manifest)
    errors: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    keys = [entry["bibkey"] for entry in entries]

    if not all(keys):
        errors.append("manifest contains an empty bibkey")
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate bibkeys: {', '.join(duplicates)}")

    declared_counts = manifest.get("counts") or {}
    if declared_counts.get("papers") != len(entries):
        errors.append(f"manifest counts.papers={declared_counts.get('papers')} but actual={len(entries)}")
    registered_pdf_count = sum(bool(entry["local_pdf"]) for entry in entries)
    if declared_counts.get("pdf_local_validated_total") != registered_pdf_count:
        errors.append(
            "manifest counts.pdf_local_validated_total="
            f"{declared_counts.get('pdf_local_validated_total')} but registered local_pdf={registered_pdf_count}"
        )

    manifest_papers = {str(paper.get("key", "")): paper for paper in manifest["papers"]}
    sha_checked = 0
    for entry in entries:
        key = entry["bibkey"]
        paper = manifest_papers[key]
        local_pdf_rel = entry["local_pdf"]
        if not local_pdf_rel:
            blockers.append(f"{key}: BLOCKED_NO_LOCAL_PDF")
        else:
            pdf_path = (root / local_pdf_rel).resolve()
            try:
                pdf_path.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{key}: local_pdf escapes repository root: {local_pdf_rel}")
                continue
            if not pdf_path.is_file():
                errors.append(f"{key}: registered local_pdf missing: {local_pdf_rel}")
                continue
            if verify_pdf_sha256:
                expected_sha = str(paper.get("pdf_sha256") or "").lower()
                if not expected_sha:
                    errors.append(f"{key}: pdf_sha256 missing from manifest")
                else:
                    actual_sha = sha256_file(pdf_path)
                    sha_checked += 1
                    if actual_sha.lower() != expected_sha:
                        errors.append(
                            f"{key}: SHA-256 mismatch expected={expected_sha} actual={actual_sha.lower()}"
                        )

        card_rel = entry["reading_card"]
        if card_rel:
            card_path = root / card_rel
            text = card_path.read_text(encoding="utf-8")
            if key not in text.splitlines()[0]:
                errors.append(f"{key}: card title line does not contain bibkey")
            for marker in CARD_MARKERS:
                if marker not in text:
                    errors.append(f"{key}: card missing required marker: {marker}")
            if not LOCATOR_PATTERN.search(text):
                errors.append(f"{key}: card has no page/equation/figure/table locator")
            doi = str(entry["doi"] or "")
            if doi and doi.lower() not in text.lower():
                warnings.append(f"{key}: DOI is not repeated in the card")

    known_note_names = {f"{key}.md" for key in keys} | {"INDEX.md"}
    orphan_cards = sorted(
        path.name
        for path in (root / NOTES_DIR_REL).glob("*.md")
        if path.name not in known_note_names
    )
    if orphan_cards:
        warnings.append(f"unmatched note files: {', '.join(orphan_cards)}")

    for path, expected in expected_outputs(root, manifest, entries).items():
        if not path.is_file():
            errors.append(f"derived output missing: {relative_posix(path, root)}")
        elif path.read_text(encoding="utf-8") != expected:
            errors.append(f"derived output stale: {relative_posix(path, root)}")

    ledger_path = root / CLAIM_LEDGER_REL
    if not ledger_path.is_file():
        errors.append(f"claim-evidence ledger missing: {CLAIM_LEDGER_REL.as_posix()}")
    else:
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
        if header != CLAIM_LEDGER_FIELDS:
            errors.append("claim-evidence ledger header does not match the controller contract")

    if not (root / REFS_BIB_REL).is_file():
        errors.append(f"bibliography SSOT missing: {REFS_BIB_REL.as_posix()}")

    verdict = "PAPER_KNOWLEDGE_READY" if not errors else "PAPER_KNOWLEDGE_INTEGRITY_FAILED"
    result = {
        "verdict": verdict,
        "controller_version": TOOL_VERSION,
        "validated_on": date.today().isoformat(),
        "validation_scope": "FULL_PDF_SHA256" if verify_pdf_sha256 else "METADATA_CARD_STRUCTURE_AND_FILE_PRESENCE",
        "source_manifest_sha256": sha256_file(root / MANIFEST_REL),
        "manifest_entries": len(entries),
        "local_pdf_present": sum(entry["local_pdf_status"] == "PRESENT" for entry in entries),
        "reading_cards_complete": sum(
            entry["reading_status"] == "READING_CARD_COMPLETE" for entry in entries
        ),
        "pdf_ready_for_reading": sum(
            entry["reading_status"] == "PDF_READY_FOR_READING" for entry in entries
        ),
        "blocked_no_fulltext": len(blockers),
        "pdf_sha256_checked": sha_checked,
        "errors": errors,
        "warnings": warnings,
        "blockers": blockers,
    }
    if write_report:
        result["report_path"] = VALIDATION_REPORT_REL.as_posix()
        write_if_changed(
            root / VALIDATION_REPORT_REL,
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or validate the derived literature knowledge controller state."
    )
    parser.add_argument("command", choices=["build", "validate"])
    parser.add_argument("--repo-root", help="Repository root; defaults to the skill's owning repository")
    parser.add_argument(
        "--verify-pdf-sha256",
        action="store_true",
        help="Recompute every registered local PDF SHA-256 during validation",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=f"Write the validation result to {VALIDATION_REPORT_REL.as_posix()}",
    )
    args = parser.parse_args(argv)
    if args.command != "validate" and (args.verify_pdf_sha256 or args.write_report):
        parser.error("--verify-pdf-sha256 and --write-report are only valid with validate")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = resolve_root(args.repo_root)
    if args.command == "build":
        return build(root)
    return validate(root, args.verify_pdf_sha256, args.write_report)


if __name__ == "__main__":
    raise SystemExit(main())
