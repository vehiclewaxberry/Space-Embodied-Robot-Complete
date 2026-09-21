"""Create a source-preserving V34 ECAD successor, never rebuild the parent."""
from pathlib import Path
import hashlib,json,shutil,urllib.request
from erc_source_contract import source_inventory
A=Path(__file__).resolve().parents[1]
D=A/'ecad/revisions/v34'; R=A/'results/aux_v34'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    assert not D.exists(),'Resume V34; never overwrite existing design'
    parent=A/'ecad/revisions/v32'
    _,pages,_=source_inventory(parent/'wp10_system.kicad_sch')
    files=set(pages)|set(parent.glob('*.kicad_sym'))|set(parent.glob('*.pretty/*.kicad_mod'))
    files|={parent/n for n in ['sym-lib-table','fp-lib-table','wp10_system.kicad_pro','wp10_main_input.kicad_pcb','wp10_main_input.kicad_pro']}
    R.mkdir(parents=True,exist_ok=True); D.mkdir(parents=True)
    lock={str(p):sha(p) for p in sorted(files|{parent/'wp10_system.xml',A/'SYSTEM_CLOSURE_MATRIX.csv'})}
    dump(R/'PARENT_SOURCE_LOCK.json',lock)
    for p in files:
        q=D/p.relative_to(parent);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    src=R/'sources';src.mkdir()
    sources={
      'tps2660_rev_g.pdf':'https://www.ti.com/lit/ds/symlink/tps2660.pdf',
      'kemet_c0g_smd.pdf':'https://content.kemet.com/datasheets/KEM_C1003_C0G_SMD.pdf'}
    rows=[]
    for name,url in sources.items():
        b=urllib.request.urlopen(url,timeout=45).read();assert b.startswith(b'%PDF-')
        p=src/name;p.write_bytes(b);rows.append(dict(file=str(p),url=url,sha256=sha(p)))
    dump(R/'SOURCE_DOWNLOADS.json',rows)
    print(json.dumps(dict(revision=str(D),parent_sources_locked=len(lock),sources=rows)))
if __name__=='__main__':main()
