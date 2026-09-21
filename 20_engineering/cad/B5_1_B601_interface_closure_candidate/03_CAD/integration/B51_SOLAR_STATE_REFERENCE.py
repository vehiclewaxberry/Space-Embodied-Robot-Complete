"""STEP generator for STOW and deployed solar endpoint references.

The real B601 geometry remains bound in the primary integration STEP; this
smaller diagnostic file exists to make the two solar endpoint states legible.
It is not continuous-clearance evidence.
"""

from b51_spacecraft_context_common import build_solar_state_reference


MODEL_KIND = "assembly"
MODEL_NAME = "B51_SOLAR_STATE_REFERENCE"


def gen_step():
    return build_solar_state_reference()

