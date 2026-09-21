"""Permuted D-max rectangular allocation, not a physical battery BRep."""
from pathlib import Path
import json
from build123d import Box,Color
A=Path(__file__).resolve().parents[1]
def gen_step():
    b=json.loads((A/'mechanical/BATTERY_BAY_LAYOUT.json').read_text())['battery']
    assert sorted(b['size_S_mm'])==sorted([189.5,85.5,82.2])
    part=Box(*b['size_S_mm']);part.label=b['id'];part.color=Color(.88,.60,.16)
    return part
