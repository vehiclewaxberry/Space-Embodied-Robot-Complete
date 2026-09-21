# -*- coding: utf-8 -*-
"""Create review-only static renders from the generated neutral STL files."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image, ImageDraw


ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
V4 = ROOT / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
CAD = V4 / "02_neutral_cad"
OUT = V4 / "10_validation/renders"


def equal_axes(ax, vertices):
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    center = (mins + maxs) / 2.0
    radius = max(maxs - mins) / 2.0
    radius = max(radius, 1.0)
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_box_aspect((1, 1, 1))


def render(title, items, output, elev=24, azim=-54):
    fig = plt.figure(figsize=(8, 7), facecolor="#f5f7fa")
    ax = fig.add_subplot(111, projection="3d")
    all_vertices = []
    for path, color, alpha, label in items:
        mesh = trimesh.load_mesh(path, process=False)
        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.to_mesh()
        triangles = mesh.vertices[mesh.faces]
        collection = Poly3DCollection(
            triangles,
            facecolors=color,
            edgecolors=(0.08, 0.10, 0.14, min(alpha, 0.35)),
            linewidths=0.12,
            alpha=alpha,
            label=label,
        )
        ax.add_collection3d(collection)
        all_vertices.append(mesh.vertices)
    vertices = np.vstack(all_vertices)
    equal_axes(ax, vertices)
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X / mm")
    ax.set_ylabel("Y / mm")
    ax.set_zlabel("Z / mm")
    ax.set_title(title, fontsize=13, pad=16)
    ax.grid(True, alpha=0.18)
    handles = [
        plt.Line2D([0], [0], marker="s", linestyle="", markersize=10, color=color, label=label)
        for _, color, _, label in items
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.9)
    fig.text(
        0.5,
        0.015,
        "Review render only — neutral candidate geometry, not native/manufacturing release",
        ha="center",
        fontsize=8,
        color="#4c566a",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    adapter = OUT / "MFINAL_ADAPTER_REVB2_REVIEW.png"
    render(
        "M-FINAL-01  Two-stage adapter Rev-B2",
        [
            (CAD / "adapter/V4_B601_STAGE_B_LOAD_ADAPTER_REVB2.stl", "#4c78a8", 0.82, "Stage B Rev-B2"),
            (CAD / "adapter/V4_B601_STAGE_A_INTERFACE_RING_REVB.stl", "#f58518", 0.88, "Stage A Rev-B"),
        ],
        adapter,
        elev=28,
        azim=-48,
    )
    wing = OUT / "MFINAL_WING_CLEVIS_REVIEW.png"
    render(
        "M-FINAL-02  Left/right three-web wing-root clevis",
        [
            (CAD / "wing_root/V4_WING_ROOT_THREE_WEB_CLEVIS_LEFT.stl", "#54a24b", 0.86, "Left"),
            (CAD / "wing_root/V4_WING_ROOT_THREE_WEB_CLEVIS_RIGHT.stl", "#e45756", 0.78, "Right"),
        ],
        wing,
        elev=24,
        azim=-62,
    )
    supports = OUT / "MFINAL_SUPPORTS_V2_REVIEW.png"
    support_items = []
    colors = {"G07": "#4c78a8", "G08": "#f58518", "MID": "#54a24b"}
    for tag in ("G07", "G08", "MID"):
        body_name = {"G07": "V4_G07_PRIMARY_SUPPORT", "G08": "V4_G08_PRIMARY_SUPPORT", "MID": "V4_MID_BACKUP_SUPPORT"}[tag]
        support_items.extend(
            [
                (CAD / f"supports/{body_name}.stl", colors[tag], 0.82, f"{tag} body"),
                (CAD / f"supports/V4_{tag}_PAD_CARRIER.stl", "#b279a2", 0.82, f"{tag} carrier"),
                (CAD / f"supports/V4_{tag}_CONTACT_PAD.stl", "#72b7b2", 0.9, f"{tag} pad"),
            ]
        )
    render("M-FINAL-03  G07/G08/Mid V2 support set", support_items, supports, elev=20, azim=-55)
    envelopes = OUT / "MFINAL_HDRM_HARNESS_ENVELOPES_REVIEW.png"
    render(
        "M-FINAL-04/05  HDRM and harness non-physical envelopes",
        [
            (CAD / "hdrm/V4_ARM_HDRM_RELEASE_SWEEP_KEEP_OUT.stl", "#e45756", 0.18, "HDRM -X sweep keepout"),
            (CAD / "hdrm/V4_ARM_HDRM_60MM_FLANGE_SKELETON.stl", "#f2cf5b", 0.55, "HDRM flange skeleton"),
            (CAD / "camera_harness/V4_HARNESS_STATIC_ROUTE_OD9_KEEP_OUT.stl", "#72b7b2", 0.82, "OD9 static route"),
        ],
        envelopes,
        elev=21,
        azim=-58,
    )

    images = [Image.open(path).convert("RGB") for path in (adapter, wing, supports, envelopes)]
    target_w = max(image.width for image in images)
    target_h = max(image.height for image in images)
    canvas = Image.new("RGB", (2 * target_w, 2 * target_h + 54), "white")
    for index, image in enumerate(images):
        x = (index % 2) * target_w + (target_w - image.width) // 2
        y = (index // 2) * target_h + 54 + (target_h - image.height) // 2
        canvas.paste(image, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 18), "F3R2 V4 competition mechanical candidate — neutral CAD review set", fill="#20242a")
    collage = OUT / "MFINAL_MECHANICAL_CANDIDATE_REVIEW_COLLAGE.png"
    canvas.save(collage, quality=95)
    print(collage)


if __name__ == "__main__":
    main()
