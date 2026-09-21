"""Validate derived report links, counts and seals, without executing project code."""
from pathlib import Path
import re, json, csv, hashlib, datetime
OUT=Path(__file__).resolve().parent
def reject_constant(s):raise ValueError(s)
issues=[];links=[];parsed=[]
for p in OUT.glob('*.json'):
    try:json.loads(p.read_text(encoding='utf-8-sig'),parse_constant=reject_constant);parsed.append(p.name)
    except Exception as e:issues.append(dict(file=p.name,error=str(e)))
for p in OUT.glob('*.md'):
    s=p.read_text(encoding='utf-8-sig')
    for value in re.findall(r'\]\(([^\n]+?)\)',s):
        value=value.strip().strip('<>')
        if value.startswith(('https://','http://','#')):continue
        m=re.match(r'^(.*?):(\d+)$',value)
        line=int(m[2]) if m else None;target=m[1] if m else value
        q=Path(target)
        if not q.is_absolute():q=OUT/q
        row=dict(report=p.name,target=str(q),line=line,exists=q.exists())
        if not q.exists():issues.append(row)
        elif line:
            row['line_valid']=line<=len(q.read_text(encoding='utf-8-sig').splitlines())
            if not row['line_valid']:issues.append(row)
        links.append(row)
matrix=list(csv.DictReader((OUT/'02_ASSET_INTEGRATION_VERIFICATION.csv').open(encoding='utf-8-sig')))
eight=[r for r in matrix if r['group']=='A3_EIGHT']
if len(eight)!=8:issues.append(dict(error='A3 missing slots not eight',count=len(eight)))
source_rows=list(csv.DictReader((OUT/'09_SOURCE_SHA256.csv').open(encoding='utf-8-sig')))
protected=json.loads((OUT/'root_protected_after_check.json').read_text(encoding='utf-8'))
if protected['changed']:issues.append(dict(error='protected changed',changes=protected['changed']))
receipt=dict(
    task='PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT',
    timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    artifact_class='DERIVED_READ_ONLY_AUDIT_NOT_PROJECT_GATE',
    audit_status='COMPLETED_WITH_DECLARED_LIMITS' if not issues else 'REPORT_VALIDATION_ISSUES',
    project_mechanical_status='HOLD_UNCHANGED',mode_b_started=False,route_change_approved_by_this_audit=False,
    current_full_assembly_validated=False,source_files_modified_by_this_audit=False,
    cad_gui_started=False,production_scripts_executed=False,optimization_executed=False,
    fea_executed=False,dynamics_executed=False,production_collision_queries=0,
    validation=dict(matrix_rows=len(matrix),a3_eight_slots=len(eight),source_paths=len(source_rows),source_missing=sum(r.get('exists')!='True' for r in source_rows),selected_protected_count=protected['checked'],selected_protected_changes=len(protected['changed']),json_files_strictly_parsed=len(parsed),markdown_local_links_checked=len(links),issues=issues),
    independent_a3_readback=json.loads((OUT/'a3_numeric_recheck.json').read_text(encoding='utf-8')),
    native_asset_readback=json.loads((OUT/'assets_audit_counts.json').read_text(encoding='utf-8')),
    limits=['Not an all-disk forensic/full-text audit','10 Root A test-cache directories access denied','No native CAD cold-open or current mate/rebuild verification','Static reference existence is not native reference resolution','Selected 134-file pre/post hash scope; additional source SHA snapshots are point-in-time','Source historical Gate execution not rerun; A3 only saved-pose numeric readback','No global infeasibility proof; no full system collision proof'],
    completed_deliverables=['00_航天服务星机械设计现状总览.md','01_WORKSPACE_AND_SCOPE.md','02_ASSET_INTEGRATION_VERIFICATION.csv','03_NATIVE_ASSEMBLY_AUDIT.md','04_A3_METHOD_AUDIT.md','05_AUTHORITY_AND_EMBODIED_HANDOFF.md','06_MASS_AND_COLLISION_CAPABILITY.md','07_REUSE_AND_REVALIDATION.md','09_SOURCE_SHA256.csv'],
    stopping_point='Audit complete; no automatic route switch or engineering execution')
(OUT/'08_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
(OUT/'root_report_link_check.json').write_text(json.dumps(links,ensure_ascii=False,indent=2),encoding='utf-8')
seals=[]
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name!='10_AUDIT_OUTPUT_SHA256.csv':
        seals.append(dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest().upper()))
with (OUT/'10_AUDIT_OUTPUT_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['file','bytes','sha256']);w.writeheader();w.writerows(seals)
print(json.dumps(receipt['validation'],ensure_ascii=False))
