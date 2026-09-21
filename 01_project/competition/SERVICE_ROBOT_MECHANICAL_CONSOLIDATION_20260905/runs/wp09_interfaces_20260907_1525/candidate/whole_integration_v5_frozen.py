"""Retain every unmodified WP08 instance and insert exact checked WP09 delta."""
from pathlib import Path
import json,hashlib,sys,importlib.util,argparse,copy
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def manifest():
    c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V5.json').read_text());e=json.loads((R/'results/EMISSION_V5.json').read_text());ch=json.loads((R/'results/INTEGRATION_CHECK_V5.json').read_text());assert ch['status']=='DELTA_GEOMETRY_CLEAR'
    result=dict(schema='WP09_THREE_STATE_DELTA_MANIFEST',parent=c['parent_manifest'],parent_sha256=c['parent_manifest_sha256'],removed_parent_ids=ch['removed_parent_ids'],states={},native_integration=False,continuous_motion=False)
    for st,base in c['states'].items():
        rows=[copy.deepcopy(r) for r in base['instances'] if r['id'] not in ch['removed_parent_ids']]
        for k,v in e['parts'].items():rows.append(dict(id=k,step_path=v['path'],source_sha256=v['sha256'],T_S_local=I,bounds_mm=v['bbox_mm'],representation_role=v['representation_role'],expected_solids=1,change='WP09_ADD_OR_REPLACE',native_path=None,source_mass_kg=None,mass_source='UNASSIGNED_AFTER_GEOMETRY_CHANGE'))
        assert len(rows)==len({r['id'] for r in rows})==701
        result['states'][st]=dict(instances=rows,component_count=len(rows),expected_solid_total=sum(r.get('expected_solids',1) for r in rows),retained_parent_count=619,new_instance_count=82)
    (R/'results/INTEGRATION_MANIFEST_V5.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result,c
def build(state='service'):
    mf,c=manifest();rows=mf['states'][state]['instances']
    spec=importlib.util.spec_from_file_location('whole_wp09_geometry',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    g=m.Geometry({'parts':{r['id']:dict(path=r['step_path'],sha256=r['source_sha256'],T_S_local=r['T_S_local']) for r in rows},'tolerances':c['acceptance']},dict(c['source_inputs']))
    from cadgen.assembly import AssemblyHelper
    from build123d import Color
    a=AssemblyHelper('WP09_ROBOT_'+state.upper());counts={}
    for n,row in enumerate(rows):
        s=g.load(row['id']);count=len(s.solids());assert count==row.get('expected_solids',1),(row['id'],count)
        color=(.92,.3,.08) if row['id']=='PROP_PWR_ROUTE' else (.1,.4,.9) if row['id']=='PROP_DATA_ROUTE' else (.3,.65,.47,.25) if row['representation_role']=='FUNCTIONAL_ENVELOPE' else (.71,.73,.76)
        a.add(type(s)(s.wrapped).located(s.global_location),row['id'],color=Color(*color));counts[row['id']]=count
        if n%100==0:print('WHOLE',n,len(rows),flush=True)
    return a.build(),counts
def main():
    ap=argparse.ArgumentParser();ap.add_argument('state',choices=['service','parking','released']);arg=ap.parse_args();a,counts=build(arg.state)
    from build123d import export_step
    p=R/'candidate'/('robot_'+arg.state+'_v5.step');assert not p.exists();export_step(a,p)
    result=dict(status='NAMED_WHOLE_STEP_EMITTED_FROM_CHECKED_DELTA',path=str(p),sha256=sha(p),state=arg.state,component_count=len(counts),solid_count=sum(counts.values()),instance_solids=counts,manifest_sha256=sha(R/'results/INTEGRATION_MANIFEST_V5.json'),native=False)
    (R/'results'/('WHOLE_'+arg.state.upper()+'_V5.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('WHOLE_EMITTED',len(counts),sum(counts.values()))
if __name__=='__main__':main()
