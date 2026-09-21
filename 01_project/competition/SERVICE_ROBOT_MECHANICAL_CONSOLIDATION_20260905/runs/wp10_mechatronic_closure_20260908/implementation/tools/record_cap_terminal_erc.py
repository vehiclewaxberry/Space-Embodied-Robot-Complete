"""Bind the actual MCP result retained from this V17 run to current sources."""
from pathlib import Path
import json,hashlib,datetime
A=Path(__file__).resolve().parents[1]
p=A/'results/ERC_MCP_CROSSCHECK.json'
v=json.loads(p.read_text(encoding='utf-8-sig'))
r=json.loads((A/'results/CAP_TERMINAL_MCP_ERC_RAW_V17.json').read_text())
assert 'Errors: 0  Warnings: 0' in r['content'][0]['text']
v.update(schema='WP10_MCP_ERC_CROSSCHECK_V17',result=r,recorded_local=datetime.datetime.now().astimezone().isoformat(),scope='Actual MCP result retained from this V17 run; record time is packaging time, not tool execution timestamp. No hardware qualification.')
v['inputs']={q:hashlib.sha256((A/q).read_bytes()).hexdigest() for q in v['inputs']}
v['inputs']['results/CAP_TERMINAL_MCP_ERC_RAW_V17.json']=hashlib.sha256((A/'results/CAP_TERMINAL_MCP_ERC_RAW_V17.json').read_bytes()).hexdigest()
p.write_text(json.dumps(v,indent=2),encoding='utf-8')
print('Recorded actual MCP V17 ERC result and current input hashes')
