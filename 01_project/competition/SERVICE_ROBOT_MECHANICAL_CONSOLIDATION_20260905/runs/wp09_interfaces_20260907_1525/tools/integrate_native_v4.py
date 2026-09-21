"""Copy WP08 assembly, remove only six obsolete instances, insert 82 checked instances."""
from pathlib import Path
import sys,json,importlib.util,argparse,copy,shutil,gc,re,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];W8=R.parent/'wp08_retention_delta_20260907_1228'
fp=R.parent/'wp09_electro_propulsion_20260907_1350/tools/build_module_native.py'
spec=importlib.util.spec_from_file_location('wp09_native_parent',fp);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def t16(T):return [T[i][j] for j in range(3) for i in range(3)]+[T[i][3]/1000 for i in range(3)]+[1.,0.,0.,0.]
class Builder(m.ModuleBuilder):
    def metadata(self,model,rows,measure=False):
        asm=self.wrap(model,'IAssemblyDoc');raw=asm.GetComponents(True) or [];registry={r['id']:r for r in rows};assert len(raw)==len(registry)==len(rows)
        observed=[];lookup={};hashes={};mathutil=self.wrap(self.sw.GetMathUtility(),'IMathUtility')
        for n,rc in enumerate(raw):
            self.ram_floor();comp=self.wrap(rc,'IComponent2');k=comp.ComponentReference;assert k in registry and k not in lookup
            row=registry[k];path=m.normalized(m.val(comp,'GetPathName'));assert path==m.normalized(row['native_path'])
            if path not in hashes:hashes[path]=m.sha(row['native_path'])
            assert hashes[path]==row['native_sha256']
            tr=self.wrap(comp.Transform2,'IMathTransform');tv=list(tr.ArrayData);assert max(abs(x-y) for x,y in zip(tv,t16(row['T_S_local'])))<=1e-8
            assert comp.IsFixed() and comp.GetSuppression2() in (1,2,4)
            o=dict(id=k,path=row['native_path'],sha256=hashes[path],transform_sw16=tv,fixed=True,visible=comp.Visible)
            if measure and k in self.report.get('new_instance_ids',[]):
                comp.SetSuppression2(2);assert comp.GetSuppression2()==2
                bodies,_=self.component_bodies(comp,0);sheets,_=self.component_bodies(comp,1)
                assert len(bodies)==row.get('expected_solids',1) and not sheets
                basis=[]
                for xyz in (([0,0,0],[10,0,0],[0,10,0],[0,0,10]) if k in self.report.get('new_instance_ids',[]) else []):
                    point=self.wrap(mathutil.CreatePoint(self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8,[v/1000 for v in xyz])),'IMathPoint')
                    q=self.wrap(point.MultiplyTransform(tr),'IMathPoint');actual=[v*1000 for v in q.ArrayData];T=row['T_S_local'];expected=[sum(T[i][j]*xyz[j] for j in range(3))+T[i][3] for i in range(3)]
                    err=max(abs(a-b) for a,b in zip(actual,expected));assert err<=1e-5;basis.append(err)
                o.update(actual_solids=len(bodies),actual_sheets=len(sheets),basis_max_error_mm=max(basis) if basis else None);bodies=sheets=point=q=None
            observed.append(o);lookup[k]=comp
            if measure and n%8==7:
                gc.collect();asm.LightweightAllResolved();self.report['cold_progress']=len(observed);self.checkpoint('cold_batch',components=len(observed))
        if measure:asm.LightweightAllResolved()
        return lookup,observed
