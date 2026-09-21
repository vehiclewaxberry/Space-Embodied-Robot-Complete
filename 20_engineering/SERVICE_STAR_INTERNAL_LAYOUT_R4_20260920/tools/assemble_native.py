"""R4 local native delta; canonical geometry always paired with its own transform."""
from geometry import *
import sys,traceback,argparse
PN=D/'inputs/NATIVE_ASSEMBLY_PLAN.json'
def prepare():
    assert read(D/'results/INCREMENT_STATIC_CHECK.json')['valid']
    mount=read(D/'inputs/MOUNT_LAYOUT.json');passage=read(D/'inputs/PASSAGE_LAYOUT.json')
    parts=mount['replacements']+passage['replacements']+mount['additions'];changed={r['id']:r for r in parts}
    rows=state_rows()['service'];armgroup=next(r['group'] for r in rows if r['id']=='equipment_arm_drive')
    expected=[dict(changed.get(r['id'],r),group=r['group']) for r in rows]+[dict(r,group=armgroup) for r in mount['additions']]
    gids={r['group'] for r in expected if r['id'] in changed}
    groups=[{'id':gid,'path':str(D/'native'/f'{gid}_R4.SLDASM'),'rows':[r for r in expected if r['group']==gid]} for gid in sorted(gids)]
    old=read(R3/'inputs/NATIVE_ASSEMBLY_PLAN.json');groupsbyid={g['id']:g for g in groups}
    top=[dict(r,native_path=groupsbyid[r['id']]['path']) if r['id'] in groupsbyid else r for r in old['top_rows']]
    delivery=read(R3/'results/NATIVE_ASSEMBLY_DELIVERY.json')
    locks=old['source_native_files']+[{'path':x['target'],'sha256':x['native_save']['sha256']} for x in delivery['parts']]+[delivery[k]['saved'] for k in ['group','service']]
    assert all(sha(x['path'])==x['sha256'] for x in locks)
    assert len(expected)==1130 and len({r['id'] for r in expected})==1130
    plan={'schema':'R4_NATIVE_PLAN_V1','parts':parts,'groups':groups,'top_rows':top,'expected_leaves':expected,
          'source_native_files':locks,'expected_leaf_count':len(expected),'expected_solid_instances':sum(r['expected_solids'] for r in expected),
          'increment_static_check_sha256':sha(D/'results/INCREMENT_STATIC_CHECK.json'),
          'CF1_installed':False,'material_mass_inertia_complete':False,'portable_package':False}
    write(PN,plan);print('PLAN',len(parts),'new part files;',len(groups),'rebuilt groups;',len(expected),'leaves;',plan['expected_solid_instances'],'solids')
def run():
    sys.path.insert(0,str(R1/'tools'));import native_integrate as ni;ni.OUT=D
    import build_integrated as bi;bi.OUT=D
    plan=read(PN);rp=D/'results/NATIVE_ASSEMBLY_DELIVERY.json';assert not rp.exists()
    report={'status':'RUNNING','progress':[],'parts':[],'groups':[],'save_attempts':[],
            'coordinate_frame':'STEP_AND_S_MM_IDENTITY_SINGLE_TRANSFORM','plan_sha256':sha(PN),
            'whole_design_complete':False,'ground_power_ready':False,'flight_ready':False}
    ni.configure_com();b=ni.PrototypeBuilder(rp,report);sw=b.sw
    prefs={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)}
    try:
        assert all(sha(x['path'])==x['sha256'] for x in plan['source_native_files'])
        for k in prefs:sw.SetUserPreferenceToggle(k,k==111)
        for p in plan['parts']:
            sw.DocumentVisible(False,1);b.import_part(p)
            facts=report['parts'][-1]['part_cold_reopen']['facts'];assert abs(facts['volume_mm3']-p['expected_volume_mm3'])<1e-3
        todo=[(g['id'],g['rows'],Path(g['path'])) for g in plan['groups']]+[('service',plan['top_rows'],D/'native/SERVICE_STAR_SERVICE_R4.SLDASM')]
        for tag,rows,target in todo:
            sw.DocumentVisible(False,2);sw.CommandInProgress=True;saved=bi.make(b,rows,target,tag);sw.CommandInProgress=False
            opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
            doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');lookup=b.identity_inventory(asm,rows)
            for r in rows:
                c=lookup[r['id']];assert ni.m.normalized(c.GetPathName())==ni.m.normalized(r['native_path'])
                assert max(abs(x-y) for x,y in zip(list(b.wrap(c.Transform2,'IMathTransform').ArrayData),ni.h.t16(r['T_S_local'])))<1e-8 and c.IsFixed()
            item={'id':tag,'saved':saved,'cold_errors':opened[1],'cold_warnings':opened[2],'direct_children':len(rows),
                  'needs_rebuild2':int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2)}
            if tag=='service':report['service']=item
            else:report['groups'].append(item)
            b.close_own_saved(doc,target,saved['sha256']);b.checkpoint('cold_checked',tag=tag)
        report.update(status='PASS_R4_LOCAL_FIXED_POSE_NATIVE_BUILD',source_native_files_unchanged=all(sha(x['path'])==x['sha256'] for x in plan['source_native_files']),new_material_assignment=False)
        assert report['source_native_files_unchanged'];b.checkpoint('complete')
    except Exception as e:
        report.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        for k,v in prefs.items():sw.SetUserPreferenceToggle(k,v)
        sw.CommandInProgress=False;sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
        if report.get('status','').startswith('PASS_') and report['session']['new_process'] and not b.documents():sw.ExitApp()
        b.pythoncom.CoUninitialize()
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','run']);args=a.parse_args();{'prepare':prepare,'run':run}[args.mode]()
