"""Preserve the complete coupled input lock before the four physical terminations."""
from pathlib import Path
import json, hashlib, shutil, sys
from erc_source_contract import source_inventory, parse, enc, children, val
A=Path(__file__).resolve().parents[1]
H=A/'history/20260910_V29_before_terminals'
assert not H.exists(), 'Do not overwrite pre-change history'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads((A/'coupled_closure/CANDIDATE.json').read_text())
paths={Path(p) for p,h in c['source_lock'].items()}
assert all(sha(Path(p))==h for p,h in c['source_lock'].items())
_,pages,_=source_inventory(A/'ecad/wp10_system.kicad_sch');paths.update(pages)
paths.update((A/'ecad').glob('*.kicad_pro'))
paths.update((A/'ecad').glob('*.pretty/*.kicad_mod'))
paths.update(A/'ecad'/n for n in ['fp-lib-table','sym-lib-table'] if (A/'ecad'/n).exists())
paths.update([A/'coupled_closure/CANDIDATE.json',A/'coupled_closure/SPREADER_INSTANCE_PLAN_V28.json'])
rows=[]
root=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists())
for p in sorted(paths):
 rel=p.relative_to(A) if p.is_relative_to(A) else Path('_external')/p.relative_to(root)
 dst=H/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
 rows.append(dict(path=rel.as_posix(),original_path=str(p),sha256=sha(p),bytes=p.stat().st_size))
(H/'SOURCE_SNAPSHOT.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
src=A/'sources/terminal_v29/MP_Wurth_WP-THRSH_74651195R.kicad_mod'
fp=parse(src.read_text());model=children(fp,'model')[0]
model[1]=json.dumps('${KIPRJMOD}/../sources/terminal_v29/MP_Wurth_WP-THRSH_74651195.step')
children(children(model,'offset')[0],'xyz')[0][3]='0.5'
lib=A/'ecad/WP10_TERMINALS.pretty';lib.mkdir(exist_ok=True)
(lib/src.name).write_text(enc(fp)+'\n',encoding='utf-8')
tbl=A/'ecad/fp-lib-table';t=parse(tbl.read_text());assert not any(val(children(x,'name')[0][1])=='WP10_TERMINALS' for x in children(t,'lib'))
t.append(parse('(lib (name "WP10_TERMINALS") (type "KiCad") (uri "${KIPRJMOD}/WP10_TERMINALS.pretty") (options "") (descr "OEM Wurth rev26b footprint, only model path made project relative"))'))
tbl.write_text(enc(t)+'\n',encoding='utf-8')
print(json.dumps(dict(snapshot_files=len(rows),snapshot_bytes=sum(r['bytes'] for r in rows),footprint=src.name)))
