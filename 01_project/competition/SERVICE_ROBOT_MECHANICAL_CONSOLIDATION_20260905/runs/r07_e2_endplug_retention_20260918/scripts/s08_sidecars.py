# -*- coding: utf-8 -*-
# s08: 为 run 目录内所有缺 .sha256 边车的文件补齐边车（hash + '  ' + 相对名 + '\n'，wb 二进制 LF）
import hashlib, os, io, json

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCLUDE_DIRS = ["inputs", "scripts", "exports", "evidence", "logs"]
INCLUDE_ROOT_FILES = ["PATCH_NOTES.md", "ACCEPTANCE_SUMMARY.json"]

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

targets = []
for d in INCLUDE_DIRS:
    root = os.path.join(RUN, d)
    for dirpath, _, files in os.walk(root):
        for fn in files:
            targets.append(os.path.join(dirpath, fn))
for fn in INCLUDE_ROOT_FILES:
    p = os.path.join(RUN, fn)
    if os.path.exists(p):
        targets.append(p)

created, skipped_existing, skipped_self = [], 0, 0
for p in sorted(targets):
    if p.endswith(".sha256"):
        skipped_self += 1
        continue
    sidecar = p + ".sha256"
    if os.path.exists(sidecar):
        skipped_existing += 1
        continue
    digest = sha256_of(p)
    rel = os.path.relpath(p, RUN).replace("\\", "/")
    with open(sidecar, "wb") as f:
        f.write((digest + "  " + rel + "\n").encode("utf-8"))
    created.append(rel)

log = {"run": os.path.basename(RUN), "check": "sha256_sidecar_backfill",
       "created_count": len(created), "skipped_existing": skipped_existing,
       "skipped_self": skipped_self, "created": created}
with open(os.path.join(RUN, "logs", "s08_sidecar_log.json"), "wb") as f:
    f.write((json.dumps(log, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
# 给日志自身也补边车
lp = os.path.join(RUN, "logs", "s08_sidecar_log.json")
with open(lp + ".sha256", "wb") as f:
    f.write((sha256_of(lp) + "  logs/s08_sidecar_log.json\n").encode("utf-8"))
print("created", len(created), "skipped_existing", skipped_existing, "skipped_self", skipped_self)
