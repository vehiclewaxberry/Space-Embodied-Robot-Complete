"""Per-solid intersection, because whole-compound booleans lose real overlaps here.

Measured on this model with OCP/OCCT: a pin driven straight through the installed
MAIN PCBA returns 0.000000 mm3 from BRepAlgoAPI_Common on the 40-solid compound
and 70.400000 mm3 when the same pin is intersected with the compound's solids one
at a time. The same happens for the AUX board against the dual battery tie rods
(0.0 vs 11.97). All three PCBA compounds contain self-overlapping solids — the
board body is Z-scaled to the 1.6 mm nominal stack while KiCad puts components on
the 1.595 mm datum — and a boolean argument that self-intersects is not a valid
operand, so the result cannot be relied on.

A synthetic compound of two overlapping boxes does *not* reproduce it, so this is
not a blanket "compounds are broken" claim: it is a property of these operands.
Screening solid by solid is unconditionally safe, so that is what this does.
"""
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

_cache = {}


def solids(shape, key=None):
    if key is not None and key in _cache:
        return _cache[key]
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    out = []
    while ex.More():
        out.append(ex.Current())
        ex.Next()
    out = out or [shape]
    if key is not None:
        _cache[key] = out
    return out


def overlap(g, common, a_shape, b_shape, a_key=None, b_key=None, bounds=None):
    """Total intersection volume, summed over every solid pair.

    `bounds` is an optional callable returning a shape's (lo, hi) so pairs whose
    boxes cannot touch are skipped; it only ever skips pairs with no overlap.
    Returns (volume, errors) and never swallows a failure silently.
    """
    A = solids(a_shape, a_key)
    B = solids(b_shape, b_key)
    total = 0.0
    errors = []
    for i, sa in enumerate(A):
        la = bounds(sa) if bounds else None
        for j, sb in enumerate(B):
            if la is not None:
                lb = bounds(sb)
                if any(lb[1][k] < la[0][k] or la[1][k] < lb[0][k] for k in range(3)):
                    continue
            try:
                total += g.volume(common(sa, sb))
            except Exception as e:
                errors.append(dict(a_solid=i, b_solid=j, error=str(e)))
    return total, errors