def main():
    ap=argparse.ArgumentParser();ap.add_argument('state',choices=['service','parking','released']);a=ap.parse_args()
    chk=json.loads((R/'results/NATIVE_MATERIAL_CHECK_V2.json').read_text());assert chk['status']=='PASS_ALL_CANONICAL_NATIVE_MATERIAL_TRANSFERS'
    cp=R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json';c=json.loads(cp.read_text());cm=json.loads((R/'results/CANONICAL_NATIVE_INPUTS.json').read_text());mi=json.loads((R/'results/INTEGRATION_MANIFEST_V6.json').read_text())
    base=copy.deepcopy(c['states'][a.state]['instances']);rows=[r for r in base if r['id'] not in mi['removed_parent_ids']]
    parts={r['id']:r for r in cm['unique_parts']}
    for row in cm['instances']:
        q=parts[row['canonical_id']];p=R/'native/p'/(q['id']+'.SLDPRT');rows.append(dict(id=row['id'],native_path=str(p),native_sha256=m.sha(p),T_S_local=row['T_native_to_S'],expected_solids=1,representation_role=row['source_role']))
    assert len(rows)==701 and len(base)==625
    parent=W8/'native'/('WP08_ROBOT_'+a.state.upper()+'.SLDASM');assert parent.exists();parenthash=m.sha(parent)
    parent_delivery=W8/'results/DELIVERY_STATUS.json';pd=json.loads(parent_delivery.read_text());ps=pd['native_states'][a.state]
    assert ps['native']['sha256']==parenthash and ps['component_count']==625 and ps['solid_count']==1006
    parent_receipt=Path(ps['execution_receipt']['path']);assert m.sha(parent_receipt)==ps['execution_receipt']['sha256']
    pr=json.loads(parent_receipt.read_text());assert pr['status']=='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN' and pr['native_save']['sha256']==parenthash
    pc=Path(ps['independent_check']['path']);assert m.sha(pc)==ps['independent_check']['sha256']
    pi=json.loads(pc.read_text());assert pi['status']=='PASS_SCOPED_NATIVE_DELTA_AND_EXACT_MEMBERSHIP' and pi['native_sha256']==parenthash
    assert all(m.sha(p)==h for p,h in c['source_inputs'].items())
    target=R/'native'/('WP09_'+a.state.upper()+'.SLDASM');work=R/'native/work'/('W_'+a.state+'.SLDASM');assert not target.exists() and not work.exists()
    out=R/'results'/('NATIVE_'+a.state.upper()+'.json');assert not out.exists()
    report=dict(status='RUNNING',state=a.state,parent=str(parent),parent_sha256=parenthash,parent_receipt_sha256=m.sha(parent_receipt),coordinate_frame='S_WORLD_MM_NATIVE_PART_LOCAL_WITH_EXPLICIT_TRANSFORMS',parts=[],progress=[],save_attempts=[],rows=rows,new_instance_ids=[r['id'] for r in rows[619:]],basis_probe_scope='NEW_82_INSTANCES; FULL_MATRIX_READBACK_ALL_701',retained_body_evidence='HASH_VERIFIED_WP08_NATIVE_STATE_RECEIPT_WITH_CURRENT_COMPONENT_PATH_HASH_AND_TRANSFORM_READBACK',manufacturing_release=False,mate_based_motion=False,body_counts_are_actual=False)
    report.update(parent_delivery_sha256=m.sha(parent_delivery),parent_receipt_path=str(parent_receipt),parent_independent_check_sha256=m.sha(pc))
    b=None
    try:
        b=Builder(out,report);assert not b.documents(),'Existing docs left untouched';sw=b.sw
        work.parent.mkdir(exist_ok=True);shutil.copy2(parent,work)
        opened=sw.OpenDoc6(str(work),2,193,'',0,0);assert opened[0] is not None and opened[1]==0
        model=b.wrap(opened[0],'IModelDoc2');b.activate(model,work);asm=b.wrap(model,'IAssemblyDoc');asm.LightweightAllResolved()
        lookup,before=b.metadata(model,base);report['parent_metadata_verified']=True
        model.ClearSelection2(True)
        for ident in mi['removed_parent_ids']:assert lookup[ident].Select4(True,None,False)
        ext=b.wrap(model.Extension,'IModelDocExtension');assert ext.DeleteSelection2(0);model.ClearSelection2(True)
        lookup,remaining=b.metadata(model,[r for r in base if r['id'] not in mi['removed_parent_ids']]);report['retained_verified']=len(remaining)
        view=b.wrap(model.ActiveView,'IModelView');feature=b.wrap(model.FeatureManager,'IFeatureManager');settings=[(sw,'CommandInProgress'),(view,'EnableGraphicsUpdate'),(feature,'EnableFeatureTree'),(feature,'EnableFeatureTreeWindow')];before_ui=[(obj,k,bool(getattr(obj,k))) for obj,k in settings]
        report['ui_before']={k:v for _,k,v in before_ui};b.checkpoint('ui_settings_recorded')
        try:
            for obj,k in settings:setattr(obj,k,k=='CommandInProgress')
            for start in range(0,82,8):
                chunk=rows[619+start:619+start+8];b.ram_floor();raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[r['native_path'] for r in chunk]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[x for r in chunk for x in t16(r['T_S_local'])]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']*len(chunk))) or [];assert len(raw)==len(chunk)
                model.ClearSelection2(True)
                for rc,row in zip(raw,chunk):
                    comp=b.wrap(rc,'IComponent2');comp.ComponentReference=row['id'];comp.Name2=re.sub(r'[ .()/\\]','_',row['id']);assert comp.Select4(True,None,False)
                asm.FixComponent();model.ClearSelection2(True);raw=rc=comp=None;gc.collect();asm.LightweightAllResolved();b.checkpoint('inserted',count=min(start+8,82))
            b.metadata(model,rows);props=b.wrap(ext.CustomPropertyManager(''),'ICustomPropertyManager')
            for k,v in dict(WP09_STATE=a.state,WP09_STATUS='FIXED_POSE_ENGINEERING_CANDIDATE',WP09_COMPONENTS=701,WP09_RELEASE=False,WP09_MOTION='THREE_DISCRETE_POSES_NOT_CONTINUOUS_MATES').items():props.Add3(k,30,str(v),2)
            model.EditRebuild3();report['native_save']=b.save_new(model,target)
        finally:
            for obj,k,v in reversed(before_ui):
                try:setattr(obj,k,v)
                except Exception:pass
            sw.CommandInProgress=before_ui[0][2]
        b.close_own_saved(model,target,report['native_save']['sha256'])
        lookup=remaining=before=asm=model=ext=view=feature=None;gc.collect()
        opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0;cold=b.wrap(opened[0],'IModelDoc2');b.activate(cold,target)
        av=b.wrap(cold.ActiveView,'IModelView');af=b.wrap(cold.FeatureManager,'IFeatureManager');settings=[(sw,'CommandInProgress'),(av,'EnableGraphicsUpdate'),(af,'EnableFeatureTree'),(af,'EnableFeatureTreeWindow')];oldsettings=[(o,k,bool(getattr(o,k))) for o,k in settings]
        try:
            for o,k in settings:setattr(o,k,k=='CommandInProgress')
            _,observed=b.metadata(cold,rows,True);report['cold_components']=observed
        finally:
            for o,k,v in reversed(oldsettings):setattr(o,k,v)
        assert m.sha(target)==report['native_save']['sha256'] and m.sha(parent)==parenthash
        assert all(m.sha(p)==h for p,h in c['source_inputs'].items());report['frozen_inputs_unchanged']=True
        deps=cold.GetDependencies2(False,True,False) or [];assert {m.normalized(deps[i+1]) for i in range(0,len(deps),2)}=={m.normalized(r['native_path']) for r in rows}
        report.update(status='PASS_FIXED_POSE_NATIVE_NEW_BODY_AND_ALL_METADATA_WITH_HASH_BOUND_PARENT',component_count=len(observed),solid_count=sum(r.get('expected_solids',1) for r in rows),new_body_count_actual=sum(x.get('actual_solids',0) for x in observed),retained_solid_count_hash_bound=sum(r.get('expected_solids',1) for r in rows[:619]),body_counts_are_actual=False,continuous_motion_verified=False)
        if not m.val(cold,'GetSaveFlag'):b.close_own_saved(cold,target,m.sha(target))
        assert not b.documents();sw.ExitApp();b.checkpoint('native_integrated_verified_empty_exit')
    except Exception as ex:
        report.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc())
        if b:b.checkpoint('failed')
        else:out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    finally:
        if b:b.pythoncom.CoUninitialize()
if __name__=='__main__':main()
