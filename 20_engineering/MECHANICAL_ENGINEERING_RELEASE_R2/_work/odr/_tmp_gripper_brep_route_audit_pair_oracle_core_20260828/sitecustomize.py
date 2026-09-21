"""Temporary host compatibility shim for build123d's Windows font scan."""

try:
    from OCP.Font import Font_FontMgr
    from OCP.TCollection import TCollection_AsciiString

    manager = Font_FontMgr.GetInstance_s()
    manager.AddFontAlias(
        TCollection_AsciiString("singleline"),
        TCollection_AsciiString("Arial"),
    )
except Exception:
    # CAD commands that do not import OCP should remain runnable.
    pass
