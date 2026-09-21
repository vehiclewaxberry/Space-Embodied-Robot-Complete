"""Current publisher bridge; V12 implementation is archived."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().with_name("publish_input_passive_addendum.py")),run_name="__main__")
