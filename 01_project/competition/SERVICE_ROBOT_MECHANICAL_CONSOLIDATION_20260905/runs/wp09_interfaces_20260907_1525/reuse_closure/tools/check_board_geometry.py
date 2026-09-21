from pathlib import Path
import json,sys,importlib.util,hashlib,math
sys.dont_write_bytecode=True
N=Path(__file__).resolve().parents[1];R=N.parent;c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text())
sp=importlib.util.spec_from_file_location('frozen_geometry',c['geometry_reader']);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths={'source':N/'mechanical/RS422_GSE_SPLICE_BOARD.step','roundtrip':N/'mechanical/RS422_GSE_BOARD_roundtrip.step'}
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
g=m.Geometry({'parts':{k:dict(path=str(p),sha256=sha(p),T_S_local=I) for k,p in paths.items()},'tolerances':c['acceptance']},{})
a=g.load('source');b=g.load('roundtrip');fa=g.facts(a);fb=g.facts(b);dif=[g.volume(a-b),g.volume(b-a)];err=max(abs(fa['bbox_mm'][t][i]-fb['bbox_mm'][t][i]) for t in ['min_mm','max_mm'] for i in range(3));sz=[fa['bbox_mm']['max_mm'][i]-fa['bbox_mm']['min_mm'][i] for i in range(3)];nominal_area=40*30-10*math.pi*0.6**2-5*math.pi*0.3683**2
assert fa['shape_valid'] and fb['shape_valid'] and fa['solid_count']==fb['solid_count']==1 and max(dif)<=1e-5 and err<=1e-5
assert abs(sz[0]-40)<1e-5 and abs(sz[1]-30)<1e-5 and abs(fa['volume_mm3']-nominal_area*sz[2])<1e-5
r=dict(status='PASS_NATIVE_BOARD_MATERIAL_AND_HOLE_VOLUME',source_facts=fa,roundtrip_facts=fb,material_difference_mm3=dif,bbox_error_mm=err,measured_size_mm=sz,pcb_nominal_total_thickness_mm=1.6,body_thickness_is_kicad_export_not_stackup_certificate=True,drill_count=15,drill_source='10x1.2mm solder;5x0.7366mm probe',analytic_hole_volume_check=True,coordinate_frame='KiCad board export coordinates, Y inverted; not spacecraft S',integrated_into_705=False,assembly_count_delta=0,manufacturing_release=False,scope='bare board body only; no copper/soldermask/components/lead dressing represented',native_sha256=sha(N/'mechanical/native/RS422_GSE_SPLICE_BOARD.SLDPRT'))
(N/'results/NATIVE_BOARD_MATERIAL.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(dict(status=r['status'],size=sz,volume=fa['volume_mm3'],diff=dif)))
