"""Local-only bounded pattern scan. Never emit credential or personal values."""
from pathlib import Path
import os, re, json, subprocess, hashlib
from collections import Counter
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]
SKIP={'.git','node_modules','__pycache__','.pytest_cache','site-packages','runtime_deps','portable','.venv','venv','_generated_com'}
EXT={'.py','.ps1','.sh','.bat','.js','.ts','.tsx','.jsx','.json','.yaml','.yml','.toml','.ini','.cfg','.md','.txt','.csv','.env','.ipynb','.xml'}
rules={
 'private_key_header':r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
 'github_token_format':r'\b(?:gh[pousr]_[A-Za-z0-9]{30,255}|github_pat_[A-Za-z0-9_]{40,255})\b',
 'openai_token_format':r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{40,255}\b',
 'slack_token_format':r'\bxox[baprs]-[A-Za-z0-9-]{20,255}\b',
 'aws_access_id_format':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'credentialed_http_url':r'https?://[^\s/:@"<>]{2,80}:[^\s/@"<>]{4,160}@',
}
patterns={k:re.compile(v) for k,v in rules.items()}
assign=re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)\s*["']?\s*[:=]\s*["']([^"'\r\n]{12,200})["']''')
findings=[];config=[];errors=[];count=Counter();private_markers=[]
tracked_raw=subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','ls-files','-z'],cwd=ROOT)
tracked=set(tracked_raw.decode('utf-8').split('\0'))
for folder,dirs,files in os.walk(ROOT,followlinks=False,onerror=lambda e:errors.append(dict(path=str(e.filename),error=type(e).__name__))):
 dirs[:]=[x for x in dirs if x not in SKIP and not (Path(folder)/x).is_symlink() and not (hasattr(Path(folder)/x,'is_junction') and (Path(folder)/x).is_junction())]
 if Path(folder).is_relative_to(OUT): dirs[:]=[];continue
 for name in files:
  p=Path(folder)/name;rel=p.relative_to(ROOT).as_posix()
  if p.is_symlink():count['skipped_links']+=1;continue
  try:
   size=p.stat().st_size
   if name.startswith(('.env','.mcp')) or name.lower() in {'credentials','id_rsa','id_ed25519','settings.local.json'}:
    config.append(dict(path=rel,tracked=rel in tracked,size_bytes=size))
   if p.suffix.lower() not in EXT and not name.startswith(('.env','.mcp')):count['skipped_extension']+=1;continue
   if size>2*1024*1024:count['skipped_over_2MiB']+=1;continue
   raw=p.read_bytes()
   if b'\x00' in raw[:8192]:count['skipped_binary']+=1;continue
   s=raw.decode('utf-8-sig',errors='replace');count['scanned_text_files']+=1;count['scanned_bytes']+=len(raw)
   for kind,pat in patterns.items():
    for m in pat.finditer(s):
     findings.append(dict(path=rel,line=s.count('\n',0,m.start())+1,kind=kind,tracked=rel in tracked,classification='UNVERIFIED_PATTERN_MATCH_VALUE_REDACTED'))
   for m in assign.finditer(s):
    val=m.group(1)
    if any(x in val.lower() for x in ['example','dummy','placeholder','your_','test','changeme','getenv','environ','secret_name']):continue
    if val.startswith(('$','<','{')) or any(c.isspace() for c in val):continue
    findings.append(dict(path=rel,line=s.count('\n',0,m.start())+1,kind='generic_credential_assignment',tracked=rel in tracked,classification='LOW_CONFIDENCE_MANUAL_REVIEW_VALUE_REDACTED'))
   hits=[w for w in ['微信','身份证','学号','联系电话','手机号码'] if w in s]
   if hits and rel.startswith(('01_project/','10_research/','AGENTS','CLAUDE')):
    private_markers.append(dict(path=rel,markers=hits,tracked=rel in tracked,classification='COLLABORATION_OR_PERSONAL_CONTEXT_MANUAL_REVIEW'))
  except (OSError,ValueError) as e:errors.append(dict(path=rel,error=type(e).__name__))
result=dict(schema='PUBLICATION_PRIVACY_PRESCAN_V1',status='PRELIMINARY_ONLY_NOT_PUBLICATION_CLEARANCE',counts=dict(count),findings=findings,configuration_candidates=config,personal_context_candidates=private_markers,read_errors=errors,excluded_directory_names=sorted(SKIP),per_file_size_limit_bytes=2*1024*1024,git_history_content_scanned=False,archives_binaries_pdf_office_scanned=False,findings_contain_secret_values=False,limitations='Pattern-based current worktree prescan only; no provider validation, entropy scanner, full history or binary/archive/Office metadata analysis. False positives and false negatives possible. Do not interpret no findings as safe to publish.')
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'PRIVACY_PRESCAN.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=result['status'],counts=dict(count),pattern_hits=len(findings),config_candidates=len(config),personal_context_candidates=len(private_markers),read_errors=len(errors)),ensure_ascii=False),flush=True)
