"""Strict verifier and deterministic builder for the competition replay.

This module only reads frozen evidence.  It does not import or run any physics,
control, or safety solver.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml


CONTRACT_SCHEMA = "competition-twin-evidence-v1"
SCENARIO_SCHEMA = "competition-demo-scenarios-v1"
REPLAY_SCHEMA = "competition-offline-replay-record-v1"
VERIFICATION_SCHEMA = "competition-evidence-verification-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_ARTIFACT_IDS = {
    "threshold_registry",
    "sim10_gate",
    "strategy_config",
    "sim12_gate",
    "sim12_results",
    "safe_policy",
    "safe_gate",
    "ctrl02_gate",
    "ctrl02_results",
}
EXPECTED_SCENARIOS = {"A_low", "B_anchor", "C_transition"}
EXPECTED_INTEGRATION_OWNED_PREFIXES = (
    "10_research/competition_convergence/",
    "30_simulation/asm_00_interface_preflight/",
    "40_evidence/artifacts/competition_convergence/",
)
EXPECTED_PREEXISTING_DIRTY_PATHS = {
    ".codex/AGENTS.md",
    ".codex/agents/physics-agent-architect.md",
    ".codex/skills/README.md",
    "CLAUDE.md",
    "01_project/competition/项目现状总览_20260720.md",
    "10_research/README.md",
    "10_research/control/attitude_stabilization_research_plan.md",
    "10_research/control/trajectory_control_research_plan.md",
    "10_research/paper1_architecture.md",
    "10_research/research_state_v4.md",
    "10_research/framework_convergence/active_mainline_dag.md",
    "10_research/framework_convergence/archive_action_plan.md",
    "10_research/framework_convergence/canonical_architecture.md",
    "10_research/framework_convergence/claim_evidence_matrix.csv",
    "10_research/framework_convergence/next_research_plan.md",
    "10_research/framework_convergence/next_wave_task_cards/NW-01_ASM-00_INTERFACE_QUALIFICATION.md",
    "10_research/framework_convergence/next_wave_task_cards/NW-02_ASM-01_CONTACT_DYNAMICS.md",
    "10_research/framework_convergence/next_wave_task_cards/NW-03_ASM-02_PHASED_CONTROL.md",
    "10_research/framework_convergence/next_wave_task_cards/NW-04_ASM-TWIN-00_OFFLINE_REPLAY.md",
    "10_research/framework_convergence/next_wave_task_cards/README.md",
    "10_research/framework_convergence/next_wave_task_cards/authorization_record_schema.yaml",
    "10_research/framework_convergence/numerical_twin_status.md",
    "10_research/framework_convergence/red_team_science.md",
    "10_research/framework_convergence/red_team_system.md",
    "10_research/framework_convergence/redundancy_audit.csv",
    "10_research/framework_convergence/state_truth_report.md",
    "10_research/framework_convergence/tool_stack_decision.md",
    "01_project/inbox/source_documents/空间机械臂.docx",
}
REQUIRED_WATERMARKS = {
    "OFFLINE EVIDENCE REPLAY",
    "NO REAL-TIME SYNCHRONIZATION",
    "NO COMMAND OUTPUT",
}
CLAIM_FIELDS = [
    "claim_id",
    "text",
    "scope",
    "gate_json",
    "scenario_hash",
    "result_csv",
    "figure",
    "commit",
    "confidence",
    "allowed_wording",
    "forbidden_wording",
]


class EvidenceError(RuntimeError):
    """Raised when evidence cannot be verified without upward reclassification."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(errors)
        super().__init__(" | ".join(self.errors))


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> Any:
    raise ValueError(f"non-finite JSON number: {token}")


