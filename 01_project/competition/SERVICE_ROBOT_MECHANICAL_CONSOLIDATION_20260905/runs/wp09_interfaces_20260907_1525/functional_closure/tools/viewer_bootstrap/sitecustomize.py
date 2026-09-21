"""Task-local CAD font initialization before the Viewer import probe.
Uses installed cadgen's font compatibility guard; does not alter system fonts.
"""
import sys
sys.dont_write_bytecode=True
import cadgen
