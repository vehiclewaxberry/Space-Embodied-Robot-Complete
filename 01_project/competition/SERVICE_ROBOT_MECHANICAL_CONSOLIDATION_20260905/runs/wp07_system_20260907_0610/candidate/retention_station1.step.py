"""Station 1 local static prefabrication candidate: 17 parts + parking saddle context.
Not a whole-spacecraft or continuous-motion completion result.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retention_station_view import build_view


def gen_step():
    return build_view(1)
