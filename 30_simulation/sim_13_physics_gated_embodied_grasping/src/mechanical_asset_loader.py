"""Strict loader for the mechanical-to-RL interface package.

The loader deliberately treats every unbound or malformed fact as an error.  In
particular, it never estimates arm mass from a visual or collision mesh.  The
accepted URDF is the only mass authority for the B601 model.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:  # PyYAML is optional when the .yaml documents use the JSON subset.
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal runtimes.
    yaml = None


INTERFACE_SCHEMA_VERSION = "MECH_RL_INTERFACE_V1"
B601_ACCEPTED_MASS_KG = 4.695555949
EXPECTED_LINK_COUNT = 10
EXPECTED_JOINT_COUNT = 9
EXPECTED_JOINT_TYPES = {"revolute": 6, "fixed": 1, "prismatic": 2}
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MESH_SUFFIXES = {".stl", ".obj", ".dae", ".ply"}


class MechanicalAssetError(ValueError):
    """Base class for fail-closed mechanical package errors."""


class AssetHashMismatch(MechanicalAssetError):
    """Raised when an asset no longer matches its manifest binding."""


class AssetSchemaError(MechanicalAssetError):
    """Raised when the interface or one of its structured assets is invalid."""


@dataclass(frozen=True)
class ArtifactBinding:
    name: str
    path: Path
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class UrdfSummary:
    robot_name: str
    link_names: tuple[str, ...]
    joint_names: tuple[str, ...]
    joint_type_counts: Mapping[str, int]
    root_link: str
    total_mass_kg: float
    mesh_paths: tuple[Path, ...]

    @property
    def link_count(self) -> int:
        return len(self.link_names)

    @property
    def joint_count(self) -> int:
        return len(self.joint_names)


@dataclass(frozen=True)
class FrameTreeSummary:
    root_frame: str
    frame_ids: tuple[str, ...]
    parent_by_frame: Mapping[str, str | None]

    @property
    def frame_count(self) -> int:
        return len(self.frame_ids)


@dataclass(frozen=True)
class MechanicalAssetBundle:
    manifest_path: Path
    manifest_sha256: str
    asset_root: Path
    artifacts: Mapping[str, ArtifactBinding]
    urdf: UrdfSummary
    frame_tree: FrameTreeSummary
    accepted_configurations: tuple[str, ...]
    grasp_candidates: tuple[Mapping[str, Any], ...]
    capture_timing_ids: tuple[str, ...]
    m3r_mount_transform: Mapping[str, Any]
    camera_reserve_frames: tuple[str, ...]
    keep_out: tuple[Mapping[str, Any], ...]
    mass_and_inertia: Mapping[str, Any]

    @property
    def artifact_hashes(self) -> Mapping[str, str]:
        return {name: item.sha256 for name, item in self.artifacts.items()}

    @property
    def grasp_candidate_ids(self) -> tuple[str, ...]:
        return tuple(str(item["id"]) for item in self.grasp_candidates)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reject_duplicate_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AssetSchemaError(f"duplicate mapping key: {key}")
        result[key] = value
    return result


if yaml is not None:
    class _UniqueKeyLoader(yaml.SafeLoader):
        pass


    def _construct_unique_mapping(
        loader: "_UniqueKeyLoader",
        node: Any,
        deep: bool = False,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in result:
                raise AssetSchemaError(f"duplicate mapping key: {key}")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result


    _UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _construct_unique_mapping,
    )


def _load_document(path: Path) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise MechanicalAssetError(f"cannot read structured asset: {path}") from exc
    try:
        if yaml is not None:
            value = yaml.load(text, Loader=_UniqueKeyLoader)
        else:
            value = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except (ValueError, AssetSchemaError) as exc:
        raise AssetSchemaError(f"invalid structured asset {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise AssetSchemaError(f"structured asset root must be a mapping: {path}")
    return value


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssetSchemaError(f"{label} must be a mapping")
    return value


def _require_sequence(value: Any, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise AssetSchemaError(f"{label} must be a sequence")
    return value


def _unique_nonempty_strings(value: Any, label: str) -> tuple[str, ...]:
    values = _require_sequence(value, label)
    output: list[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise AssetSchemaError(f"{label} entries must be non-empty strings")
        if item in output:
            raise AssetSchemaError(f"duplicate {label} entry: {item}")
        output.append(item)
    if not output:
        raise AssetSchemaError(f"{label} must not be empty")
    return tuple(output)


def _resolve_under(root: Path, relative_path: str, label: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise AssetSchemaError(f"{label}.path must be a non-empty string")
    candidate_input = Path(relative_path)
    if candidate_input.is_absolute():
        raise AssetSchemaError(f"{label}.path must be relative to asset_root")
    candidate = (root / candidate_input).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AssetSchemaError(f"{label}.path escapes asset_root") from exc
    return candidate


def _load_artifact_binding(
    name: str,
    value: Any,
    asset_root: Path,
) -> ArtifactBinding:
    record = _require_mapping(value, f"artifacts.{name}")
    relative_path = record.get("path")
    path = _resolve_under(asset_root, relative_path, f"artifacts.{name}")
    expected_hash = record.get("sha256")
    if not isinstance(expected_hash, str) or not _SHA256_RE.fullmatch(expected_hash):
        raise AssetSchemaError(f"artifacts.{name}.sha256 must be 64 hexadecimal characters")
    if not path.is_file():
        raise MechanicalAssetError(f"required artifact does not exist: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise MechanicalAssetError(f"required artifact is empty: {path}")
    actual_hash = sha256_file(path)
    if actual_hash.lower() != expected_hash.lower():
        raise AssetHashMismatch(
            f"{name} SHA-256 mismatch: expected {expected_hash.lower()}, "
            f"got {actual_hash}"
        )
    return ArtifactBinding(
        name=name,
        path=path,
        relative_path=str(relative_path).replace("\\", "/"),
        sha256=actual_hash,
        size_bytes=size,
    )


def _local_urdf_mesh_path(filename: str, urdf_path: Path, asset_root: Path) -> Path:
    if filename.startswith("package://"):
        remainder = filename[len("package://"):]
        parts = Path(remainder).parts
        if len(parts) < 2:
            raise AssetSchemaError(f"invalid package URI in URDF: {filename}")
        candidate = (asset_root / Path(*parts[1:])).resolve()
    elif filename.startswith("file://"):
        candidate = Path(filename[len("file://"):]).resolve()
    else:
        raw = Path(filename)
        candidate = (raw if raw.is_absolute() else urdf_path.parent / raw).resolve()
    try:
        candidate.relative_to(asset_root)
    except ValueError as exc:
        raise AssetSchemaError(f"URDF mesh escapes asset_root: {filename}") from exc
    return candidate


def _validate_urdf(path: Path, asset_root: Path) -> UrdfSummary:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise AssetSchemaError(f"invalid URDF XML: {path}") from exc
    if root.tag != "robot":
        raise AssetSchemaError("accepted_urdf root element must be <robot>")
    robot_name = root.attrib.get("name", "")
    if not robot_name:
        raise AssetSchemaError("accepted_urdf robot name is missing")

    links = root.findall("link")
    link_names = tuple(item.attrib.get("name", "") for item in links)
    if any(not item for item in link_names) or len(set(link_names)) != len(link_names):
        raise AssetSchemaError("URDF link names must be unique and non-empty")
    if len(link_names) != EXPECTED_LINK_COUNT:
        raise AssetSchemaError(
            f"accepted B601 URDF must contain {EXPECTED_LINK_COUNT} links; "
            f"found {len(link_names)}"
        )

    masses: list[float] = []
    for link in links:
        mass_node = link.find("./inertial/mass")
        if mass_node is None or "value" not in mass_node.attrib:
            raise AssetSchemaError(f"URDF link {link.attrib['name']} has no authoritative mass")
        try:
            mass = float(mass_node.attrib["value"])
        except ValueError as exc:
            raise AssetSchemaError(f"invalid mass on URDF link {link.attrib['name']}") from exc
        if not math.isfinite(mass) or mass <= 0.0:
            raise AssetSchemaError(f"URDF link {link.attrib['name']} mass must be positive")
        masses.append(mass)

    joints = root.findall("joint")
    joint_names = tuple(item.attrib.get("name", "") for item in joints)
    if any(not item for item in joint_names) or len(set(joint_names)) != len(joint_names):
        raise AssetSchemaError("URDF joint names must be unique and non-empty")
    if len(joint_names) != EXPECTED_JOINT_COUNT:
        raise AssetSchemaError(
            f"accepted B601 URDF must contain {EXPECTED_JOINT_COUNT} joints; "
            f"found {len(joint_names)}"
        )

    type_counts: dict[str, int] = {}
    children: set[str] = set()
    adjacency: dict[str, list[str]] = {name: [] for name in link_names}
    for joint in joints:
        joint_type = joint.attrib.get("type", "")
        if joint_type == "continuous":
            joint_type = "revolute"
        type_counts[joint_type] = type_counts.get(joint_type, 0) + 1
        parent_node = joint.find("parent")
        child_node = joint.find("child")
        parent = parent_node.attrib.get("link", "") if parent_node is not None else ""
        child = child_node.attrib.get("link", "") if child_node is not None else ""
        if parent not in adjacency or child not in adjacency:
            raise AssetSchemaError(f"URDF joint {joint.attrib['name']} references an unknown link")
        if child in children:
            raise AssetSchemaError(f"URDF link has more than one parent: {child}")
        children.add(child)
        adjacency[parent].append(child)
    if type_counts != EXPECTED_JOINT_TYPES:
        raise AssetSchemaError(
            "accepted B601 URDF joint distribution must be 6R + 1 fixed + 2P; "
            f"found {type_counts}"
        )
    roots = [name for name in link_names if name not in children]
    if len(roots) != 1:
        raise AssetSchemaError(f"URDF must have exactly one root link; found {roots}")
    visited: set[str] = set()

    def visit(link_name: str) -> None:
        if link_name in visited:
            raise AssetSchemaError("URDF kinematic graph contains a cycle")
        visited.add(link_name)
        for child_name in adjacency[link_name]:
            visit(child_name)

    visit(roots[0])
    if visited != set(link_names):
        raise AssetSchemaError("URDF kinematic graph is disconnected")

    mesh_paths: list[Path] = []
    for mesh_node in root.findall(".//mesh"):
        filename = mesh_node.attrib.get("filename", "")
        if not filename:
            raise AssetSchemaError("URDF mesh filename is empty")
        mesh_path = _local_urdf_mesh_path(filename, path, asset_root)
        if not mesh_path.is_file() or mesh_path.stat().st_size <= 0:
            raise MechanicalAssetError(f"URDF-referenced mesh does not exist: {mesh_path}")
        mesh_paths.append(mesh_path)

    total_mass = math.fsum(masses)
    if not math.isclose(total_mass, B601_ACCEPTED_MASS_KG, rel_tol=0.0, abs_tol=1e-9):
        raise AssetSchemaError(
            f"accepted URDF B601 mass must be {B601_ACCEPTED_MASS_KG:.9f} kg; "
            f"found {total_mass:.9f} kg"
        )
    return UrdfSummary(
        robot_name=robot_name,
        link_names=link_names,
        joint_names=joint_names,
        joint_type_counts=dict(sorted(type_counts.items())),
        root_link=roots[0],
        total_mass_kg=total_mass,
        mesh_paths=tuple(mesh_paths),
    )


def _frame_records(document: Mapping[str, Any]) -> list[tuple[str, str | None]]:
    raw_frames = document.get("frames")
    if isinstance(raw_frames, Mapping):
        records: list[tuple[str, str | None]] = []
        for frame_id, value in raw_frames.items():
            item = _require_mapping(value, f"frames.{frame_id}")
            records.append((str(frame_id), item.get("parent")))
        return records
    records = []
    for index, value in enumerate(_require_sequence(raw_frames, "frame_tree.frames")):
        item = _require_mapping(value, f"frame_tree.frames[{index}]")
        frame_id = item.get("id", item.get("frame_id"))
        records.append((frame_id, item.get("parent")))
    return records


def _validate_frame_tree(path: Path) -> FrameTreeSummary:
    document = _load_document(path)
    records = _frame_records(document)
    parent_by_frame: dict[str, str | None] = {}
    for frame_id, parent in records:
        if not isinstance(frame_id, str) or not frame_id.strip():
            raise AssetSchemaError("frame IDs must be non-empty strings")
        if frame_id in parent_by_frame:
            raise AssetSchemaError(f"duplicate frame ID: {frame_id}")
        if parent is not None and (not isinstance(parent, str) or not parent.strip()):
            raise AssetSchemaError(f"invalid parent for frame {frame_id}")
        parent_by_frame[frame_id] = parent
    if not parent_by_frame:
        raise AssetSchemaError("frame tree must not be empty")
    roots = [frame_id for frame_id, parent in parent_by_frame.items() if parent is None]
    declared_root = document.get("root_frame")
    if len(roots) != 1 or (declared_root is not None and declared_root != roots[0]):
        raise AssetSchemaError(
            f"frame tree must have one consistent root; roots={roots}, declared={declared_root}"
        )
    for frame_id, parent in parent_by_frame.items():
        if parent is not None and parent not in parent_by_frame:
            raise AssetSchemaError(f"frame {frame_id} references unknown parent {parent}")
    for frame_id in parent_by_frame:
        seen: set[str] = set()
        cursor: str | None = frame_id
        while cursor is not None:
            if cursor in seen:
                raise AssetSchemaError(f"frame tree cycle includes {cursor}")
            seen.add(cursor)
            cursor = parent_by_frame[cursor]
        if roots[0] not in seen:
            raise AssetSchemaError(f"frame {frame_id} is disconnected from root")
    return FrameTreeSummary(
        root_frame=roots[0],
        frame_ids=tuple(parent_by_frame),
        parent_by_frame=parent_by_frame,
    )


def _finite_vector(value: Any, length: int, label: str) -> tuple[float, ...]:
    sequence = _require_sequence(value, label)
    if len(sequence) != length:
        raise AssetSchemaError(f"{label} must contain {length} numbers")
    try:
        output = tuple(float(item) for item in sequence)
    except (TypeError, ValueError) as exc:
        raise AssetSchemaError(f"{label} must contain numbers") from exc
    if not all(math.isfinite(item) for item in output):
        raise AssetSchemaError(f"{label} must contain finite numbers")
    return output


def _validate_manifest_semantics(
    document: Mapping[str, Any],
    urdf: UrdfSummary,
    frame_tree: FrameTreeSummary,
) -> tuple[
    tuple[str, ...], tuple[Mapping[str, Any], ...], tuple[str, ...],
    Mapping[str, Any], tuple[str, ...], tuple[Mapping[str, Any], ...], Mapping[str, Any]
]:
    configurations = _unique_nonempty_strings(
        document.get("accepted_configurations"), "accepted_configurations")
    required_configurations = {"DEPLOYED_NOMINAL", "ARM_TASK_READY"}
    missing = required_configurations - set(configurations)
    if missing:
        raise AssetSchemaError(f"accepted configurations missing: {sorted(missing)}")

    grasp_candidates: list[Mapping[str, Any]] = []
    candidate_ids: set[str] = set()
    for index, raw in enumerate(_require_sequence(
        document.get("gripper_contact_frames"), "gripper_contact_frames"
    )):
        item = _require_mapping(raw, f"gripper_contact_frames[{index}]")
        candidate_id = item.get("id")
        frame_id = item.get("frame_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise AssetSchemaError("gripper contact candidate ID is missing")
        if candidate_id in candidate_ids:
            raise AssetSchemaError(f"duplicate grasp candidate: {candidate_id}")
        if frame_id not in frame_tree.parent_by_frame:
            raise AssetSchemaError(f"gripper contact frame is absent from frame tree: {frame_id}")
        normal = _finite_vector(item.get("surface_normal"), 3, "surface_normal")
        if math.sqrt(math.fsum(component * component for component in normal)) <= 0.0:
            raise AssetSchemaError(f"grasp candidate {candidate_id} has a zero surface normal")
        candidate_ids.add(candidate_id)
        grasp_candidates.append({**item, "surface_normal": normal})
    if not grasp_candidates:
        raise AssetSchemaError("at least one gripper contact frame is required")

    timing_ids = _unique_nonempty_strings(
        document.get("capture_timing_ids"), "capture_timing_ids")
    mount = _require_mapping(document.get("m3r_mount_transform"), "m3r_mount_transform")
    for key in ("parent_frame", "child_frame"):
        if mount.get(key) not in frame_tree.parent_by_frame:
            raise AssetSchemaError(f"m3r_mount_transform.{key} is absent from frame tree")
    translation = _finite_vector(mount.get("translation_m"), 3, "m3r translation")
    quaternion = _finite_vector(mount.get("quaternion_xyzw"), 4, "m3r quaternion")
    qnorm = math.sqrt(math.fsum(item * item for item in quaternion))
    if not math.isclose(qnorm, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise AssetSchemaError("m3r_mount_transform quaternion must be normalized")
    mount = {**mount, "translation_m": translation, "quaternion_xyzw": quaternion}

    camera_frames = _unique_nonempty_strings(
        document.get("camera_reserve_frames"), "camera_reserve_frames")
    for frame_id in camera_frames:
        if frame_id not in frame_tree.parent_by_frame:
            raise AssetSchemaError(f"camera reserve frame is absent from frame tree: {frame_id}")
    keep_out_raw = _require_sequence(document.get("keep_out"), "keep_out")
    keep_out = tuple(_require_mapping(item, f"keep_out[{index}]")
                     for index, item in enumerate(keep_out_raw))
    for index, item in enumerate(keep_out):
        if item.get("frame_id") not in frame_tree.parent_by_frame:
            raise AssetSchemaError(f"keep_out[{index}] frame is absent from frame tree")

    mass_and_inertia = _require_mapping(
        document.get("mass_and_inertia"), "mass_and_inertia")
    if mass_and_inertia.get("authority") != "accepted_urdf":
        raise AssetSchemaError("B601 mass authority must be accepted_urdf, never a mesh")
    try:
        declared_mass = float(mass_and_inertia.get("b601_total_mass_kg"))
    except (TypeError, ValueError) as exc:
        raise AssetSchemaError("mass_and_inertia.b601_total_mass_kg is invalid") from exc
    if not math.isclose(declared_mass, urdf.total_mass_kg, rel_tol=0.0, abs_tol=1e-9):
        raise AssetSchemaError("manifest B601 mass does not match accepted URDF")
    return (
        configurations,
        tuple(grasp_candidates),
        timing_ids,
        mount,
        camera_frames,
        keep_out,
        mass_and_inertia,
    )


def load_mechanical_assets(manifest_path: str | Path) -> MechanicalAssetBundle:
    """Load and fully validate ``MECH_RL_INTERFACE_V1.yaml``.

    Validation binds raw SHA-256 hashes before parsing, checks the accepted
    B601 topology (10 links, 9 joints, 6R+1F+2P), proves that both the URDF and
    system frame graphs are trees, and confirms every declared mesh exists.
    """
    path = Path(manifest_path).resolve()
    if path.name != "MECH_RL_INTERFACE_V1.yaml":
        raise AssetSchemaError("manifest must be named MECH_RL_INTERFACE_V1.yaml")
    if not path.is_file():
        raise MechanicalAssetError(f"mechanical interface manifest does not exist: {path}")
    document = _load_document(path)
    if document.get("schema_version") != INTERFACE_SCHEMA_VERSION:
        raise AssetSchemaError(
            f"schema_version must be {INTERFACE_SCHEMA_VERSION}"
        )
    asset_root_value = document.get("asset_root", ".")
    if not isinstance(asset_root_value, str) or Path(asset_root_value).is_absolute():
        raise AssetSchemaError("asset_root must be a relative path")
    asset_root = (path.parent / asset_root_value).resolve()
    if not asset_root.is_dir():
        raise MechanicalAssetError(f"asset_root does not exist: {asset_root}")

    artifact_records = _require_mapping(document.get("artifacts"), "artifacts")
    required_artifacts = ("accepted_urdf", "visual_mesh", "collision_mesh", "frame_tree")
    artifacts = {
        name: _load_artifact_binding(name, artifact_records.get(name), asset_root)
        for name in required_artifacts
    }
    for mesh_name in ("visual_mesh", "collision_mesh"):
        suffix = artifacts[mesh_name].path.suffix.lower()
        if suffix not in _MESH_SUFFIXES:
            raise AssetSchemaError(f"{mesh_name} has unsupported mesh suffix: {suffix}")

    urdf = _validate_urdf(artifacts["accepted_urdf"].path, asset_root)
    frame_tree = _validate_frame_tree(artifacts["frame_tree"].path)
    (
        configurations,
        grasp_candidates,
        timing_ids,
        mount,
        camera_frames,
        keep_out,
        mass_and_inertia,
    ) = _validate_manifest_semantics(document, urdf, frame_tree)
    return MechanicalAssetBundle(
        manifest_path=path,
        manifest_sha256=sha256_file(path),
        asset_root=asset_root,
        artifacts=artifacts,
        urdf=urdf,
        frame_tree=frame_tree,
        accepted_configurations=configurations,
        grasp_candidates=grasp_candidates,
        capture_timing_ids=timing_ids,
        m3r_mount_transform=mount,
        camera_reserve_frames=camera_frames,
        keep_out=keep_out,
        mass_and_inertia=mass_and_inertia,
    )


__all__ = [
    "AssetHashMismatch",
    "AssetSchemaError",
    "ArtifactBinding",
    "B601_ACCEPTED_MASS_KG",
    "FrameTreeSummary",
    "MechanicalAssetBundle",
    "MechanicalAssetError",
    "UrdfSummary",
    "load_mechanical_assets",
    "sha256_file",
]
