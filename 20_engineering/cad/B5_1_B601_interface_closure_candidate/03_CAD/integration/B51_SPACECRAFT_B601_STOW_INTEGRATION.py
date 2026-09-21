"""Primary STEP generator for the B5.1 static full-spacecraft STOW context."""

from b51_spacecraft_context_common import build_full_integration


MODEL_KIND = "assembly"
MODEL_NAME = "B51_SPACECRAFT_B601_STOW_INTEGRATION"


def gen_step():
    return build_full_integration()

