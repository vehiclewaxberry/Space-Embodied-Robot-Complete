"""Stable same-candidate publication entry; previous source retained in history."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('publish_brake_candidate.py')),run_name='__main__')
