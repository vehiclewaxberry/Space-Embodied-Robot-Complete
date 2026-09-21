"""Synthetic-only model construction and read-only authority hash records.

The current Unified-R2 source is intentionally never imported or executed in
this module.  Its files may be hashed as read-only provenance, but they are not
solver inputs.  The sole solver input is a deterministic, hand-authored,
in-memory XML fixture with six revolute and two prismatic joints.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


V3_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = V3_ROOT.parents[2]
V2_ROOT = V3_ROOT.parent / "v2_system_rebind"
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from sim13_v2.free_floating_dynamics import URDFTreeDynamics


FIXTURE_ID = "SYNTHETIC_8DOF_FREE_FLYER_V1"
FIXTURE_AUTHORITY_CLASS = "SYNTHETIC_ONLY_GENERIC_NUMERICAL_FIXTURE_NOT_CURRENT_SYSTEM"
UNIFIED_R2_SOURCE_DIR = PROJECT_ROOT / (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/source_only_v2"
)


def _fmt(values: tuple[float, ...]) -> str:
    return " ".join(f"{float(value):.17g}" for value in values)


def _add_inertial(
    link: ET.Element,
    *,
    mass_kg: float,
    com_m: tuple[float, float, float],
    principal_inertia_kg_m2: tuple[float, float, float],
) -> None:
    inertial = ET.SubElement(link, "inertial")
    ET.SubElement(inertial, "origin", {"xyz": _fmt(com_m), "rpy": "0 0 0"})
    ET.SubElement(inertial, "mass", {"value": f"{mass_kg:.17g}"})
    ixx, iyy, izz = principal_inertia_kg_m2
    ET.SubElement(
        inertial,
        "inertia",
        {
            "ixx": f"{ixx:.17g}",
            "ixy": "0",
            "ixz": "0",
            "iyy": f"{iyy:.17g}",
            "iyz": "0",
            "izz": f"{izz:.17g}",
        },
    )


def synthetic_8dof_xml_bytes() -> bytes:
    """Return the deterministic synthetic fixture as memory bytes only."""

    robot = ET.Element("robot", {"name": "synthetic_8dof_free_flyer_v1"})
    robot.append(
        ET.Comment(
            "SYNTHETIC_ONLY generic numerical fixture; not Unified-R2, not production, not contact"
        )
    )
    base = ET.SubElement(robot, "link", {"name": "synthetic_base"})
    _add_inertial(
        base,
        mass_kg=20.0,
        com_m=(0.03, -0.02, 0.015),
        principal_inertia_kg_m2=(1.35, 1.55, 1.80),
    )

    axes = (
        (0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 0.0),
    )
    origins = (
        (0.22, 0.00, 0.08),
        (0.34, 0.02, 0.00),
        (0.31, -0.015, 0.025),
        (0.27, 0.025, -0.02),
        (0.23, -0.02, 0.015),
        (0.19, 0.015, 0.01),
    )
    rpys = (
        (0.0, 0.0, 0.0),
        (0.12, -0.08, 0.05),
        (-0.06, 0.11, -0.09),
        (0.09, 0.04, 0.13),
        (-0.08, -0.10, 0.07),
        (0.05, -0.07, -0.11),
    )
    parent = "synthetic_base"
    for index in range(6):
        child = f"synthetic_link_{index + 1}"
        link = ET.SubElement(robot, "link", {"name": child})
        scale = float(index + 1)
        _add_inertial(
            link,
            mass_kg=1.8 - 0.12 * index,
            com_m=(0.13 - 0.008 * index, 0.006 * (-1) ** index, 0.004 * index),
            principal_inertia_kg_m2=(
                0.030 - 0.0020 * index,
                0.036 - 0.0022 * index,
                0.041 - 0.0024 * index,
            ),
        )
        joint = ET.SubElement(robot, "joint", {"name": f"synthetic_joint_{index + 1}", "type": "revolute"})
        ET.SubElement(joint, "parent", {"link": parent})
        ET.SubElement(joint, "child", {"link": child})
        ET.SubElement(joint, "origin", {"xyz": _fmt(origins[index]), "rpy": _fmt(rpys[index])})
        ET.SubElement(joint, "axis", {"xyz": _fmt(axes[index])})
        ET.SubElement(joint, "limit", {"lower": "-3", "upper": "3", "effort": f"{4.0 + scale:.17g}", "velocity": "2"})
        parent = child

    for finger_index, axis in ((1, (0.0, 1.0, 0.0)), (2, (0.0, 0.0, 1.0))):
        child = f"synthetic_finger_{finger_index}"
        link = ET.SubElement(robot, "link", {"name": child})
        _add_inertial(
            link,
            mass_kg=0.36 + 0.04 * finger_index,
            com_m=(0.055, 0.008 * (-1) ** finger_index, 0.005),
            principal_inertia_kg_m2=(0.0024, 0.0029, 0.0032),
        )
        joint = ET.SubElement(robot, "joint", {"name": f"synthetic_finger_joint_{finger_index}", "type": "prismatic"})
        ET.SubElement(joint, "parent", {"link": "synthetic_link_6"})
        ET.SubElement(joint, "child", {"link": child})
        ET.SubElement(
            joint,
            "origin",
            {
                "xyz": _fmt((0.17, 0.035 * (-1) ** finger_index, 0.025 * (finger_index - 1))),
                "rpy": _fmt((0.03 * finger_index, -0.02, 0.04 * (-1) ** finger_index)),
            },
        )
        ET.SubElement(joint, "axis", {"xyz": _fmt(axis)})
        ET.SubElement(joint, "limit", {"lower": "-0.03", "upper": "0.03", "effort": "2", "velocity": "0.2"})
    return ET.tostring(robot, encoding="utf-8")


def build_synthetic_8dof_model() -> URDFTreeDynamics:
    """Build the only model admitted to the V3 Phase-A solver."""

    return URDFTreeDynamics(synthetic_8dof_xml_bytes())


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def file_record(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def read_only_current_system_records() -> list[dict[str, object]]:
    """Hash static current-system files without importing or executing them."""

    names = (
        "unified_r2_urdf_source_v2.py",
        "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml",
        "UNIFIED_R2_URDF_SOURCE_GATE_V2.json",
        "UNIFIED_R2_URDF_SOURCE_STATIC_VALIDATION_V2.json",
    )
    return [file_record(UNIFIED_R2_SOURCE_DIR / name) for name in names]

