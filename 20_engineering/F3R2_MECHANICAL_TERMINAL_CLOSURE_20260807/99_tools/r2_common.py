# -*- coding: utf-8 -*-
"""F3R2 terminal-closure common layer.

All NEW scripts of the F3R2 campaign live here and write ONLY into the F3R2
candidate tree.  The proven F3R1 primitives (b3_lib COM core, session
discipline, VARIANT transforms, protected-hash digests) are imported read-only
from F3R1/99_tools; nothing in F3R1 is written by this module.

Hard lessons carried in (do not re-learn):
  D-F3R1-07  every SolidWorks run starts from a killed process + 24 s settle,
             otherwise stale session state fakes err=5 and phantom interference.
  D-F3R2-01  the machine runs at ~1.5 GB free.  SolidWorks answers a fatal
             low-memory dialog and then dies mid-COM-call with RPC failure
             (-2147023170).  Opens are therefore SILENT, work is chunked per
             session, results are journalled incrementally, and every SW step
             is retried in a fresh process.
  D-F3R2-02  a crashed SolidWorks leaves one ~$<name> lock file per loaded
             document.  Stale locks raise modal dialogs on the next open, so
             they are swept before every session.
"""
import ctypes
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
ENG = REPO / "20_engineering"
F3R1 = ENG / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806"
F3R2 = ENG / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"

sys.path.insert(0, str(F3R1 / "99_tools"))
sys.path.insert(0, str(F3R2 / "99_tools"))

import b3_lib.sw_core as swc  # noqa: E402
import sw_session as ss  # noqa: E402
import r2_env as R  # noqa: E402
from f3r1_env import PROTECTED, sha256_file  # noqa: E402

gm = swc.get_com_member

# ---- F3R2-local authority + logs (never write into F3R1) ----
AUTH2 = F3R2 / "00_authority"
LOGS2 = F3R2 / "99_tools" / "logs"
for _d in (AUTH2, LOGS2):
    _d.mkdir(parents=True, exist_ok=True)

# re-export the F3R2 tree
NC2, CFG2, CLR2 = R.NC2, R.CFG2, R.CLR2
SUP2, HDRM2, CAM2 = R.SUP2, R.HDRM2, R.CAM2
THREAD2, SHOT2, REVIEW2 = R.THREAD2, R.SHOT2, R.REVIEW2
GATE2, PKG2, CC2 = R.GATE2, R.PKG2, R.CC2
BASELINE, CONFIGS = R.BASELINE, R.CONFIGS


class Log:
    """jsonl event log under F3R2/99_tools/logs."""

    def __init__(self, name):
        self.path = LOGS2 / (name + ".jsonl")

    def ev(self, event, **kw):
        rec = {"utc": datetime.now(timezone.utc).isoformat(), "event": event}
        rec.update(kw)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        print("[%s] %s %s" % (time.strftime("%H:%M:%S"), event,
                              json.dumps(kw, ensure_ascii=False,
                                         default=str)[:200]), flush=True)


def check_protected2(tag):
    """Protected-asset digest check; report written INSIDE F3R2."""
    rep = {"tag": tag, "utc": datetime.now(timezone.utc).isoformat(),
           "assets": {}}
    bad = []
    for name, spec in PROTECTED.items():
        p = spec["path"]
        if not p.is_file():
            rep["assets"][name] = {"status": "MISSING", "path": str(p)}
            bad.append(name)
            continue
        actual = sha256_file(p)
        ok = actual == spec["sha256"].upper()
        rep["assets"][name] = {"status": "MATCH" if ok else "DRIFT",
                               "declared": spec["sha256"].upper(),
                               "actual": actual, "path": str(p)}
        if not ok:
            bad.append(name)
    rep["verdict"] = ("ALL_PROTECTED_UNCHANGED" if not bad
                      else "PROTECTED_DRIFT_" + ",".join(bad))
    (AUTH2 / ("F3R2_PROTECTED_CHECK_%s.json" % tag)).write_text(
        json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    if bad:
        raise RuntimeError("PROTECTED ASSET DRIFT: %s" % bad)
    return rep


# ---------------- memory + lock hygiene (D-F3R2-01 / D-F3R2-02) ----------------
def avail_mb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    st = MS()
    st.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return int(st.ullAvailPhys / (1024 * 1024))


def sweep_locks(*roots):
    """Delete stale ~$ SolidWorks lock files (only valid while SW is dead)."""
    n = 0
    for root in roots or (F3R2,):
        for p in Path(root).rglob("~$*"):
            try:
                p.unlink()
                n += 1
            except Exception:
                pass
    return n


def fresh(log, tag, wait=24):
    """Kill SolidWorks, sweep locks, restart, report memory."""
    before = R.sw_count()
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process SLDWORKS -ErrorAction SilentlyContinue |"
                    " Stop-Process -Force"],
                   capture_output=True, text=True, timeout=120)
    time.sleep(3)
    after = R.sw_count()
    if after not in (0, -1):
        raise RuntimeError("SolidWorks still alive: %s" % after)
    swept = sweep_locks(F3R2)
    log.ev("SW_CLEARED", before=before, after=after, locks_swept=swept,
           avail_mb=avail_mb())
    time.sleep(wait)
    app = ss.connect(log)
    rec = {"tag": tag, "sw_before": before, "locks_swept": swept,
           "avail_mb_start": avail_mb(),
           "revision": str(gm(app, "RevisionNumber"))}
    log.ev("SW_STARTED", **rec)
    return app, rec


