"""Automated URDF extraction (no hand re-typing of parameters).

Extracts links/joints/inertials from a URDF file into a plain dict, together
with source SHA-256 provenance. Raises on structural violations instead of
guessing (fail-closed).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from .frames import rpy_to_R
from .hashing import sha256_file


class UrdfContractViolation(RuntimeError):
    pass


def _floats(s: str, n: int) -> list[float]:
    vals = [float(v) for v in s.replace(",", " ").split()]
    if len(vals) != n:
        raise UrdfContractViolation(f"expected {n} floats, got {s!r}")
    return vals


def extract_urdf(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise UrdfContractViolation(f"URDF not found: {path}")
    sha = sha256_file(path)
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "robot":
        raise UrdfContractViolation(f"root tag {root.tag!r} != 'robot'")

    links = []
    for le in root.findall("link"):
        name = le.attrib["name"]
        inertial = None
        ie = le.find("inertial")
        if ie is not None:
            oe = ie.find("origin")
            xyz = _floats(oe.attrib.get("xyz", "0 0 0"), 3) if oe is not None else [0.0, 0.0, 0.0]
            rpy = _floats(oe.attrib.get("rpy", "0 0 0"), 3) if oe is not None else [0.0, 0.0, 0.0]
            me = ie.find("mass")
            if me is None:
                raise UrdfContractViolation(f"link {name}: inertial without mass")
            mass = float(me.attrib["value"])
            ne = ie.find("inertia")
            if ne is None:
                raise UrdfContractViolation(f"link {name}: inertial without inertia tensor")
            ixx = float(ne.attrib["ixx"])
            ixy = float(ne.attrib["ixy"])
            ixz = float(ne.attrib["ixz"])
            iyy = float(ne.attrib["iyy"])
            iyz = float(ne.attrib["iyz"])
            izz = float(ne.attrib["izz"])
            I_raw = np.array([[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]], dtype=float)
            # URDF: tensor about CoM, expressed in the inertial-origin frame.
            # Rotate into the link frame: I_link = R I R^T.
            R = rpy_to_R(rpy)
            I_com_link = R @ I_raw @ R.T
            inertial = {
                "mass": mass,
                "com": xyz,
                "inertia_com": I_com_link.tolist(),
                "inertial_origin_rpy": rpy,
            }
        links.append(
            {
                "name": name,
                "inertial": inertial,
                "has_visual": le.find("visual") is not None,
                "has_collision": le.find("collision") is not None,
            }
        )

    joints = []
    for je in root.findall("joint"):
        name = je.attrib["name"]
        jtype = je.attrib["type"]
        if jtype not in ("revolute", "prismatic", "fixed", "continuous", "floating", "planar"):
            raise UrdfContractViolation(f"joint {name}: unsupported type {jtype!r}")
        parent = je.find("parent").attrib["link"]
        child = je.find("child").attrib["link"]
        oe = je.find("origin")
        xyz = _floats(oe.attrib.get("xyz", "0 0 0"), 3) if oe is not None else [0.0, 0.0, 0.0]
        rpy = _floats(oe.attrib.get("rpy", "0 0 0"), 3) if oe is not None else [0.0, 0.0, 0.0]
        ae = je.find("axis")
        axis = _floats(ae.attrib["xyz"], 3) if ae is not None else None
        if axis is not None:
            n = float(np.linalg.norm(axis))
            if jtype in ("revolute", "prismatic", "continuous"):
                if n == 0.0:
                    raise UrdfContractViolation(f"joint {name}: zero axis on a movable joint")
                axis = (np.asarray(axis) / n).tolist()
        le_ = je.find("limit")
        limits = None
        if le_ is not None:
            limits = {
                k: float(le_.attrib[k]) for k in ("lower", "upper", "effort", "velocity") if k in le_.attrib
            }
        joints.append(
            {
                "name": name,
                "type": jtype,
                "parent": parent,
                "child": child,
                "origin_xyz": xyz,
                "origin_rpy": rpy,
                "axis": axis,
                "limits": limits,
            }
        )

    model = {
        "robot_name": root.attrib.get("name", ""),
        "links": links,
        "joints": joints,
        "provenance": {"source_path": str(path), "source_sha256": sha},
    }
    validate_tree(model)
    return model


def validate_tree(model: dict) -> dict:
    """Structural validation: unique names, single root, connected, acyclic.
    Returns a topology report dict; raises UrdfContractViolation on violation."""
    link_names = [l["name"] for l in model["links"]]
    if len(set(link_names)) != len(link_names):
        raise UrdfContractViolation("duplicate link names")
    jnames = [j["name"] for j in model["joints"]]
    if len(set(jnames)) != len(jnames):
        raise UrdfContractViolation("duplicate joint names")
    children = {}
    for j in model["joints"]:
        if j["parent"] not in link_names or j["child"] not in link_names:
            raise UrdfContractViolation(f"joint {j['name']}: parent/child not among links")
        if j["child"] in children:
            raise UrdfContractViolation(f"link {j['child']} has two parent joints")
        children[j["child"]] = j["name"]
    roots = [n for n in link_names if n not in children]
    if len(roots) != 1:
        raise UrdfContractViolation(f"tree must have exactly one root, found {roots}")
    # connectivity + acyclicity via walk from root
    adj = {}
    for j in model["joints"]:
        adj.setdefault(j["parent"], []).append(j["child"])
    seen = set()
    stack = [roots[0]]
    while stack:
        n = stack.pop()
        if n in seen:
            raise UrdfContractViolation(f"cycle detected at link {n}")
        seen.add(n)
        stack.extend(adj.get(n, []))
    if seen != set(link_names):
        raise UrdfContractViolation(f"disconnected links: {set(link_names) - seen}")

    by_type: dict[str, int] = {}
    for j in model["joints"]:
        by_type[j["type"]] = by_type.get(j["type"], 0) + 1
    return {
        "root_link": roots[0],
        "n_links": len(link_names),
        "n_joints": len(model["joints"]),
        "joints_by_type": by_type,
        "links_with_inertial": sum(1 for l in model["links"] if l["inertial"] is not None),
        "movable_joints": [j["name"] for j in model["joints"] if j["type"] in ("revolute", "prismatic", "continuous")],
    }


def total_mass(model: dict) -> float:
    return float(sum(l["inertial"]["mass"] for l in model["links"] if l["inertial"] is not None))
