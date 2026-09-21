"""Read-only hardware-copy checks; writes only audit and compact delivery records."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv, hashlib, json, re

AUDIT = Path(__file__).resolve().parents[1]
ROOT = AUDIT.parents[2]
PACK = ROOT / '20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921'
RELEASE = PACK / '00_release'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

errors, protected = [], []
entry_links = []
entrypoints = ['README.md', '01_mechanical/MECHANICAL_OPEN_GUIDE.md',
               '02_electrical/README.md', '03_power_thermal/README.md',
               '04_propulsion/README.md', '00_release/OPEN_ITEMS.md',
               '00_release/PUBLICATION_NOTES.md', '00_release/THIRD_PARTY_NOTICES.md']
for rel in entrypoints:
    path = PACK / rel
    if not path.is_file():
        errors.append({'kind':'MISSING_ENTRYPOINT','path':rel})
        continue
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        target = target.strip('<>')
        if target.startswith(('https://','http://','#','mailto:')):
            continue
        resolved = path.parent / target.split('#')[0]
        valid = resolved.exists()
        entry_links.append({'document':rel,'target':target,'exists':valid})
        if not valid:
            errors.append({'kind':'BROKEN_ENTRYPOINT_LINK','document':rel,'target':target})
for name, field in [
    ('20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/SOURCE_DEPENDENCIES_SHA256.csv', 'path'),
    ('20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/PACKAGE_SHA256.csv', 'workspace_relative_path'),
    ('20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920/PACKAGE_SHA256.csv', 'workspace_relative_path')]:
    with (ROOT / name).open(encoding='utf-8-sig', newline='') as handle:
        records = list(csv.DictReader(handle))
    for record in records:
        key = field if field in record else 'path'
        rel = record[key]
        path = ROOT / rel
        if not path.is_file() and not rel.startswith('20_engineering/'):
            path = (ROOT / name).parent / rel
        actual = sha(path) if path.is_file() else None
        match = actual == record['sha256'].lower()
        protected.append({'manifest': name, 'path': rel, 'matches': match})
        if not match:
            errors.append({'kind':'PROTECTED_SOURCE_MISMATCH','path':rel})

# This audit does not copy or print the two previously identified credential values.
credential_source = ROOT / '20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational/jobs/fea1_capture_150kg_qs_coarse.env'
known_values = re.findall(rb'sk-[A-Za-z0-9_-]{32,}', credential_source.read_bytes())
secret_pattern = re.compile(rb'(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{40,}')
secret_findings, forbidden, large, absolute_text = [], [], [], []
excluded = {'00_release/PACKAGE_SHA256.csv', '00_release/PACKAGE_STATUS.json'}
files = [p for p in sorted(PACK.rglob('*')) if p.is_file() and p.relative_to(PACK).as_posix() not in excluded]
module_counts = Counter()
module_bytes = Counter()
for path in files:
    rel = path.relative_to(PACK).as_posix()
    payload = path.read_bytes()
    module = rel.split('/')[0] if '/' in rel else '(root)'
    module_counts[module] += 1
    module_bytes[module] += len(payload)
    if path.is_symlink():
        errors.append({'kind':'SYMLINK_IN_DELIVERY','path':rel})
    if path.suffix.lower() in {'.exe','.dll','.pyc','.env','.sqlite','.db'} or '.git' in path.parts:
        forbidden.append(rel)
    if len(payload) > 100 * 1024**2:
        large.append({'path':rel,'bytes':len(payload),'requires_lfs_or_release':True})
    hits = len(secret_pattern.findall(payload))
    known = sum(value in payload or value.decode('ascii').encode('utf-16le') in payload for value in known_values)
    if hits or known:
        secret_findings.append({'path':rel,'format_matches':hits,'known_value_matches':known})
    if path.suffix.lower() in {'.json','.csv','.md','.py','.ps1','.kicad_sch','.kicad_pcb','.kicad_pro','.kicad_sym','.kicad_mod'}:
        if re.search(rb'[FG]:[\\/]', payload):
            absolute_text.append(rel)
if forbidden:
    errors.append({'kind':'FORBIDDEN_DELIVERY_FILE_TYPES','paths':forbidden})
if secret_findings:
    errors.append({'kind':'SECRET_FORMAT_OR_KNOWN_VALUE_MATCH','findings':secret_findings})

for part in ['01_mechanical','02_electrical','03_power_thermal','04_propulsion']:
    if not any(p.is_file() for p in (PACK / part).rglob('*')):
        errors.append({'kind':'MISSING_HARDWARE_MODULE','path':part})

mechanical = json.loads((PACK / '01_mechanical/MECHANICAL_DELIVERY.json').read_text(encoding='utf-8'))
electrical = json.loads((PACK / '02_electrical/verification/SYSTEM_COPY_VERIFICATION.json').read_text(encoding='utf-8'))
status = {
    'schema':'HARDWARE_COMPACT_DELIVERY_INTEGRITY_V1',
    'generated_utc':datetime.now(timezone.utc).isoformat(),
    'scope':'Mechanical, electrical/harness, power/thermal and propulsion design files only',
    'integrity_checks_pass': not errors,
    'source_design_records_checked':len(protected),
    'source_design_records_unchanged':all(r['matches'] for r in protected),
    'entrypoint_local_links_checked':len(entry_links),
    'native_portable_package':mechanical['native_portable_package'],
    'native_files':mechanical['native_files'],
    'current_assembly_leaf_instances':mechanical['leaf_instances'],
    'native_copy_status':mechanical['status'],
    'electrical_copy_status':electrical['status'],
    'selected_files_before_status_manifest':len(files),
    'selected_bytes_before_status_manifest':sum(module_bytes.values()),
    'modules':{key:{'files':module_counts[key],'bytes':module_bytes[key]} for key in module_counts},
    'credential_format_scan':{'files':len(files),'findings':secret_findings,'full_history_scanned':False,'native_metadata_privacy_certified':False},
    'over_100_MiB_files':large,
    'files_with_FG_absolute_text_references':absolute_text,
    'absolute_path_scope':'Source provenance and historical receipts may retain paths; current CAD/EDA runtime closure has separate module receipts',
    'publication_clearance':False,
    'publication_open_items':['Owner license selection','Asset-specific third-party/OEM redistribution rights and metadata review'],
    'whole_spacecraft_design_complete':False,
    'ready_to_power':False,
    'flight_ready':False,
    'github_uploaded':False,
    'original_git_history_included':False,
    'research_control_content_packaged':False,
    'engineering_validity_upgraded_by_curation':False,
    'errors':errors,
    'manifest_policy':'Manifest covers delivered files and PACKAGE_STATUS.json; manifest itself excluded'
}
RELEASE.mkdir(exist_ok=True)
(AUDIT / 'PROTECTED_SOURCE_RECHECK.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(AUDIT / 'ENTRYPOINT_LINK_CHECK.json').write_text(json.dumps(entry_links,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(RELEASE / 'PACKAGE_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files.append(RELEASE / 'PACKAGE_STATUS.json')
with (RELEASE / 'PACKAGE_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=['path','bytes','sha256'])
    writer.writeheader()
    for path in sorted(files):
        writer.writerow({'path':path.relative_to(PACK).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
print(json.dumps({k:status[k] for k in ['integrity_checks_pass','source_design_records_checked','source_design_records_unchanged','selected_files_before_status_manifest','selected_bytes_before_status_manifest','modules','errors']},ensure_ascii=False))
raise SystemExit(0 if not errors else 2)
