"""Reuse the checked native builder, with the horizontal source/pose plan."""
from geometry import *
import argparse, importlib.util
PN=D/'inputs/NATIVE_ASSEMBLY_PLAN.json'

def prepare():
    assert read(D/'results/INCREMENT_STATIC_CHECK.json')['valid']
    lay=read(D/'inputs/INSTALLATION_LAYOUT.json');old=read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json')
    changed={r['id']:r for r in lay['replacements']+lay['pose_changes']};gid='R6H_CORE_INSTALLATION'
    expected=[dict(changed.get(r['id'],r),group=r['group']) for r in old['expected_leaves']]+[dict(r,group=gid) for r in lay['parts']]
    gids={r['group'] for r in expected if r['id'] in changed}|{gid}
    groups=[dict(id=k,path=str(D/'native'/f'{k}_R6H.SLDASM'),rows=[r for r in expected if r['group']==k]) for k in sorted(gids)]
    byid={x['id']:x for x in groups};top=[dict(r,native_path=byid[r['id']]['path']) if r['id'] in byid else r for r in old['top_rows']]+[dict(id=gid,native_path=byid[gid]['path'],T_S_local=I)]
    dl=read(R4/'results/NATIVE_ASSEMBLY_DELIVERY.json')
    locks=old['source_native_files']+[dict(path=x['target'],sha256=x['native_save']['sha256']) for x in dl['parts']]+[x['saved'] for x in dl['groups']]+[dl['service']['saved']]
    locks=list({str(Path(x['path']).resolve()).lower():x for x in locks}.values());assert all(sha(x['path'])==x['sha256'] for x in locks)
    plan=dict(schema='R6H_HORIZONTAL_NATIVE_PLAN_V1',parts=lay['parts']+lay['replacements'],groups=groups,top_rows=top,expected_leaves=expected,
      expected_leaf_count=len(expected),expected_solid_instances=sum(r['expected_solids'] for r in expected),source_native_files=locks,
      source_R4_plan_sha256=sha(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json'),source_layout_sha256=sha(D/'inputs/INSTALLATION_LAYOUT.json'),increment_static_check_sha256=sha(D/'results/INCREMENT_STATIC_CHECK.json'),
      horizontal_MAIN=True,exterior_changed=False,portable_package=False,whole_design_complete=False,ready_to_power=False,flight_ready=False)
    write(PN,plan);print('PLAN',len(plan['parts']),len(groups),len(expected),plan['expected_solid_instances'],flush=True)

def run():
    sp=importlib.util.spec_from_file_location('scoped_native_builder',R6/'tools/assemble_native.py');builder=importlib.util.module_from_spec(sp);sp.loader.exec_module(builder)
    builder.D=D;builder.PN=PN;builder.TOP_NATIVE_FILENAME='SERVICE_STAR_SERVICE_R6H.SLDASM'
    original_material=builder.candidate_material
    def material(b,row):
        if row['id']=='R6H_IF_THERMAL_BRIDGE':return original_material(b,dict(row,id='R6_IF_THERMAL_BRIDGE'))
        return None
    builder.candidate_material=material
    builder.run()
    rp=D/'results/NATIVE_ASSEMBLY_DELIVERY.json';r=read(rp);assert r['status']=='PASS_R6_FIXED_POSE_NATIVE_BUILD'
    r['status']='PASS_R6H_HORIZONTAL_FIXED_POSE_NATIVE_BUILD';r['horizontal_MAIN']=True
    r['top_native_filename_note']='SERVICE_STAR_SERVICE_R6H.SLDASM is the horizontal final candidate.'
    write(rp,r)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','run']);a=ap.parse_args();{'prepare':prepare,'run':run}[a.mode]()
