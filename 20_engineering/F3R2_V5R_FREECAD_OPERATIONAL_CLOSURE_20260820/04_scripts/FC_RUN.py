r"""FC_RUN.py - the launcher every FCxx script is executed through.

script_id            : FC_RUN
schema_version       : 1.0
allowed_output_root  : 20_engineering/F3R2_V5R_FREECAD_OPERATIONAL_CLOSURE_20260820

Why this exists (two real defects it prevents):

1. freecadcmd executes a script WITHOUT setting __name__ == "__main__", so a
   standard `if __name__ == "__main__": main()` guard never fires. FC00 exited 0
   having done nothing - a silent no-op that looked like success.

2. freecadcmd swallows stdout/stderr and returns exit code 0 even when the script
   raises. A traceback would otherwise be invisible.

So this wrapper sets __name__, tees all output to a per-script log, records the
real exit code, and always leaves a run receipt on disk.

Usage:
  freecadcmd.exe FC_RUN.py FC02_IMPORT_AND_INDEX.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND_DIR = os.path.dirname(HERE)
LOG_DIR = os.path.join(ROUND_DIR, "99_logs")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: freecadcmd.exe FC_RUN.py <script.py> [args...]")
        return 64

    target_name = sys.argv[1]
    target = target_name if os.path.isabs(target_name) else os.path.join(HERE, target_name)
    if not os.path.isfile(target):
        print(f"FC_RUN: target not found: {target}")
        return 66

    os.makedirs(LOG_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = os.path.splitext(os.path.basename(target))[0]
    log_path = os.path.join(LOG_DIR, f"{base}_{stamp}.log")

    buffer = io.StringIO()
    real_stdout = sys.stdout

    class Tee:
        def write(self, text):
            buffer.write(text)
            try:
                real_stdout.write(text)
            except Exception:
                pass

        def flush(self):
            try:
                real_stdout.flush()
            except Exception:
                pass

    exit_code, error = 0, None
    sys.argv = sys.argv[1:]          # target sees its own argv
    sys.stdout = sys.stderr = Tee()
    started = time.time()
    try:
        source = open(target, encoding="utf-8").read()
        globals_dict = {"__name__": "__main__", "__file__": target}
        exec(compile(source, target, "exec"), globals_dict)   # noqa: S102
    except SystemExit as exc:
        exit_code = int(exc.code) if isinstance(exc.code, int) else 0
    except BaseException:            # MemoryError must be caught too
        exit_code = 70
        error = traceback.format_exc()
        buffer.write("\nTRACEBACK:\n" + error)
    finally:
        elapsed = round(time.time() - started, 2)
        sys.stdout = sys.stderr = real_stdout

    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(buffer.getvalue())

    receipt = {
        "script_id": "FC_RUN",
        "target": target.replace("\\", "/"),
        "exit_code": exit_code,
        "elapsed_s": elapsed,
        "log": log_path.replace("\\", "/"),
        "log_bytes": os.path.getsize(log_path),
        "error": error,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    receipt_path = os.path.join(LOG_DIR, f"{base}_{stamp}_RUN.json")
    with open(receipt_path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=1, ensure_ascii=False)

    print(f"\nFC_RUN target={base} exit={exit_code} elapsed={elapsed}s")
    print(f"FC_RUN log={log_path}")
    return exit_code


sys.exit(main())
