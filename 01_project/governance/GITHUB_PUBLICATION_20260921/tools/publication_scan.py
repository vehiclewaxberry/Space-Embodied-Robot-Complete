"""Read-only, redacted review of the selected compact publication package."""
from pathlib import Path
import hashlib,json,re,datetime,collections

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]
P=ROOT/'20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921'
def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    strong={
      'GITHUB_TOKEN':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{70,255})\b'),
      'AWS_ACCESS_KEY_ID':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
      'OPENAI_TOKEN_SHAPE':re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,255}\b'),
      'PRIVATE_KEY_HEADER':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
      'URL_EMBEDDED_CREDENTIAL':re.compile(r'https?://[^\s/:@<>"\']{1,100}:[^\s/@<>"\']{4,200}@'),
    }
    private={'WINDOWS_USER_PROFILE_PATH':re.compile(r'(?i)[a-z]:[\\/]Users[\\/][^\\/\x00\r\n<>"\']{1,80}'),
             'FG_ABSOLUTE_PATH':re.compile(r'(?i)(?<![A-Za-z0-9])[FG]:[\\/]'),
             'LOCALHOST_OR_PRIVATE_IP':re.compile(r'(?i)(?:https?://)?(?:localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')}
    matches=[];paths=[];files=[];html=[]
    for p in sorted(P.rglob('*')):
        if not p.is_file():continue
        rp=p.relative_to(P).as_posix();b=p.read_bytes();h=sha(b);files.append({'path':rp,'bytes':len(b),'sha256':h})
        is_native=p.suffix.lower() in {'.sldprt','.sldasm','.slddrw'}
        texts=[('utf8',b.decode('utf-8',errors='ignore'))]
        if is_native or b.startswith((b'\xff\xfe',b'\xfe\xff')):texts.extend([('utf16le',b.decode('utf-16-le',errors='ignore')),('utf16le_offset1',b[1:].decode('utf-16-le',errors='ignore'))])
        for name,rx in strong.items():
            found={m.group(0) for _,txt in texts for m in rx.finditer(txt)}
            if found:matches.append({'path':rp,'pattern':name,'count':len(found),'match_sha256':[sha(x.encode()) for x in sorted(found)],'value_disclosed':False})
        for name,rx in private.items():
            count=sum(len(rx.findall(txt)) for _,txt in texts)
            if count:paths.append({'path':rp,'category':name,'count':count,'native_binary':is_native,'values_disclosed':False})
        if p.suffix.lower()=='.html':
            text=texts[0][1];ver=re.search(r'plotly\.js v([\d.]+)',text)
            html.append({'path':rp,'plotly_version':ver.group(1) if ver else None,'copyright_marker_present':'Copyright' in text,'MIT_notice_present':'Permission is hereby granted' in text,'external_script_sources':re.findall(r'<script[^>]+src=[\"\']([^\"\']+)',text,re.I),'potential_embedded_OEM_geometry':'MAIN_PCBA' in text or 'R6H_MAIN' in text})
    model=json.loads((P/'02_electrical/MODEL_DEPENDENCIES.json').read_text('utf-8'));missing=[]
    for row in model['records']:
        if not row.get('included'):
            actual=Path(row['resolved_source']);missing.append({'reference':row['source'],'resolved_source':row['resolved_source'],'installed_exact_model_exists':actual.is_file(),'role':'3D_VIEW_AND_STEP_EXPORT_MODEL_NOT_REQUIRED_FOR_SCHEMATIC_OR_PCB_TEXT_PARSE','required_for_complete_3D_bundle':True})
    sel=json.loads((ROOT/'01_project/competition/HARDWARE_DESIGN_CURATION_20260921/SYSTEM_SELECTION.json').read_text('utf-8'))
    wurth=[{'path':x['destination'],'source':x['source'],'redistribution_status':x['redistribution_status'],'sha256':sha((P/x['destination']).read_bytes())} for x in sel['items'] if x['redistribution_status'].startswith('OEM_WURTH')]
    wurth_embedded=[]
    for p in (P/'02_electrical/kicad/wp10').glob('*.kicad_pcb'):
        txt=p.read_text('utf-8');needle='MP_Wurth_WP-THRSH_74651195R'
        n=txt.count(needle)
        if n:wurth_embedded.append({'path':p.relative_to(P).as_posix(),'occurrences_of_footprint_name':n,'interpretation':'Embedded footprint geometry is present; removing standalone footprint alone does not remove all copies.'})
    out={'schema':'COMPACT_HARDWARE_PUBLICATION_REVIEW_V1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Current compact working-tree files only; no upload, source modification, credential testing, Git history scan or native CAD application metadata rewrite.','status':'PENDING_MANUAL_ASSET_SCOPE_REVIEW','file_count':len(files),'total_bytes':sum(x['bytes'] for x in files),'files':files,'high_specificity_secret_findings':matches,'personal_or_machine_path_findings':paths,'native_metadata_scan_limit':'UTF8/UTF16 visible-pattern scan only; not every OLE/custom property was semantically parsed. User profile paths are privacy/hygiene findings, not proven credentials.','html_review':html,'missing_molex_models':missing,'specific_OEM_pending_assets':wurth,'embedded_OEM_footprint_occurrences':wurth_embedded,'system_redistribution_status_counts':dict(collections.Counter(x['redistribution_status'] for x in sel['items'])),'own_project_license_selected_by_reviewer':False,'compact_modified_by_reviewer':False}
    (OUT/'PUBLICATION_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'files':len(files),'bytes':out['total_bytes'],'secret_finding_count':len(matches),'path_pattern_files':len({x['path'] for x in paths}),'user_path_files':sum(x['category']=='WINDOWS_USER_PROFILE_PATH' for x in paths),'FG_path_files':sum(x['category']=='FG_ABSOLUTE_PATH' for x in paths),'html_review':html,'missing_molex':len(missing),'OEM_pending':wurth,'OEM_embedded':wurth_embedded},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
