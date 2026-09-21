"""Viewer-only import compatibility; same CAD skill font filter as generation.
No system fonts or installed packages are edited. Geometry uses no text/fonts.
"""
from cadgen._internal.font_scan import install_font_guard
install_font_guard()
