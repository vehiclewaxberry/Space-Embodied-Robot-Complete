from __future__ import annotations

import copy
import xml.etree.ElementTree as ET

import pytest

from preexec_security.urdf_contract import URDFContractError, build_synthetic_parser_fixture_bytes, validate_system_urdf_bytes


def _mutate(callback) -> bytes:
    root = ET.fromstring(build_synthetic_parser_fixture_bytes())
    callback(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def test_exact_synthetic_fixture_validates_without_release_credit() -> None:
    result = validate_system_urdf_bytes(build_synthetic_parser_fixture_bytes())
    assert result == {
        "robot_name": "unified_r2_c01_no_route_c_sim_candidate_v2",
        "links": 19, "physical_links": 16, "frame_only_links": 3,
        "joints": 18, "fixed": 10, "revolute": 6, "prismatic": 2,
        "actuated_dof": 8, "total_mass_kg": 31.022864807342987,
        "mesh_references": 0, "visual_box_count": 16, "collision_box_count": 16,
        "geometry_contract": "EXACT_SOURCE_STATIC_PRIMITIVE_BROADPHASE_ONLY__NO_NARROWPHASE_OR_PHYSICAL_CONTACT_CREDIT",
        "numeric_comparison": "EXACT_PARSED_FLOAT_NO_TOLERANCE", "fixture_only": True,
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda root: root.set("forged", "1"),
        lambda root: root.find("link").set("forged", "1"),
        lambda root: root.find("joint").set("forged", "1"),
        lambda root: root.find("link/inertial").set("forged", "1"),
        lambda root: root.find("link/inertial/origin").set("forged", "1"),
        lambda root: root.find("joint/parent").set("forged", "1"),
        lambda root: root.find("joint/origin").set("forged", "1"),
    ],
)
def test_extra_attributes_fail_closed(mutation) -> None:
    with pytest.raises(URDFContractError):
        validate_system_urdf_bytes(_mutate(mutation))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda root: ET.SubElement(root, "gazebo"),
        lambda root: ET.SubElement(root.find("link"), "forged"),
        lambda root: root.find("link/inertial").append(copy.deepcopy(root.find("link/inertial/mass"))),
        lambda root: root.find("joint").append(copy.deepcopy(root.find("joint/parent"))),
        lambda root: root.find("link").append(copy.deepcopy(root.find("link/inertial"))),
    ],
)
def test_unknown_or_duplicate_elements_fail_closed(mutation) -> None:
    with pytest.raises(URDFContractError):
        validate_system_urdf_bytes(_mutate(mutation))


def test_exact_inertia_axis_limit_and_geometry_class_are_enforced() -> None:
    def inertia(root):
        root.find("link/inertial/inertia").set("ixx", "9")
    def axis(root):
        root.find("joint[@name='joint2']/axis").set("xyz", "0 0 1")
    def limit(root):
        root.find("joint[@name='joint1']/limit").set("upper", "2.7")
    def geometry(root):
        link = root.find("link[@name='link1']")
        link.remove(link.find("collision"))
    for mutation in (inertia, axis, limit, geometry):
        with pytest.raises(URDFContractError):
            validate_system_urdf_bytes(_mutate(mutation))


def test_mesh_is_path_checked_then_forbidden_by_primitive_contract() -> None:
    def replace_box(root, filename):
        geometry = root.find("link[@name='link1']/visual/geometry")
        geometry.remove(geometry.find("box"))
        ET.SubElement(geometry, "mesh", {"filename": filename})
    with pytest.raises(URDFContractError, match="UNSAFE_MESH_REFERENCE"):
        validate_system_urdf_bytes(_mutate(lambda root: replace_box(root, "meshes//escape.stl")))
    with pytest.raises(URDFContractError, match="MESH_GEOMETRY_FORBIDDEN"):
        validate_system_urdf_bytes(_mutate(lambda root: replace_box(root, "meshes/safe_local.stl")))


@pytest.mark.parametrize(
    ("link_name", "field", "drift"),
    [
        ("bus_primary_structure_candidate_v1", "xyz", "1e-30 0 0"),
        ("link1", "rpy", "0 0 1e-30"),
        ("link1", "size", "1000000000 0.07725002229885372 0.09854998779296875"),
    ],
)
def test_exact_source_static_broadphase_rejects_tiny_and_huge_drift(link_name: str, field: str, drift: str) -> None:
    def mutate(root):
        visual = root.find(f"link[@name='{link_name}']/visual")
        if field == "size":
            visual.find("geometry/box").set("size", drift)
        else:
            visual.find("origin").set(field, drift)
    with pytest.raises(URDFContractError, match="EXACT_NUMERIC_MISMATCH"):
        validate_system_urdf_bytes(_mutate(mutate))


def test_exact_no_geometry_links_reject_primitive_contamination() -> None:
    def mutate(root):
        source = copy.deepcopy(root.find("link[@name='link1']/visual"))
        root.find("link[@name='spacecraft_bus']").append(source)
    with pytest.raises(URDFContractError):
        validate_system_urdf_bytes(_mutate(mutate))


def test_dtd_and_entity_are_rejected_before_parse() -> None:
    payload = b'<?xml version="1.0"?><!DOCTYPE robot [<!ENTITY x "bad">]><robot name="x"/>'
    with pytest.raises(URDFContractError, match="DTD_OR_ENTITY"):
        validate_system_urdf_bytes(payload)
