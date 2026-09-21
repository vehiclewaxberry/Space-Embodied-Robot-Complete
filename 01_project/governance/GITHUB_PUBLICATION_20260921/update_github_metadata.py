"""Update only the authorized repository's public description/topics.

Uses the existing Git Credential Manager login in memory; never logs credentials.
"""
from pathlib import Path
import json, os, subprocess, urllib.request, urllib.error

A=Path(__file__).resolve().parent
ROOT=A.parents[2]
P=ROOT/'20_engineering/SERVICE_STAR_PUBLICATION_20260921'
REPO='vehiclewaxberry/Space-Embodied-Robot-Complete'
env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0';env['GCM_INTERACTIVE']='never'
result=subprocess.run(['git','-c','safe.directory='+P.as_posix(),'credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,env=env,cwd=P,timeout=45)
if result.returncode: raise SystemExit('Existing GitHub credential lookup failed; no credential output disclosed')
credential=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
token=credential.get('password')
if not token: raise SystemExit('No existing credential available')
def call(method,path,payload=None):
    data=json.dumps(payload,ensure_ascii=False).encode('utf-8') if payload is not None else None
    request=urllib.request.Request('https://api.github.com/repos/'+REPO+path,data=data,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Python-urllib/3.13','Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:
        body=b''
        while len(body)<2_000_000:
            chunk=response.read1(65536)
            if not chunk: break
            body+=chunk
            try: return json.loads(body)
            except (json.JSONDecodeError,UnicodeDecodeError): pass
        return json.loads(body)
description='航天服务星具身智能机械臂机器人 | Space Service Robot with Embodied Intelligence — mechanical, electrical & harness, power & thermal, and propulsion hardware design.'
topics=['space-robotics','on-orbit-servicing','robotic-manipulator','cubesat','solidworks','kicad','hardware-design','thermal-engineering']
updated=call('GET','')
if updated.get('description')!=description: updated=call('PATCH','',{'description':description})
topic_result=call('GET','/topics')
if sorted(topic_result.get('names',[]))!=sorted(topics):topic_result=call('PUT','/topics',{'names':topics})
receipt={'repository':updated['full_name'],'visibility':updated.get('visibility'),'description':updated.get('description'),'topics':topic_result['names'],'repository_url_unchanged':True,'credentials_logged':False}
(A/'GITHUB_METADATA_UPDATED.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
