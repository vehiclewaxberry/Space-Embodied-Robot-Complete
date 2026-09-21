"""Per-launch WP06 Viewer bootstrap: install cadgen's existing font guard first.
Only used through this process's VIEWER_CAD_PYTHONPATH. No global Python,
installed viewer, fonts, or system settings are modified.
"""
import cadgen
