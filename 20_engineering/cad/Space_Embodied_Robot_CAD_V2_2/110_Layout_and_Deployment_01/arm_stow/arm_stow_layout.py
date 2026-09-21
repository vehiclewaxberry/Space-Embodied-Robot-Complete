"""STEP-first V22 top-deck arm-stow and equipment-zoning layout.

All physical items are DESIGN_PROPOSAL/TBD/HOLD.  All keep-outs and
reservations are explicitly NON_PHYSICAL.  This file has no mass, strength,
stiffness, vendor-shell support, manufacturing, or flight-qualification
authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from build123d import Align, Box, Color, Compound, Location


MODEL_NAME = "V22_GATE4_ARM_STOW_AND_TOP_EQUIPMENT_LAYOUT"
MODEL_KIND = "assembly"
SPEC_PATH = Path(__file__).with_name("interface_claim_registry.json")

STYLE = {
    "physical_crossbeam": Color(0.28, 0.34, 0.42, 1.0),
    "physical_bracket": Color(0.86, 0.48, 0.14, 1.0),
    "frozen_keep_out": Color(0.88, 0.12, 0.12, 0.75),
    "proposal_clearance": Color(1.0, 0.55, 0.05, 0.60),
    "arm_reservation": Color(0.80, 0.20, 0.75, 0.55),
    "equipment_band": Color(0.12, 0.45, 0.90, 0.55),
    "radiator": Color(0.10, 0.75, 0.80, 0.80),
    "sensor": Color(0.20, 0.78, 0.32, 0.65),
    "antenna": Color(0.58, 0.30, 0.86, 0.65),
}


def load_spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _bbox_size_and_center(bbox: list[float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    size = (xmax - xmin, ymax - ymin, zmax - zmin)
    center = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)
    if min(size) <= 0.0:
        raise ValueError(f"Non-positive bbox size: {bbox}")
    return size, center


def _entity_color(entity: dict[str, Any]) -> Color:
    entity_id = entity["id"]
    if entity_id.startswith("CROSSBEAM"):
        return STYLE["physical_crossbeam"]
    if entity["classification"].startswith("PHYSICAL"):
        return STYLE["physical_bracket"]
    if entity_id == "ARM_KEEP_OUT_FROZEN":
        return STYLE["frozen_keep_out"]
    if entity_id == "ARM_OUTER_CLEARANCE_PROPOSAL":
        return STYLE["proposal_clearance"]
    if entity_id.startswith("EQUIPMENT_BAND"):
        return STYLE["equipment_band"]
    if entity_id.startswith("RADIATOR"):
        return STYLE["radiator"]
    if entity_id.startswith("SENSOR"):
        return STYLE["sensor"]
    if entity_id.startswith("ANTENNA"):
        return STYLE["antenna"]
    return STYLE["arm_reservation"]


def _make_box(entity: dict[str, Any]):
    size, center = _bbox_size_and_center(entity["bbox"])
    shape = Box(*size, align=(Align.CENTER, Align.CENTER, Align.CENTER)).moved(Location(center))
    shape.label = entity["label"]
    shape.color = _entity_color(entity)
    return shape


def _make_cage(entity: dict[str, Any], edge: float):
    xmin, ymin, zmin, xmax, ymax, zmax = entity["bbox"]
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    if min(dx, dy, dz) <= 2.0 * edge:
        raise ValueError(f"Envelope too small for edge cage: {entity['id']}")

    color = _entity_color(entity)
    bars = []

    def add_bar(lengths, center, suffix):
        bar = Box(*lengths, align=(Align.CENTER, Align.CENTER, Align.CENTER)).moved(Location(center))
        bar.label = f"{entity['label']}:{suffix}"
        bar.color = color
        bars.append(bar)

    xmid, ymid, zmid = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0
    y_edges = (ymin + edge / 2.0, ymax - edge / 2.0)
    z_edges = (zmin + edge / 2.0, zmax - edge / 2.0)
    x_edges = (xmin + edge / 2.0, xmax - edge / 2.0)

    for yi, y in enumerate(y_edges):
        for zi, z in enumerate(z_edges):
            add_bar((dx, edge, edge), (xmid, y, z), f"edge_x_{yi}_{zi}")
    for xi, x in enumerate(x_edges):
        for zi, z in enumerate(z_edges):
            add_bar((edge, dy, edge), (x, ymid, z), f"edge_y_{xi}_{zi}")
    for xi, x in enumerate(x_edges):
        for yi, y in enumerate(y_edges):
            add_bar((edge, edge, dz), (x, y, zmid), f"edge_z_{xi}_{yi}")

    cage = Compound(children=bars, label=entity["label"])
    return cage


def make_entities() -> dict[str, Any]:
    spec = load_spec()
    edge = spec["proposal_parameters"]["envelope_edge_thickness"]["value"]
    entities = {}
    for entity in spec["entities"]:
        if entity["geometry_type"] == "box":
            shape = _make_box(entity)
        elif entity["geometry_type"] == "cage":
            shape = _make_cage(entity, edge)
        else:
            raise ValueError(f"Unsupported geometry type: {entity['geometry_type']}")
        entities[entity["id"]] = shape
    return entities


def gen_step():
    spec = load_spec()
    entities = make_entities()
    children_by_group = {group_id: [] for group_id in spec["groups"]}
    for entity in spec["entities"]:
        children_by_group[entity["group"]].append(entities[entity["id"]])

    groups = []
    for group_id, group_label in spec["groups"].items():
        groups.append(Compound(children=children_by_group[group_id], label=group_label))

    return Compound(children=groups, label=MODEL_NAME)


if __name__ == "__main__":
    # STEP writing is intentionally owned by the CAD skill CLI.
    model = gen_step()
    print(MODEL_NAME)
    print(f"solids={len(model.solids())}")
    print(f"bbox={model.bounding_box().size}")
