"""Verify known credential-pattern exposure locally; report no secret values."""
from pathlib import Path
import subprocess,re,json,hashlib
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]
path='20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational/jobs/fea1_capture_150kg_qs_coarse.env'
pat=re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{40,255}\b')
def git(*args):return subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}',*args],cwd=ROOT)
def inspect(raw):
 s=raw.decode('utf-8',errors='replace');rows=[];matches=[]
 for i,line in enumerate(s.splitlines(),1):
  for m in pat.finditer(line):
   labels=re.findall(r'''["']?([A-Za-z_][A-Za-z0-9_]{1,60})["']?\s*[:=]''',line)
   credential_labels=[x for x in labels if any(t in x.upper() for t in ['API_KEY','AUTH_TOKEN','SECRET','PASSWORD'])]
   matches.append(m.group()); rows.append(dict(line=i,token_length=len(m.group()),project_key_prefix=m.group().startswith('sk-proj-'),credential_assignment_names=credential_labels,provider_identity_confirmed=False,contains_OPENAI_API_KEY_label='OPENAI_API_KEY' in line,contains_environment_label=bool(re.search(r'environ|environment|ENV',line))))
 return dict(pattern_count=len(rows),unique_pattern_count=len(set(matches)),redacted_occurrences=rows)
current=(ROOT/path).read_bytes();head=git('show',f'HEAD:{path}')
commits=git('log','--all','--format=%H','--',path).decode('ascii').splitlines()
history=[]
for c in commits:
 try:r=inspect(git('show',f'{c}:{path}'));history.append(dict(commit=c,**r))
 except subprocess.CalledProcessError:history.append(dict(commit=c,path_present=False))
result=dict(status='BLOCK_PUBLICATION_PENDING_CREDENTIAL_REVIEW',path=path,current_file_sha256=hashlib.sha256(current).hexdigest(),current=inspect(current),HEAD=inspect(head),current_matches_HEAD=current==head,reachable_path_history_versions=history,provider_validity_tested=False,token_values_disclosed=False,credentials_rotated=False,history_modified=False,interpretation='Strong credential-format match in tracked environment snapshot; liveness/ownership are not tested. If genuine, revoke/rotate before publication and remove from any selected release history. Current-only deletion or ignore does not purge history.')
(OUT/'SECRET_FINDINGS_REDACTED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=result['status'],current=result['current'],HEAD=result['HEAD'],history_versions=len(history),matching_history_versions=sum(x.get('pattern_count',0)>0 for x in history)),ensure_ascii=False))
