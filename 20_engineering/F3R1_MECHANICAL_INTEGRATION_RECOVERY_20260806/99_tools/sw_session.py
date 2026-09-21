# -*- coding: utf-8 -*-
"""F3R1 SolidWorks session layer on top of b3_lib.

- connect(): GetActiveObject first (reuse the session started by the smoke test),
  Dispatch as fallback. Never more than one SW instance.
- MemoryDialogWatchdog: the machine runs at ~2GB free and SolidWorks blocks COM
  with a modal "内存不足/memory" dialog (B3 campaign precedent). The watchdog
  dismisses ONLY dialogs whose text matches memory keywords; every other dialog
  is logged and left alone so the run fails closed on timeout instead of
  clicking through an unknown prompt (e.g. a save prompt).
- deps/inventory/repair helpers shared by the P1..P9 scripts.
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time
from pathlib import Path

import pythoncom
import win32com.client

import b3_lib.sw_core as swc
from f3r1_env import F3R1, JLog

user32 = ctypes.windll.user32

MEM_KEYWORDS = ("内存", "memory", "Memory")
SAFE_BUTTONS = ("是(Y)", "是", "Yes", "确定", "OK", "继续", "Continue")


def _window_text(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _children(hwnd):
    out = []
    proc_t = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(h, _):
        out.append(h)
        return True

    user32.EnumChildWindows(hwnd, proc_t(cb), 0)
    return out


class MemoryDialogWatchdog(threading.Thread):
    """Poll for modal #32770 dialogs; dismiss only memory warnings."""

    def __init__(self, log: JLog, interval=2.0):
        super().__init__(daemon=True)
        self.log = log
        self.interval = interval
        self.stop_flag = threading.Event()
        self.dismissed = 0
        self.seen_other = []

    def run(self):
        proc_t = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        while not self.stop_flag.is_set():
            tops = []

            def cb(h, _):
                if _class_name(h) == "#32770" and user32.IsWindowVisible(h):
                    tops.append(h)
                return True

            user32.EnumWindows(proc_t(cb), 0)
            for h in tops:
                title = _window_text(h)
                kids = _children(h)
                texts = [_window_text(k) for k in kids]
                blob = title + " | " + " | ".join(t for t in texts if t)
                if any(k in blob for k in MEM_KEYWORDS):
                    for k in kids:
                        # SW renders accelerators with '&' ("是(&Y)"); strip
                        # before matching so the memory-continue button is found.
                        btxt = _window_text(k).replace("&", "")
                        if _class_name(k) == "Button" and btxt in SAFE_BUTTONS:
                            user32.SendMessageW(k, 0x00F5, 0, 0)  # BM_CLICK
                            self.dismissed += 1
                            self.log.ev("WATCHDOG_DISMISSED_MEMORY_DIALOG",
                                        title=title, button=btxt)
                            break
                elif "SOLIDWORKS" in title or "SolidWorks" in blob:
                    sig = blob[:200]
                    if sig not in self.seen_other:
                        self.seen_other.append(sig)
                        self.log.ev("WATCHDOG_SAW_DIALOG_NOT_TOUCHED", text=sig)
            time.sleep(self.interval)

    def stop(self):
        self.stop_flag.set()


def connect(log: JLog, visible=False):
    """Early-bound ISldWorks via b3_lib (headless by default: fewer low-memory
    modals on this 2GB-free machine; pass visible=True only for view exports)."""
    pythoncom.CoInitialize()
    blog = swc.BuildLog("sw_session_connect")
    app = swc.connect(blog, visible=visible)
    log.ev("SW_CONNECTED", visible=visible,
           revision=str(swc.get_com_member(app, "RevisionNumber")))
    return app


def doc_dependencies(app, path):
    """(name, path) pairs from GetDocumentDependencies2 without opening."""
    raw = app.GetDocumentDependencies2(str(path), True, True, False)
    if raw is None:
        return []
    flat = list(raw)
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def classify_deps(pairs, allowed_root):
    root = str(allowed_root).lower().replace("/", "\\")
    inside, leaks = [], []
    for name, p in pairs:
        (inside if str(p).lower().replace("/", "\\").startswith(root) else leaks
         ).append({"name": name, "path": str(p)})
    return inside, leaks


def open_doc(app, log, path, doc_type=None):
    """Open SLDASM/SLDPRT via b3_lib open_document (fail-closed)."""
    blog = swc.BuildLog("sw_session_open")
    return swc.open_document(app, blog, str(path))


def components_of(model, top_only=False):
    """List components with resolved path, config, transform, suppression."""
    conf = model.ConfigurationManager.ActiveConfiguration
    root = conf.GetRootComponent3(True)
    comps = root.GetChildren if callable(root.GetChildren) else root.GetChildren
    if callable(comps):
        comps = comps()
    out = []

    gm = swc.get_com_member

    def walk(clist, depth):
        for c in clist or []:
            c2 = swc.cast(c, "IComponent2")
            entry = {
                "name": str(gm(c2, "Name2")),
                "path": str(gm(c2, "GetPathName")),
                "config": str(gm(c2, "ReferencedConfiguration")),
                "suppressed": bool(gm(c2, "IsSuppressed")),
                "depth": depth,
            }
            try:
                xf = gm(c2, "Transform2")
                entry["transform16"] = list(gm(xf, "ArrayData")) if xf is not None else None
            except Exception:
                entry["transform16"] = None
            out.append(entry)
            if not top_only:
                kids = gm(c2, "GetChildren")
                if kids:
                    walk(kids, depth + 1)

    walk(comps, 1)
    return out


def mate_status(model):
    """Return (total, errors) over top-level mates of an assembly."""
    gm = swc.get_com_member
    feat = gm(model, "FirstFeature")
    total = errors = 0
    while feat is not None:
        f = swc.cast(feat, "IFeature")
        if str(gm(f, "GetTypeName2")) == "MateGroup":
            sub = gm(f, "GetFirstSubFeature")
            while sub is not None:
                s = swc.cast(sub, "IFeature")
                total += 1
                try:
                    mate = swc.cast(gm(s, "GetSpecificFeature2"), "IMate2")
                    if int(gm(mate, "MateError")) != 0:
                        errors += 1
                except Exception:
                    pass
                sub = gm(s, "GetNextSubFeature")
        feat = gm(f, "GetNextFeature")
    return total, errors