def load_strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_nonfinite,
    )
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """PyYAML safe loader with duplicate-key rejection."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_strict_yaml(path: Path) -> dict[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    if not isinstance(value, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return value


def load_strict_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        if not fields or len(fields) != len(set(fields)):
            raise ValueError(f"CSV header missing or duplicated: {path}")
        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row {index} does not match header: {path}")
            rows.append(dict(row))
    return fields, rows


def canonical_csv_table_sha256(
    rows: list[dict[str, str]], key_fields: Iterable[str]
) -> str:
    keys = tuple(key_fields)
    if not keys:
        raise ValueError("CSV canonical hash requires key fields")
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(row[field] for field in keys)
        if key in seen:
            raise ValueError(f"duplicate CSV row key: {key}")
        seen.add(key)
    ordered = sorted(rows, key=lambda row: tuple(row[field] for field in keys))
    return object_sha256(ordered)


def _canonical_hash_from_git_blob(
    data: bytes, mode: str, key_fields: Iterable[str]
) -> str:
    """Hash Git blob meaning while tolerating checkout-only EOL conversion."""
    if mode == "RAW_BYTES_SHA256":
        return hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8")
    if mode == "CANONICAL_JSON_SHA256_V1":
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
        )
        return object_sha256(value)
    if mode == "CANONICAL_YAML_SHA256_V1":
        value = yaml.load(text, Loader=_UniqueKeySafeLoader)
        return object_sha256(value)
    if mode == "CANONICAL_CSV_TABLE_SHA256_V1":
        reader = csv.DictReader(io.StringIO(text, newline=""))
        fields = list(reader.fieldnames or [])
        if not fields or len(fields) != len(set(fields)):
            raise ValueError("Git CSV blob header missing or duplicated")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Git CSV blob row does not match header")
            rows.append(dict(row))
        return canonical_csv_table_sha256(rows, key_fields)
    raise ValueError(f"unsupported Git blob hash mode: {mode}")


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_repo_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"artifact path is not repo-relative: {relative}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact escapes repository: {relative}") from exc
    return resolved


def _get_path(value: Any, dotted_path: str) -> Any:
    current = value
    for token in dotted_path.split("."):
        if not isinstance(current, dict) or token not in current:
            raise KeyError(dotted_path)
        current = current[token]
    return current


def _one_row(
    rows: list[dict[str, str]], key: dict[str, Any], context: str
) -> dict[str, str]:
    expected = {field: str(value) for field, value in key.items()}
    matches = [
        row for row in rows
        if all(row.get(field) == value for field, value in expected.items())
    ]
    if len(matches) != 1:
        raise ValueError(f"{context}: expected one row, found {len(matches)}")
    return matches[0]


def _one_object(
    values: list[dict[str, Any]], match: dict[str, Any], context: str
) -> dict[str, Any]:
    matches = [
        value for value in values
        if all(value.get(field) == expected for field, expected in match.items())
    ]
    if len(matches) != 1:
        raise ValueError(f"{context}: expected one object, found {len(matches)}")
    return matches[0]


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _required_values(
    actual: dict[str, Any],
    expected: dict[str, Any],
    context: str,
    errors: list[str],
) -> None:
    for dotted_path, expected_value in expected.items():
        try:
            actual_value = _get_path(actual, dotted_path)
        except KeyError:
            errors.append(f"{context}: missing {dotted_path}")
            continue
        if actual_value != expected_value:
            errors.append(
                f"{context}: {dotted_path}={actual_value!r}, "
                f"expected {expected_value!r}"
            )


def _run_git(root: Path, args: list[str], binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", errors="strict")


def _verify_git_and_scope(
    contract: dict[str, Any],
    root: Path,
    artifacts: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    baseline = contract.get("baseline", {})
    base = baseline.get("approved_git_commit", "")
    owned_prefix = baseline.get("owned_path_prefix", "")
    declared_prefixes = baseline.get("integration_owned_prefixes", [])
    frozen_dirty = baseline.get("preexisting_dirty_fingerprints", {})
    _require(bool(COMMIT_RE.fullmatch(base)), "baseline commit is not SHA-40", errors)
    _require(
        owned_prefix == "10_research/competition_convergence/",
        "owned path prefix widened or changed",
        errors,
    )
    _require(
        tuple(declared_prefixes) == EXPECTED_INTEGRATION_OWNED_PREFIXES,
        "integration-owned path prefixes widened or changed",
        errors,
    )
    _require(
        isinstance(frozen_dirty, dict)
        and set(frozen_dirty) == EXPECTED_PREEXISTING_DIRTY_PATHS,
        "pre-existing dirty-path baseline differs from launch freeze",
        errors,
    )
    if not COMMIT_RE.fullmatch(base):
        return {"approved_git_commit": base, "base_is_ancestor": False}

    violations: list[str] = []
    dirty_snapshot_errors: list[str] = []
    try:
        _run_git(root, ["cat-file", "-e", f"{base}^{{commit}}"])
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, "HEAD"],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).returncode == 0
        _require(ancestor, "approved base is not an ancestor of HEAD", errors)

        for artifact_id, spec in artifacts.items():
            rel = spec["path"]
            mode = spec["hash_mode"]
            expected_blob_hash = (
                spec["raw_sha256"]
                if mode == "RAW_BYTES_SHA256"
                else spec["canonical_sha256"]
            )
            base_bytes = _run_git(root, ["show", f"{base}:{rel}"], binary=True)
            base_hash = _canonical_hash_from_git_blob(
                base_bytes, mode, spec.get("key_fields", [])
            )
            _require(
                base_hash == expected_blob_hash,
                f"{artifact_id}: approved-base blob hash mismatch",
                errors,
            )
            source_commit = spec.get("source_commit", "")
            _require(
                bool(COMMIT_RE.fullmatch(source_commit)),
                f"{artifact_id}: source_commit is not SHA-40",
                errors,
            )
            if COMMIT_RE.fullmatch(source_commit):
                source_bytes = _run_git(
                    root, ["show", f"{source_commit}:{rel}"], binary=True
                )
                source_hash = _canonical_hash_from_git_blob(
                    source_bytes, mode, spec.get("key_fields", [])
                )
                _require(
                    source_hash == expected_blob_hash,
                    f"{artifact_id}: source-commit blob hash mismatch",
                    errors,
                )

        changed = set(
            line.strip()
            for line in str(
                _run_git(root, ["diff", "--name-only", f"{base}..HEAD"])
            ).splitlines()
            if line.strip()
        )
        status_bytes = _run_git(
            root,
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            binary=True,
        )
        status_parts = status_bytes.split(b"\0")
        index = 0
        while index < len(status_parts) - 1:
            entry = status_parts[index]
            index += 1
            if not entry or len(entry) < 4:
                continue
            status = entry[:2].decode("ascii", errors="strict")
            path = entry[3:].decode("utf-8", errors="strict").replace("\\", "/")
            changed.add(path)
            if status[0] in "RC" or status[1] in "RC":
                if index >= len(status_parts) - 1:
                    raise ValueError("truncated rename/copy entry in git status")
                paired_path = (
                    status_parts[index]
                    .decode("utf-8", errors="strict")
                    .replace("\\", "/")
                )
                index += 1
                changed.add(paired_path)

        if isinstance(frozen_dirty, dict):
            for path, expected_hash in sorted(frozen_dirty.items()):
                if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(
                    expected_hash
                ):
                    dirty_snapshot_errors.append(
                        f"{path}: invalid frozen SHA-256"
                    )
                    continue
                try:
                    resolved = _resolve_repo_path(root, path)
                    if not resolved.is_file():
                        dirty_snapshot_errors.append(f"{path}: missing")
                    else:
                        actual_hash = raw_sha256(resolved)
                        if actual_hash != expected_hash:
                            dirty_snapshot_errors.append(
                                f"{path}: {actual_hash} != {expected_hash}"
                            )
                except ValueError as exc:
                    dirty_snapshot_errors.append(f"{path}: {exc}")
        _require(
            not dirty_snapshot_errors,
            f"pre-existing dirty snapshot drift: {dirty_snapshot_errors}",
            errors,
        )
        violations = sorted(
            path for path in changed
            if path
            and path not in EXPECTED_PREEXISTING_DIRTY_PATHS
            and not any(
                path.startswith(prefix)
                for prefix in EXPECTED_INTEGRATION_OWNED_PREFIXES
            )
        )
        _require(not violations, f"scope violations: {violations}", errors)
    except ValueError as exc:
        errors.append(str(exc))
        ancestor = False
        violations = ["GIT_CHECK_FAILED"]

    return {
        "approved_git_commit": base,
        "base_is_ancestor": ancestor,
        "scope_violations": violations,
        "integration_owned_prefixes": list(EXPECTED_INTEGRATION_OWNED_PREFIXES),
        "preexisting_dirty_snapshot_count": len(
            EXPECTED_PREEXISTING_DIRTY_PATHS
        ),
        "preexisting_dirty_snapshot_errors": dirty_snapshot_errors,
    }


def _verify_artifacts(
    contract: dict[str, Any], root: Path, errors: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    registry = contract.get("artifact_registry", {})
    _require(
        set(registry) == EXPECTED_ARTIFACT_IDS,
        f"artifact registry IDs differ: {sorted(set(registry) ^ EXPECTED_ARTIFACT_IDS)}",
        errors,
    )
    snapshots: dict[str, dict[str, Any]] = {}
    documents: dict[str, Any] = {}

    for artifact_id, spec in registry.items():
        try:
            path = _resolve_repo_path(root, spec["path"])
            if not path.is_file():
                raise ValueError(f"missing artifact: {spec['path']}")
            actual_raw = raw_sha256(path)
            if actual_raw != spec.get("raw_sha256"):
                raise ValueError(
                    f"{artifact_id}: raw hash {actual_raw} != "
                    f"{spec.get('raw_sha256')}"
                )
            mode = spec.get("hash_mode")
            canonical: str | None = None
            if mode == "RAW_BYTES_SHA256":
                document: Any = None
            elif mode == "CANONICAL_JSON_SHA256_V1":
                document = load_strict_json(path)
                canonical = object_sha256(document)
            elif mode == "CANONICAL_YAML_SHA256_V1":
                document = load_strict_yaml(path)
                canonical = object_sha256(document)
            elif mode == "CANONICAL_CSV_TABLE_SHA256_V1":
                _, document = load_strict_csv(path)
                canonical = canonical_csv_table_sha256(
                    document, spec.get("key_fields", [])
                )
            else:
                raise ValueError(f"{artifact_id}: unsupported hash mode {mode!r}")
            if canonical is not None and canonical != spec.get("canonical_sha256"):
                raise ValueError(
                    f"{artifact_id}: canonical hash {canonical} != "
                    f"{spec.get('canonical_sha256')}"
                )
            if document is not None:
                documents[artifact_id] = document
            if "verdict_key" in spec:
                actual_verdict = _get_path(document, spec["verdict_key"])
                if actual_verdict != spec.get("expected_verdict"):
                    raise ValueError(
                        f"{artifact_id}: verdict {actual_verdict!r} != "
                        f"{spec.get('expected_verdict')!r}"
                    )
            else:
                actual_verdict = None
            if "review_status_key" in spec:
                actual_review = _get_path(document, spec["review_status_key"])
                if actual_review != spec.get("expected_review_status"):
                    raise ValueError(
                        f"{artifact_id}: review status {actual_review!r} != "
                        f"{spec.get('expected_review_status')!r}"
                    )
            else:
                actual_review = spec.get("review_status", "NOT_APPLICABLE")
            if isinstance(document, dict):
                local_errors: list[str] = []
                _required_values(
                    document,
                    spec.get("required_values", {}),
                    artifact_id,
                    local_errors,
                )
                if local_errors:
                    raise ValueError(" | ".join(local_errors))
            snapshots[artifact_id] = {
                "path": spec["path"],
                "role": spec["role"],
                "hash_mode": mode,
                "raw_sha256": actual_raw,
                "canonical_sha256": canonical,
                "source_commit": spec["source_commit"],
                "actual_verdict": actual_verdict,
                "review_status": actual_review,
                "provisional_fields": deepcopy(spec.get("provisional_fields", [])),
            }
        except (KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))

    return snapshots, documents, registry


def _check_explanation(
    scenario_id: str,
    scenario: dict[str, Any],
    action: str,
    binding: str,
    errors: list[str],
) -> None:
    explanation = scenario.get("explanation", {})
    _require(
        scenario.get("expected_display_action") == action,
        f"{scenario_id}: expected_display_action must be {action}",
        errors,
    )
    _require(
        explanation.get("display_action") == action,
        f"{scenario_id}: display_action must be {action}",
        errors,
    )
    _require(
        explanation.get("execution_authority") is False,
        f"{scenario_id}: execution_authority must be false",
        errors,
    )
    _require(
        explanation.get("command_emitted") is False,
        f"{scenario_id}: command_emitted must be false",
        errors,
    )
    _require(
        explanation.get("authorized_candidate_binding") == binding,
        f"{scenario_id}: candidate binding must be {binding}",
        errors,
    )
    _require(
        explanation.get("evidence_complete") is True,
        f"{scenario_id}: evidence_complete must describe a complete explanation",
        errors,
    )
    _require(
        explanation.get("no_upward_reclassification") is True,
        f"{scenario_id}: no_upward_reclassification must be true",
        errors,
    )


def _check_case(
    scenario_id: str,
    scenario: dict[str, Any],
    strategy_config: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    case_spec = scenario.get("case_source", {})
    actual = strategy_config.get("cases", {}).get(scenario_id)
    _require(actual is not None, f"{scenario_id}: source case missing", errors)
    _require(
        actual == case_spec.get("expected_case"),
        f"{scenario_id}: source case values differ",
        errors,
    )
    if actual is None:
        return {}
    _require(
        object_sha256(actual) == case_spec.get("canonical_case_sha256"),
        f"{scenario_id}: canonical case hash mismatch",
        errors,
    )
    _require(
        case_spec.get("key_path") == f"cases.{scenario_id}",
        f"{scenario_id}: case key path mismatch",
        errors,
    )
    return actual


def _verify_scenarios(
    contract: dict[str, Any],
    manifest: dict[str, Any],
    documents: dict[str, Any],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    _require(
        manifest.get("schema_version") == SCENARIO_SCHEMA,
        "scenario manifest schema mismatch",
        errors,
    )
    _require(
        manifest.get("contract_schema_version") == CONTRACT_SCHEMA,
        "scenario contract schema mismatch",
        errors,
    )
    _require(
        manifest.get("replay_mode") == "OFFLINE_DETERMINISTIC",
        "scenario replay mode is not OFFLINE_DETERMINISTIC",
        errors,
    )
    _require(
        manifest.get("command_emitted") is False,
        "scenario manifest command_emitted must be false",
        errors,
    )
    _require(
        set(manifest.get("watermarks", [])) == REQUIRED_WATERMARKS,
        "required replay watermarks are missing or changed",
        errors,
    )
    scenarios = manifest.get("scenarios", {})
    _require(
        set(scenarios) == EXPECTED_SCENARIOS,
        f"scenario IDs differ: {sorted(set(scenarios) ^ EXPECTED_SCENARIOS)}",
        errors,
    )
    if not EXPECTED_SCENARIOS.issubset(scenarios):
        return {}

    strategy_config = documents["strategy_config"]
    sim10_gate = documents["sim10_gate"]
    sim12_gate = documents["sim12_gate"]
    sim12_rows = documents["sim12_results"]
    safe_policy = documents["safe_policy"]
    safe_gate = documents["safe_gate"]
    ctrl_gate = documents["ctrl02_gate"]
    ctrl_rows = documents["ctrl02_results"]
    stability_rows = ctrl_gate["gates"]["GC7_transient_stability_window"][
        "stability_table"
    ]
    summaries: dict[str, dict[str, Any]] = {}

    # Scenario A: exact sim12 and SAFE candidate binding; no authorization request.
    a = scenarios["A_low"]
    a_case = _check_case("A_low", a, strategy_config, errors)
    _require(
        a["sim10"].get("join_status") == "GLOBAL_ONLY"
        and a["sim10"].get("exact_scenario_row_present") is False,
        "A_low: sim10 must remain GLOBAL_ONLY with no exact 0.5 deg/s row",
        errors,
    )
    _require(
        sim12_gate["gates"]["GS2_differentiation"]["best_per_case"]["A_low"]
        == a["sim12"].get("expected_best_strategy")
        == "S1_passive",
        "A_low: frozen sim12 best strategy is not S1_passive",
        errors,
    )
    try:
        a_row = _one_row(sim12_rows, a["sim12"]["result_key"], "A_low sim12")
        _require(
            object_sha256(a_row) == a["sim12"]["canonical_row_sha256"],
            "A_low: sim12 row hash mismatch",
            errors,
        )
        _required_values(
            a_row, a["sim12"]["required_values"], "A_low sim12 row", errors
        )
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        a_row = {}

    binding = safe_policy.get("candidate_binding", {})
    a_safe = a.get("safe00", {})
    _require(
        binding.get("candidate_id")
        == a_safe.get("candidate_id")
        == "A_low-S1_passive",
        "A_low: SAFE candidate binding is not exact",
        errors,
    )
    _require(
        binding.get("row_ref")
        == a_safe.get("source_row_ref")
        == "A_low|S1_passive",
        "A_low: SAFE row binding is not exact",
        errors,
    )
    _require(
        binding.get("row_source", {}).get("canonical_row_sha256")
        == a_safe.get("canonical_candidate_row_sha256")
        == object_sha256(a_row),
        "A_low: SAFE candidate row hash mismatch",
        errors,
    )
    _require(
        a_safe.get("join_status") == "EXACT",
        "A_low: SAFE join must be EXACT",
        errors,
    )
    _require(
        a_safe.get("actual_authorization_request_present") is False
        and a_safe.get("actual_safe_response_present") is False,
        "A_low: no actual authorization request/response may be claimed",
        errors,
    )
    _require(
        a_safe.get("authorization_status") == "NOT_AUTHORIZED_FOR_NEXT_STAGE",
        "A_low: authorization status was upward-reclassified",
        errors,
    )
    _required_values(
        safe_gate,
        a_safe.get("required_gate_values", {}),
        "A_low SAFE gate",
        errors,
    )
    _require(
        safe_gate.get("next_stage_authorized") is False,
        "A_low: SAFE next_stage_authorized must remain false",
        errors,
    )

    a_ctrl = a.get("ctrl02", {})
    _require(
        a_ctrl.get("join_status") == "EXACT",
        "A_low: CTRL02 scenario/controller join must be EXACT",
        errors,
    )
    _require(
        a_ctrl.get("strategy_equivalence_claimed") is False,
        "A_low: capture strategy and post-capture controller were conflated",
        errors,
    )
    try:
        a_ctrl_row = _one_row(
            ctrl_rows, a_ctrl["controller_key"], "A_low CTRL02 result"
        )
        a_stability = _one_object(
            stability_rows,
            {
                "case": a_ctrl["controller_key"]["scenario"],
                "controller": a_ctrl["controller_key"]["controller"],
            },
            "A_low CTRL02 stability",
        )
        _require(
            object_sha256(a_ctrl_row)
            == a_ctrl.get("canonical_result_row_sha256"),
            "A_low: CTRL02 result row hash mismatch",
            errors,
        )
        _require(
            object_sha256(a_stability)
            == a_ctrl.get("canonical_stability_row_sha256"),
            "A_low: CTRL02 stability row hash mismatch",
            errors,
        )
        _required_values(
            a_ctrl_row,
            a_ctrl.get("required_result_values", {}),
            "A_low CTRL02 result",
            errors,
        )
        _required_values(
            a_stability,
            a_ctrl.get("required_stability_values", {}),
            "A_low CTRL02 stability",
            errors,
        )
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        a_ctrl_row, a_stability = {}, {}
    for required_limit in (
        "PASS_WITH_PROVISIONAL_SCOPE",
        "PROVISIONAL_L1_MOMENTUM_ACTUATOR",
        "PENDING_REVIEW",
        "L0 hardware-valid stability is NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
    ):
        _require(
            required_limit in a_ctrl.get("limitations", []),
            f"A_low: missing CTRL02 limitation {required_limit}",
            errors,
        )
    _check_explanation("A_low", a, "EXECUTE", "EXACT", errors)

    # Scenario B: exact sim10 anchor and upstream sim12 ABORT.  No downstream request.
    b = scenarios["B_anchor"]
    b_case = _check_case("B_anchor", b, strategy_config, errors)
    _require(
        b["sim10"].get("join_status") == "EXACT",
        "B_anchor: sim10 join must be EXACT",
        errors,
    )
    try:
        b_anchor = _one_object(
            _get_path(sim10_gate, b["sim10"]["selector"]["path"]),
            b["sim10"]["selector"]["match"],
            "B_anchor sim10 anchor",
        )
        _require(
            object_sha256(b_anchor)
            == b["sim10"].get("canonical_selected_object_sha256"),
            "B_anchor: sim10 selected object hash mismatch",
            errors,
        )
        _required_values(
            b_anchor,
            b["sim10"].get("required_values", {}),
            "B_anchor sim10 anchor",
            errors,
        )
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        b_anchor = {}
    _require(
        sim12_gate["gates"]["GS2_differentiation"]["best_per_case"]["B_anchor"]
        == b["sim12"].get("expected_best_strategy")
        == "ABORT",
        "B_anchor: frozen sim12 decision is not ABORT",
        errors,
    )
    b_rows: list[dict[str, str]] = []
    for row_spec in b["sim12"].get("required_rows", []):
        try:
            row = _one_row(sim12_rows, row_spec["key"], "B_anchor sim12")
            b_rows.append(row)
            _require(
                object_sha256(row) == row_spec["canonical_row_sha256"],
                f"B_anchor: row hash mismatch for {row_spec['key']}",
                errors,
            )
            _required_values(
                row,
                b["sim12"].get("required_all_values", {}),
                f"B_anchor sim12 {row_spec['key']}",
                errors,
            )
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
    _require(
        len(b_rows) == 4,
        "B_anchor: all four frozen strategy rows are required",
        errors,
    )
    b_safe = b.get("safe00", {})
    _require(
        b_safe.get("join_status") == "NOT_APPLICABLE"
        and b_safe.get("actual_authorization_request_present") is False
        and b_safe.get("actual_safe_response_present") is False
        and b_safe.get("decision") == "NOT_APPLICABLE_UPSTREAM_ABORT",
        "B_anchor: a SAFE request/response was fabricated after upstream ABORT",
        errors,
    )
    b_ctrl = b.get("ctrl02", {})
    _require(
        b_ctrl.get("join_status") == "NOT_APPLICABLE"
        and b_ctrl.get("included_in_execution_chain") is False
        and b_ctrl.get("available_rows_are_counterfactual") is True,
        "B_anchor: CTRL02 counterfactual rows were promoted into the chain",
        errors,
    )
    _require(
        ctrl_gate["gates"]["GC2_four_case_independent_replay"][
            "B_anchor_all_rows_out_of_feasible_region"
        ]
        is True,
        "B_anchor: CTRL02 gate no longer marks all rows out of region",
        errors,
    )
    b_stability_rows = [
        row for row in stability_rows if row.get("case") == "B_anchor"
    ]
    _require(
        len(b_stability_rows) == 4
        and all(row.get("counterfactual_only") is True for row in b_stability_rows),
        "B_anchor: CTRL02 rows are not uniformly counterfactual",
        errors,
    )
    _check_explanation("B_anchor", b, "ABORT", "NOT_APPLICABLE", errors)

    # Scenario C: exact strategy modification, missing SAFE candidate, CTRL02 reference only.
    c = scenarios["C_transition"]
    c_case = _check_case("C_transition", c, strategy_config, errors)
    _require(
        c["sim10"].get("join_status") == "GLOBAL_ONLY"
        and c["sim10"].get("exact_scenario_row_present") is False,
        "C_transition: sim10 must remain GLOBAL_ONLY with no exact row",
        errors,
    )
    _require(
        sim12_gate["gates"]["GS2_differentiation"]["best_per_case"]["C_transition"]
        == c["sim12"].get("expected_best_strategy")
        == "S3a_wheel_bias",
        "C_transition: frozen sim12 best strategy is not S3a",
        errors,
    )
    try:
        c_s1_spec = c["sim12"]["rejected_baseline"]
        c_s3_spec = c["sim12"]["selected_strategy"]
        c_s1 = _one_row(sim12_rows, c_s1_spec["key"], "C_transition S1")
        c_s3 = _one_row(sim12_rows, c_s3_spec["key"], "C_transition S3a")
        _require(
            object_sha256(c_s1) == c_s1_spec["canonical_row_sha256"],
            "C_transition: S1 row hash mismatch",
            errors,
        )
        _require(
            object_sha256(c_s3) == c_s3_spec["canonical_row_sha256"],
            "C_transition: S3a row hash mismatch",
            errors,
        )
        _required_values(
            c_s1,
            c_s1_spec["required_values"],
            "C_transition S1",
            errors,
        )
        _required_values(
            c_s3,
            c_s3_spec["required_values"],
            "C_transition S3a",
            errors,
        )
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        c_s1, c_s3 = {}, {}
    c_safe = c.get("safe00", {})
    _require(
        c_safe.get("join_status") == "NOT_APPLICABLE"
        and c_safe.get("authorized_candidate_binding") == "MISSING"
        and c_safe.get("decision") == "MISSING_REGISTERED_CANDIDATE",
        "C_transition: missing SAFE candidate was promoted",
        errors,
    )
    _require(
        c_safe.get("actual_authorization_request_present") is False
        and c_safe.get("actual_safe_response_present") is False,
        "C_transition: an unregistered SAFE request/response was fabricated",
        errors,
    )
    _require(
        c_safe.get("registered_candidate_id")
        == binding.get("candidate_id")
        == "A_low-S1_passive",
        "C_transition: SAFE registry truth differs",
        errors,
    )
    _require(
        c_safe.get("requested_candidate_id") != binding.get("candidate_id"),
        "C_transition: requested candidate unexpectedly equals the registry entry",
        errors,
    )
    c_ctrl = c.get("ctrl02", {})
    _require(
        c_ctrl.get("join_status") == "REFERENCE_ONLY",
        "C_transition: CTRL02 join must remain REFERENCE_ONLY",
        errors,
    )
    _require(
        c_ctrl.get("strategy_equivalence_claimed") is False,
        "C_transition: CTRL02 controller was conflated with S3a",
        errors,
    )
    c_ctrl_rows: list[dict[str, str]] = []
    c_stability_rows: list[dict[str, Any]] = []
    for row_spec in c_ctrl.get("reference_rows", []):
        try:
            result_row = _one_row(
                ctrl_rows, row_spec["key"], "C_transition CTRL02 result"
            )
            stability_row = _one_object(
                stability_rows,
                {
                    "case": row_spec["key"]["scenario"],
                    "controller": row_spec["key"]["controller"],
                },
                "C_transition CTRL02 stability",
            )
            c_ctrl_rows.append(result_row)
            c_stability_rows.append(stability_row)
            _require(
                object_sha256(result_row)
                == row_spec["canonical_result_row_sha256"],
                f"C_transition: result hash mismatch for {row_spec['key']}",
                errors,
            )
            _require(
                object_sha256(stability_row)
                == row_spec["canonical_stability_row_sha256"],
                f"C_transition: stability hash mismatch for {row_spec['key']}",
                errors,
            )
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
    _require(
        len(c_ctrl_rows) == 4 and len(c_stability_rows) == 4,
        "C_transition: all four CTRL02 rows are required as references",
        errors,
    )
    for required_limit in (
        "REFERENCE_ONLY",
        "PASS_WITH_PROVISIONAL_SCOPE",
        "PROVISIONAL_L1_MOMENTUM_ACTUATOR",
        "PENDING_REVIEW",
        "The CTRL-02 controllers are not the sim12 S3a capture strategy.",
    ):
        _require(
            required_limit in c_ctrl.get("limitations", []),
            f"C_transition: missing CTRL02 limitation {required_limit}",
            errors,
        )
    _check_explanation("C_transition", c, "MODIFY", "MISSING", errors)

    summaries["A_low"] = {
        "case": a_case,
        "sim12_row": a_row,
        "ctrl02_result": a_ctrl_row,
        "ctrl02_stability": a_stability,
    }
    summaries["B_anchor"] = {
        "case": b_case,
        "sim10_anchor": b_anchor,
        "sim12_rows": b_rows,
    }
    summaries["C_transition"] = {
        "case": c_case,
        "sim12_rejected": c_s1,
        "sim12_selected": c_s3,
        "ctrl02_reference_rows": c_ctrl_rows,
        "ctrl02_stability_rows": c_stability_rows,
    }
    return summaries


def _verify_claim_matrix(
    contract: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
    registry: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    relative = contract.get("outputs", {}).get("claim_matrix_path", "")
    try:
        path = _resolve_repo_path(root, relative)
        fields, rows = load_strict_csv(path)
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        return {"path": relative, "row_count": 0}
    _require(fields == CLAIM_FIELDS, "claim matrix does not have the 11 frozen fields", errors)
    claim_ids = [row["claim_id"] for row in rows]
    _require(
        len(claim_ids) == len(set(claim_ids)),
        "claim matrix contains duplicate claim_id",
        errors,
    )
    _require(len(rows) >= 8, "claim matrix must contain at least eight bounded claims", errors)
    valid_hashes = {
        scenario["case_source"]["canonical_case_sha256"]
        for scenario in manifest.get("scenarios", {}).values()
    } | {"GLOBAL", "ALL_THREE_CASES"}
    registered_gate_paths = {
        spec["path"] for spec in registry.values() if spec.get("role") == "GATE"
    }
    registered_csv_paths = {
        spec["path"]
        for spec in registry.values()
        if spec.get("role") == "RESULT_TABLE"
    }
    base = contract.get("baseline", {}).get("approved_git_commit")
    for row in rows:
        for field in CLAIM_FIELDS:
            _require(bool(row[field].strip()), f"{row.get('claim_id')}: empty {field}", errors)
        _require(
            row["commit"] == base,
            f"{row['claim_id']}: claim commit differs from approved base",
            errors,
        )
        _require(
            row["scenario_hash"] in valid_hashes,
            f"{row['claim_id']}: unknown scenario hash",
            errors,
        )
        for ref in row["gate_json"].split(";"):
            ref_path = ref.split("#", 1)[0]
            _require(
                ref_path in registered_gate_paths,
                f"{row['claim_id']}: unregistered gate path {ref_path}",
                errors,
            )
        if row["result_csv"] != "NONE":
            result_path = row["result_csv"].split("#", 1)[0]
            _require(
                result_path in registered_csv_paths,
                f"{row['claim_id']}: unregistered result CSV {result_path}",
                errors,
            )
        _require(
            row["allowed_wording"] != row["forbidden_wording"],
            f"{row['claim_id']}: allowed and forbidden wording are identical",
            errors,
        )
    return {
        "path": relative,
        "row_count": len(rows),
        "raw_sha256": raw_sha256(path) if path.is_file() else None,
        "fields": fields,
    }


def verify_evidence_contract_data(
    contract: dict[str, Any],
    manifest: dict[str, Any],
    root: Path,
    *,
    check_git: bool = True,
    check_claims: bool = True,
) -> dict[str, Any]:
    """Verify frozen artifacts and scenario semantics without running science."""
    root = root.resolve()
    errors: list[str] = []
    _require(
        contract.get("schema_version") == CONTRACT_SCHEMA,
        "contract schema mismatch",
        errors,
    )
    _require(
        contract.get("scope") == "DT2_CURRENT_SCOPE_OFFLINE_EVIDENCE_REPLAY",
        "contract scope was widened",
        errors,
    )
    _require(
        contract.get("replay_mode") == "OFFLINE_DETERMINISTIC",
        "contract replay mode is not offline deterministic",
        errors,
    )
    _require(
        contract.get("command_emitted") is False,
        "contract command_emitted must be false",
        errors,
    )
    _require(
        contract.get("decision_rules", {}).get("unknown_policy")
        == "NEVER_UPWARD_RECLASSIFY",
        "UNKNOWN upward-reclassification policy changed",
        errors,
    )
    _require(
        contract.get("baseline", {}).get("thresholds_widened") is False,
        "thresholds_widened is not false",
        errors,
    )
    _require(
        contract.get("baseline", {}).get("owned_path_prefix")
        == "10_research/competition_convergence/",
        "owned path prefix widened or changed",
        errors,
    )
    _require(
        tuple(
            contract.get("baseline", {}).get("integration_owned_prefixes", [])
        )
        == EXPECTED_INTEGRATION_OWNED_PREFIXES,
        "integration-owned path prefixes widened or changed",
        errors,
    )
    frozen_dirty = contract.get("baseline", {}).get(
        "preexisting_dirty_fingerprints", {}
    )
    _require(
        isinstance(frozen_dirty, dict)
        and set(frozen_dirty) == EXPECTED_PREEXISTING_DIRTY_PATHS,
        "pre-existing dirty-path baseline differs from launch freeze",
        errors,
    )
    if isinstance(frozen_dirty, dict):
        for path, digest in frozen_dirty.items():
            _require(
                isinstance(digest, str) and bool(SHA256_RE.fullmatch(digest)),
                f"{path}: invalid pre-existing dirty SHA-256",
                errors,
            )
    _require(
        contract.get("baseline", {}).get("frozen_threshold_registry_sha256")
        == "400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873",
        "threshold registry binding changed",
        errors,
    )

    snapshots, documents, registry = _verify_artifacts(contract, root, errors)
    if check_git:
        git_check = _verify_git_and_scope(contract, root, registry, errors)
    else:
        git_check = {
            "approved_git_commit": contract.get("baseline", {}).get(
                "approved_git_commit"
            ),
            "base_is_ancestor": "NOT_CHECKED",
            "scope_violations": [],
        }

    if EXPECTED_ARTIFACT_IDS.issubset(documents.keys() | {"threshold_registry"}):
        summaries = _verify_scenarios(contract, manifest, documents, errors)
    else:
        summaries = {}
    if check_claims:
        claims = _verify_claim_matrix(contract, manifest, root, registry, errors)
    else:
        claims = {"path": contract.get("outputs", {}).get("claim_matrix_path"),
                  "row_count": "NOT_CHECKED"}

    if errors:
        raise EvidenceError(errors)
    return {
        "schema_version": VERIFICATION_SCHEMA,
        "overall": "PASS",
        "replay_mode": "OFFLINE_DETERMINISTIC",
        "command_emitted": False,
        "thresholds_widened": False,
        "git": git_check,
        "artifacts": snapshots,
        "scenario_actions": {
            "A_low": "EXECUTE_EXPLANATION_ONLY",
            "B_anchor": "ABORT_UPSTREAM",
            "C_transition": "MODIFY_TO_S3A_NO_SAFE_BINDING",
        },
        "scenario_summaries": summaries,
        "claims": claims,
    }


def load_and_verify(
    contract_path: Path,
    scenario_path: Path,
    root: Path | None = None,
    *,
    check_git: bool = True,
    check_claims: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = load_strict_yaml(contract_path)
    manifest = load_strict_yaml(scenario_path)
    repository = (root or repo_root_from_here()).resolve()
    report = verify_evidence_contract_data(
        contract,
        manifest,
        repository,
        check_git=check_git,
        check_claims=check_claims,
    )
    return contract, manifest, report


def _artifact_refs(
    report: dict[str, Any], artifact_ids: Iterable[str]
) -> list[dict[str, Any]]:
    refs = []
    for artifact_id in artifact_ids:
        snapshot = deepcopy(report["artifacts"][artifact_id])
        snapshot["artifact_id"] = artifact_id
        refs.append(snapshot)
    return refs


def _stage(
    stage_id: str,
    *,
    input_refs: list[str],
    output_ref: str,
    join_keys: dict[str, Any],
    join_status: str,
    scientific_state: str,
    decision: str,
    reason_code: str,
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "input_refs": input_refs,
        "output_ref": output_ref,
        "join_keys": join_keys,
        "join_status": join_status,
        "scientific_state": scientific_state,
        "decision": decision,
        "reason_code": reason_code,
        "limitations": limitations,
    }


def build_replay_records(
    contract: dict[str, Any],
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build display-neutral replay records from the already verified report."""
    base = {
        "approved_git_commit": contract["baseline"]["approved_git_commit"],
        "source_worktree_clean_at_freeze": contract["baseline"][
            "source_worktree_clean_at_freeze"
        ],
        "frozen_threshold_registry_sha256": contract["baseline"][
            "frozen_threshold_registry_sha256"
        ],
        "thresholds_widened": False,
    }
    scenarios = manifest["scenarios"]
    summaries = report["scenario_summaries"]
    records: dict[str, dict[str, Any]] = {}

    def common_record(
        scenario_id: str, artifact_ids: list[str]
    ) -> dict[str, Any]:
        spec = scenarios[scenario_id]
        case = summaries[scenario_id]["case"]
        return {
            "schema_version": REPLAY_SCHEMA,
            "record_id": spec["record_id"],
            "scenario_id": scenario_id,
            "replay_mode": "OFFLINE_DETERMINISTIC",
            "command_emitted": False,
            "baseline": deepcopy(base),
            "mission_input": {
                "source_path": report["artifacts"]["strategy_config"]["path"],
                "source_key": spec["case_source"]["key_path"],
                "raw_sha256": report["artifacts"]["strategy_config"]["raw_sha256"],
                "canonical_hash_mode": "CANONICAL_YAML_SHA256_V1",
                "canonical_case_sha256": spec["case_source"][
                    "canonical_case_sha256"
                ],
                "geometry_or_case_confidence": spec["case_source"][
                    "geometry_or_case_confidence"
                ],
                "value": deepcopy(case),
            },
            "evidence_artifacts": _artifact_refs(report, artifact_ids),
            "stage_records": [],
            "explanation": deepcopy(spec["explanation"]),
            "watermarks": list(manifest["watermarks"]),
        }

    # A
    a_summary = summaries["A_low"]
    a = common_record(
        "A_low",
        [
            "threshold_registry",
            "sim10_gate",
            "strategy_config",
            "sim12_gate",
            "sim12_results",
            "safe_policy",
            "safe_gate",
            "ctrl02_gate",
            "ctrl02_results",
        ],
    )
    a["stage_records"] = [
        _stage(
            "MISSION_INPUT",
            input_refs=["strategy_config#cases.A_low"],
            output_ref="mission_input",
            join_keys={"case": "A_low"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="INPUT_FROZEN",
            reason_code="CANONICAL_CASE_HASH_MATCH",
            limitations=["22 kg mass is a low-confidence v0 competition input"],
        ),
        _stage(
            "SIM10",
            input_refs=["sim10_gate"],
            output_ref="sim10_gate#verdict",
            join_keys={},
            join_status="GLOBAL_ONLY",
            scientific_state="PASS",
            decision="SIM10_GATES_PASS",
            reason_code="GLOBAL_GATE_ONLY_NO_A_LOW_EXACT_ROW",
            limitations=[
                "A_low at 0.5 deg/s has no exact sim10 gate row",
                "FLEX=UNKNOWN_NOT_IN_CRITERIA",
            ],
        ),
        _stage(
            "SIM12",
            input_refs=[
                "strategy_config#cases.A_low",
                "sim12_results#A_low|S1_passive",
                "sim12_gate#GS2",
            ],
            output_ref="sim12_results#A_low|S1_passive",
            join_keys={"case": "A_low", "strategy": "S1_passive"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="S1_passive",
            reason_code="BEST_STRATEGY_EXACT_ROW",
            limitations=[
                "flex_energy=PROVISIONAL_NOT_EVALUATED",
                f"post_capture_rate_dps={a_summary['sim12_row']['post_capture_rate_dps']}",
            ],
        ),
        _stage(
            "SAFE00",
            input_refs=[
                "safe_policy#candidate_binding",
                "safe_gate#verdict",
                "sim12_results#A_low|S1_passive",
            ],
            output_ref="safe_policy#candidate_binding",
            join_keys={
                "candidate_id": "A_low-S1_passive",
                "row_ref": "A_low|S1_passive",
            },
            join_status="EXACT",
            scientific_state="PASS",
            decision="CANDIDATE_BINDING_VERIFIED_NO_EXECUTION_AUTHORITY",
            reason_code="SAFE_GATE_PASS_REVIEW_PENDING_NEXT_STAGE_FALSE",
            limitations=[
                "No actual authorization request or SAFE response exists",
                "review_status=PENDING_REVIEW",
                "next_stage_authorized=false",
            ],
        ),
        _stage(
            "CTRL02",
            input_refs=[
                "ctrl02_results#B|A_low|B1_wheel_storage",
                "ctrl02_gate#GC7",
            ],
            output_ref="ctrl02_gate#GC7:A_low|B1_wheel_storage",
            join_keys={
                "case": "A_low",
                "controller": "B1_wheel_storage",
                "stage": "POST_CAPTURE_RESOURCE_EVALUATION",
            },
            join_status="EXACT",
            scientific_state="PASS",
            decision=a_summary["ctrl02_stability"]["stability_verdict"],
            reason_code="SCENARIO_AND_CONTROLLER_ROW_EXACT",
            limitations=[
                "PASS_WITH_PROVISIONAL_SCOPE",
                "PROVISIONAL_L1_MOMENTUM_ACTUATOR",
                "L0 hardware-valid stability is NOT_EVALUATED_NO_ACTUATOR_DYNAMICS",
                "This controller is not claimed to be the S1 capture strategy",
            ],
        ),
        _stage(
            "OFFLINE_REPLAY",
            input_refs=["SIM10", "SIM12", "SAFE00", "CTRL02"],
            output_ref="explanation",
            join_keys={"scenario": "A_low"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="EXECUTE_EXPLANATION_ONLY",
            reason_code="EXACT_REGISTERED_CANDIDATE_NO_EXECUTION_AUTHORITY",
            limitations=["NO COMMAND OUTPUT", "NO REAL-TIME SYNCHRONIZATION"],
        ),
        _stage(
            "EXPLANATION",
            input_refs=["OFFLINE_REPLAY"],
            output_ref="display_action",
            join_keys={"scenario": "A_low"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="EXECUTE",
            reason_code="DISPLAY_LABEL_ONLY",
            limitations=["execution_authority=false", "command_emitted=false"],
        ),
    ]
    records["A_low"] = a

    # B
    b_summary = summaries["B_anchor"]
    b = common_record(
        "B_anchor",
        [
            "threshold_registry",
            "sim10_gate",
            "strategy_config",
            "sim12_gate",
            "sim12_results",
            "ctrl02_gate",
        ],
    )
    b["stage_records"] = [
        _stage(
            "MISSION_INPUT",
            input_refs=["strategy_config#cases.B_anchor"],
            output_ref="mission_input",
            join_keys={"case": "B_anchor"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="INPUT_FROZEN",
            reason_code="CANONICAL_CASE_HASH_MATCH",
            limitations=["150 kg mass is a low-confidence v0 competition input"],
        ),
        _stage(
            "SIM10",
            input_refs=["sim10_gate#X1:debris_sim06"],
            output_ref="sim10_gate#X1:debris_sim06",
            join_keys={"anchor": "debris_sim06"},
            join_status="EXACT",
            scientific_state="PASS",
            decision=b_summary["sim10_anchor"]["region"],
            reason_code="POST_CAPTURE_RATE_GATE",
            limitations=[
                f"w_plus_dps={b_summary['sim10_anchor']['w_plus_dps']}",
                "FLEX=UNKNOWN_NOT_IN_CRITERIA",
            ],
        ),
        _stage(
            "SIM12",
            input_refs=[
                "sim12_results#B_anchor|ALL_FOUR_STRATEGIES",
                "sim12_gate#GS2",
            ],
            output_ref="sim12_gate#GS2:B_anchor",
            join_keys={"case": "B_anchor"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="ABORT",
            reason_code="ALL_FOUR_STRATEGIES_INFEASIBLE_POST_CAPTURE_RATE",
            limitations=["ABORT is bounded to the frozen strategy set and inputs"],
        ),
        _stage(
            "SAFE00",
            input_refs=["SIM12"],
            output_ref="NONE",
            join_keys={},
            join_status="NOT_APPLICABLE",
            scientific_state="NOT_EVALUATED",
            decision="NOT_APPLICABLE_UPSTREAM_ABORT",
            reason_code="UPSTREAM_SIM12_ABORT_NO_REQUEST",
            limitations=["No SAFE request or response was generated"],
        ),
        _stage(
            "CTRL02",
            input_refs=["ctrl02_gate#GC2:B_anchor"],
            output_ref="NONE",
            join_keys={"case": "B_anchor"},
            join_status="NOT_APPLICABLE",
            scientific_state="NOT_EVALUATED",
            decision="NOT_APPLICABLE_UPSTREAM_ABORT",
            reason_code="COUNTERFACTUAL_ROWS_EXCLUDED",
            limitations=[
                "All CTRL02 B_anchor rows are out-of-feasible-region counterfactuals",
                "No detumble execution is represented",
            ],
        ),
        _stage(
            "OFFLINE_REPLAY",
            input_refs=["SIM10", "SIM12"],
            output_ref="explanation",
            join_keys={"scenario": "B_anchor"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="ABORT",
            reason_code="UPSTREAM_ABORT_NO_DOWNSTREAM_REQUEST",
            limitations=["NO COMMAND OUTPUT", "NO REAL-TIME SYNCHRONIZATION"],
        ),
        _stage(
            "EXPLANATION",
            input_refs=["OFFLINE_REPLAY"],
            output_ref="display_action",
            join_keys={"scenario": "B_anchor"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="ABORT",
            reason_code="DISPLAY_LABEL_FROM_VERIFIED_UPSTREAM_ABORT",
            limitations=["execution_authority=false", "command_emitted=false"],
        ),
    ]
    records["B_anchor"] = b

    # C
    c_summary = summaries["C_transition"]
    c = common_record(
        "C_transition",
        [
            "threshold_registry",
            "sim10_gate",
            "strategy_config",
            "sim12_gate",
            "sim12_results",
            "safe_policy",
            "safe_gate",
            "ctrl02_gate",
            "ctrl02_results",
        ],
    )
    c["stage_records"] = [
        _stage(
            "MISSION_INPUT",
            input_refs=["strategy_config#cases.C_transition"],
            output_ref="mission_input",
            join_keys={"case": "C_transition"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="INPUT_FROZEN",
            reason_code="CANONICAL_CASE_HASH_MATCH",
            limitations=["C is a frozen proof case, not a hardware target"],
        ),
        _stage(
            "SIM10",
            input_refs=["sim10_gate"],
            output_ref="sim10_gate#verdict",
            join_keys={},
            join_status="GLOBAL_ONLY",
            scientific_state="PASS",
            decision="SIM10_GATES_PASS",
            reason_code="GLOBAL_GATE_ONLY_NO_C_TRANSITION_EXACT_ROW",
            limitations=[
                "C_transition has no exact sim10 gate row",
                "FLEX=UNKNOWN_NOT_IN_CRITERIA",
            ],
        ),
        _stage(
            "SIM12",
            input_refs=[
                "sim12_results#C_transition|S1_passive",
                "sim12_results#C_transition|S3a_wheel_bias",
                "sim12_gate#GS2",
            ],
            output_ref="sim12_results#C_transition|S3a_wheel_bias",
            join_keys={"case": "C_transition", "strategy": "S3a_wheel_bias"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="MODIFY_TO_S3a_wheel_bias",
            reason_code="S1_WHEEL_MOMENTUM_BOUND_S3A_FEASIBLE",
            limitations=[
                "flex_energy=PROVISIONAL_NOT_EVALUATED",
                f"S1_wheel_margin_Nms={c_summary['sim12_rejected']['wheel_margin_Nms']}",
                f"S3a_wheel_margin_Nms={c_summary['sim12_selected']['wheel_margin_Nms']}",
            ],
        ),
        _stage(
            "SAFE00",
            input_refs=["safe_policy#candidate_binding", "SIM12"],
            output_ref="NONE",
            join_keys={"requested_candidate_id": "C_transition-S3a_wheel_bias"},
            join_status="NOT_APPLICABLE",
            scientific_state="BLOCKED",
            decision="MISSING_REGISTERED_CANDIDATE",
            reason_code="SAFE_POLICY_HAS_NO_C_TRANSITION_CANDIDATE",
            limitations=[
                "No SAFE request or response was generated",
                "Only A_low-S1_passive is registered",
                "review_status=PENDING_REVIEW",
            ],
        ),
        _stage(
            "CTRL02",
            input_refs=[
                "ctrl02_results#B|C_transition|ALL_CONTROLLERS",
                "ctrl02_gate#GC7:C_transition",
            ],
            output_ref="ctrl02_reference_rows",
            join_keys={"case": "C_transition"},
            join_status="REFERENCE_ONLY",
            scientific_state="PASS",
            decision="REFERENCE_ONLY_NO_STRATEGY_EQUIVALENCE",
            reason_code="CTRL02_CONTROLLERS_ARE_NOT_SIM12_S3A",
            limitations=[
                "PASS_WITH_PROVISIONAL_SCOPE",
                "PROVISIONAL_L1_MOMENTUM_ACTUATOR",
                "The CTRL02 rows cannot authorize or validate S3a",
            ],
        ),
        _stage(
            "OFFLINE_REPLAY",
            input_refs=["SIM10", "SIM12", "SAFE00", "CTRL02"],
            output_ref="explanation",
            join_keys={"scenario": "C_transition"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="MODIFY",
            reason_code="S3A_SELECTED_SAFE_BINDING_MISSING",
            limitations=["NO COMMAND OUTPUT", "NO REAL-TIME SYNCHRONIZATION"],
        ),
        _stage(
            "EXPLANATION",
            input_refs=["OFFLINE_REPLAY"],
            output_ref="display_action",
            join_keys={"scenario": "C_transition"},
            join_status="EXACT",
            scientific_state="PASS",
            decision="MODIFY",
            reason_code="CHANGE_CANDIDATE_THEN_REENTER_AUTHORIZATION",
            limitations=["execution_authority=false", "command_emitted=false"],
        ),
    ]
    c["ctrl02_reference_rows"] = [
        {
            "result": deepcopy(result),
            "stability": deepcopy(stability),
            "join_status": "REFERENCE_ONLY",
        }
        for result, stability in zip(
            c_summary["ctrl02_reference_rows"],
            c_summary["ctrl02_stability_rows"],
            strict=True,
        )
    ]
    records["C_transition"] = c
    return records


def deterministic_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_replay_package(
    contract_path: Path,
    scenario_path: Path,
    output_dir: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    repository = (root or repo_root_from_here()).resolve()
    contract, manifest, report = load_and_verify(
        contract_path, scenario_path, repository
    )
    output = output_dir if output_dir.is_absolute() else repository / output_dir
    output.mkdir(parents=True, exist_ok=True)
    expected_names = {
        "scenario_A_low.json",
        "scenario_B_anchor.json",
        "scenario_C_transition.json",
        "replay_manifest.json",
    }
    unexpected = sorted(
        child.name
        for child in output.iterdir()
        if child.is_file() and child.name not in expected_names
    )
    if unexpected:
        raise EvidenceError([f"unexpected replay output files: {unexpected}"])

    records = build_replay_records(contract, manifest, report)
    scenario_files: dict[str, dict[str, str]] = {}
    for scenario_id, record in records.items():
        filename = f"scenario_{scenario_id}.json"
        data = deterministic_json_bytes(record)
        (output / filename).write_bytes(data)
        scenario_files[scenario_id] = {
            "path": filename,
            "raw_sha256": hashlib.sha256(data).hexdigest(),
            "display_action": record["explanation"]["display_action"],
        }

    package_basis = {
        "contract_raw_sha256": raw_sha256(contract_path),
        "scenario_manifest_raw_sha256": raw_sha256(scenario_path),
        "scenario_files": scenario_files,
    }
    replay_manifest = {
        "schema_version": "competition-offline-replay-package-v1",
        "replay_mode": "OFFLINE_DETERMINISTIC",
        "command_emitted": False,
        "approved_git_commit": contract["baseline"]["approved_git_commit"],
        "contract_path": str(contract_path.relative_to(repository)).replace("\\", "/"),
        "contract_raw_sha256": package_basis["contract_raw_sha256"],
        "scenario_manifest_path": str(
            scenario_path.relative_to(repository)
        ).replace("\\", "/"),
        "scenario_manifest_raw_sha256": package_basis[
            "scenario_manifest_raw_sha256"
        ],
        "scenario_files": scenario_files,
        "package_content_sha256": object_sha256(package_basis),
        "watermarks": list(manifest["watermarks"]),
        "claim_matrix": report["claims"],
        "deterministic": True,
    }
    (output / "replay_manifest.json").write_bytes(
        deterministic_json_bytes(replay_manifest)
    )
    return replay_manifest
