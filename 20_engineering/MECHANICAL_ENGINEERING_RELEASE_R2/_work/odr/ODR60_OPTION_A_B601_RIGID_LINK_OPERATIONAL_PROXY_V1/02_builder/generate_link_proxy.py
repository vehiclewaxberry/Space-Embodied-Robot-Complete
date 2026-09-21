"""build123d generator shared by the six B601 rigid-link STEP wrappers."""

from __future__ import annotations

from OCP.Font import Font_FontMgr
from OCP.TCollection import TCollection_AsciiString


# build123d scans every user font on first import on Windows.  This host has
# one non-font file with a font extension, so establish the same deterministic
# canary alias used by the current base_link proxy before importing build123d.
_font_manager = Font_FontMgr.GetInstance_s()
_font_manager.AddFontAlias(
    TCollection_AsciiString("singleline"), TCollection_AsciiString("Arial")
)

from build123d import Align, Box, Color, Compound, Location  # noqa: E402

from proxy_geometry import sectional_convex_cover


def gen_for_link(link_id: str):
    cover = sectional_convex_cover(link_id)
    children = []
    for slab_index, bounds_m in enumerate(cover["boxes_m"]):
        bounds_mm = bounds_m * 1000.0
        dimensions = bounds_mm[1] - bounds_mm[0]
        centre = 0.5 * (bounds_mm[0] + bounds_mm[1])
        solid = Box(
            float(dimensions[0]),
            float(dimensions[1]),
            float(dimensions[2]),
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).located(Location(tuple(float(value) for value in centre)))
        solid.label = f"{link_id.upper()}_CONVEX_COVER_SLAB_{slab_index:02d}"
        solid.color = Color(0.20, 0.62, 0.88, 0.62)
        solid.material = (
            "CONSERVATIVE_CONVEX_HULL_CROSS_SECTION_AABB;"
            "COLLISION_ONLY_NOT_CONTACT_STRENGTH_MASS_OR_HARDWARE_AUTHORITY"
        )
        children.append(solid)
    result = Compound(children=children, label=f"B601_{link_id.upper()}_OPERATIONAL_COLLISION_PROXY_V1")
    result.material = (
        f"B601_{link_id.upper()}_LINK_LOCAL;UNITS_MM;TWELVE_SLAB_CONSERVATIVE_PROXY;"
        "NO_SYSTEM_PAIR_OR_PATH_AUTHORITY"
    )
    return result
