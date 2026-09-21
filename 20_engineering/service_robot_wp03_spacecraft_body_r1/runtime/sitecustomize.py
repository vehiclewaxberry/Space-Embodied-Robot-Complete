"""Process-local CAD runtime: apply bundled cadgen's invalid-font guard early.

Used only when this folder is explicitly added to the viewer PYTHONPATH.
No fonts or installed packages are modified.
"""
import cadgen
