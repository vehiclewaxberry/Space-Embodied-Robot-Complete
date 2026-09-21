"""Import the independent validator without importing the solver or runner."""

from pathlib import Path
import sys


PHASE_ROOT = Path(__file__).resolve().parents[1]
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))
