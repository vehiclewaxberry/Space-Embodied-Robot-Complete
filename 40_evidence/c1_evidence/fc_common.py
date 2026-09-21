# fc_common.py — shared helpers for all migration scripts (FreeCAD console safe).
import sys, os, json, hashlib

MIG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
FA_ROOT = os.path.join(MIG_ROOT, "20_engineering", "cad", "freecad_authoritative")
VERIF_DIR = os.path.join(FA_ROOT, "08_verification")
EXPORT_DIR = os.path.join(FA_ROOT, "07_exports")
AUTH_DIR = os.path.join(MIG_ROOT, "00_authority", "input_bundle")
ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"

def script_args():
    # FreeCAD console leaves flags + repeated script path in sys.argv; filter both.
    return [a for a in sys.argv[1:] if not a.startswith("-") and not a.lower().endswith(".py")]

def ensure_dirs():
    for d in (VERIF_DIR, EXPORT_DIR):
        os.makedirs(d, exist_ok=True)

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def write_json(obj, name):
    ensure_dirs()
    path = os.path.join(VERIF_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    return path

def load_ssot_params():
    import csv
    path = os.path.join(FA_ROOT, "01_skeleton", "B51R1_FREECAD_SSOT_PARAMETERS.csv")
    params = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            params[row["name"]] = row
    return params
