from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_builder"))
from generate_link_proxy import gen_for_link


def gen_step():
    return gen_for_link("link2")