def kill_sw(log):
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process SLDWORKS -ErrorAction SilentlyContinue |"
                    " Stop-Process -Force"],
                   capture_output=True, text=True, timeout=120)
    time.sleep(3)
    swept = sweep_locks(F3R2)
    log.ev("SW_KILLED", locks_swept=swept, avail_mb=avail_mb())


# ---------------- silent open (D-F3R2-01) ----------------
SW_SILENT = 1
SW_READONLY = 2


def open_silent(app, blog, path, read_only=False):
    """OpenDoc6 with the SILENT bit so a low-memory / read-only modal cannot
    block COM.  Fail-closed: None return raises."""
    opts = SW_SILENT | (SW_READONLY if read_only else 0)
    ret = app.OpenDoc6(str(path), 2, opts, "", 0, 0)
    model = ret[0] if isinstance(ret, tuple) else ret
    if model is None:
        raise RuntimeError("OpenDoc6 returned None: %s" % path)
    blog.event("DOC_OPEN_SILENT", path=str(path), read_only=read_only)
    return swc.cast(model, "IModelDoc2")


class ProgressWatchdog:
    """Kill SolidWorks if no progress is reported for `limit` seconds.

    SolidWorks has TWO failure modes on this machine: it dies (RPC failure) and
    it HANGS (Responding=False, CPU flat, COM call never returns).  A hang would
    otherwise block the campaign forever, so an unresponsive session is killed;
    the pending COM call then raises and with_retry starts a clean attempt.
    """

    def __init__(self, log, limit=420):
        import threading
        self.log, self.limit = log, limit
        self.last = time.time()
        self._stop = threading.Event()
        self.fired = False
        self.t = threading.Thread(target=self._run, daemon=True)

    def beat(self, what=""):
        self.last = time.time()

    def _run(self):
        while not self._stop.wait(15):
            idle = time.time() - self.last
            if idle > self.limit:
                self.fired = True
                self.log.ev("PROGRESS_WATCHDOG_KILLING_SW",
                            idle_s=round(idle, 1), limit_s=self.limit,
                            avail_mb=avail_mb())
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-Process SLDWORKS -ErrorAction SilentlyContinue |"
                     " Stop-Process -Force"],
                    capture_output=True, text=True, timeout=120)
                return

    def start(self):
        self.t.start()
        return self

    def stop(self):
        self._stop.set()


def with_retry(log, tag, fn, attempts=3, settle=24, idle_limit=420):
    """Run fn(app, blog, attempt, beat) in a fresh SolidWorks session; retry the
    whole session on RPC death or on a hang detected by the progress watchdog."""
    last = None
    for i in range(1, attempts + 1):
        app = None
        wd = pw = None
        try:
            app, sess = fresh(log, "%s_a%d" % (tag, i), wait=settle)
            blog = swc.BuildLog(tag)
            wd = ss.MemoryDialogWatchdog(log)
            wd.start()
            pw = ProgressWatchdog(log, limit=idle_limit).start()
            try:
                out = fn(app, blog, i, pw.beat)
            except TypeError as te:
                if "positional argument" not in str(te):
                    raise
                out = fn(app, blog, i)
            if isinstance(out, dict):
                out.setdefault("session", sess)
            return out
        except Exception as exc:
            last = exc
            log.ev("SESSION_ATTEMPT_FAILED", tag=tag, attempt=i,
                   error=str(exc)[:200], avail_mb=avail_mb(),
                   hang_killed=bool(pw and pw.fired))
            if i == attempts:
                raise
            time.sleep(10)
        finally:
            if pw is not None:
                pw.stop()
            if wd is not None:
                wd.stop()
            try:
                kill_sw(log)
            except Exception:
                pass
    raise last


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                                     default=str), encoding="utf-8")


def write_csv(path, rows, fields=None):
    import csv
    if not rows:
        return 0
    fields = fields or list(rows[0].keys())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)
