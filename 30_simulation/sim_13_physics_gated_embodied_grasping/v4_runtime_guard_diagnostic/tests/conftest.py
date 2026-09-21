from __future__ import annotations

from pathlib import Path
import sys


V4_ROOT = Path(__file__).resolve().parents[1]
if str(V4_ROOT) not in sys.path:
    sys.path.insert(0, str(V4_ROOT))
