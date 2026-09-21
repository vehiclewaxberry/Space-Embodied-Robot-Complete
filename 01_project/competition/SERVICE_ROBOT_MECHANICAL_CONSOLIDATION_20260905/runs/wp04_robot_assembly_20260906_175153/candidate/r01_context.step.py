"""Service non-arm context, excluding the 12 replaced items and new hardware."""
from spacecraft_model import build, P, HERE
from build123d import Compound
import r01_design
def gen_step():
    _,shapes,receipt=build("service",include_arm=False)
    changed=set(r01_design.structures(P))
    keep=[r for r in receipt["instances"] if r["id"] not in changed and r["parent_assembly"]!="R01_FASTENERS"]
    return Compound(label="R01_UNCHANGED_SERVICE_CONTEXT",children=[shapes[r["id"]] for r in keep])

