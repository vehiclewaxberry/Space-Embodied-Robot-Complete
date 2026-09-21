"""Exact six-replacement / 28-addition WP08, single existing SW session only."""
from pathlib import Path
import sys,json,copy,gc,re,shutil,traceback,argparse,time
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];W7=R.parent/'wp07_system_20260907_0610'
sys.path.insert(0,str(W7/'tools'))
import resume_service as reuse
import integrate_native as oldbase
import build_native_local as swbase
sys.path.insert(0,str(R/'tools'))
from check_native_delta import read,sha,norm,t16,check_rows,expected_rows
require=oldbase.require;val=oldbase.val

class Builder(reuse.ComponentwiseIntegrator):
    def metadata(self,model,rows):
        a=self.wrap(model,'IAssemblyDoc');raw=a.GetComponents(True) or [];expected={r['id']:r for r in rows};observed=[];lookup={};hashes={}
        require(len(raw)==len(rows)==len(expected),'Unexpected actual component multiset length')
        for item in raw:
            c=self.wrap(item,'IComponent2');ident=c.ComponentReference
            require(ident in expected and ident not in lookup,'Unknown or duplicate component identity: '+str(ident))
            row=expected[ident];path=norm(val(c,'GetPathName'))
            require(path==norm(row['native_path']),'Wrong native dependency '+ident)
            if path not in hashes:hashes[path]=sha(path)
            require(hashes[path]==row['native_sha256'],'Native dependency changed '+ident)
            tr=self.wrap(c.Transform2,'IMathTransform');v=list(tr.ArrayData);tr=None
            require(len(v)==16 and max(abs(x-y) for x,y in zip(v,t16(row['T_S_local'])))<1e-8,'Transform mismatch '+ident)
            require(bool(c.IsFixed()) and c.GetSuppression2() in (1,2,4),'Hidden/suppressed/unfixed source '+ident)
            require(c.Visible==row['expected_visible'],'Source visibility changed '+ident)
            observed.append(dict(id=ident,path=path,sha256=hashes[path],transform_sw16=v,fixed=True,visible=c.Visible,suppression=c.GetSuppression2()));lookup[ident]=c
        return lookup,observed

    def inspect_delta(self,model,rows,path):
        a=self.wrap(model,'IAssemblyDoc');view=self.wrap(model.ActiveView,'IModelView');feature=self.wrap(model.FeatureManager,'IFeatureManager')
        require(view is not None and feature is not None,'Cannot preserve actual UI settings')
        settings=[(self.sw,'CommandInProgress',True),(view,'EnableGraphicsUpdate',False),(feature,'EnableFeatureTree',False),(feature,'EnableFeatureTreeWindow',False)]
        before=[(obj,name,bool(getattr(obj,name))) for obj,name,_ in settings];applied=[]
        result=dict(status='RUNNING',assembly_path=str(path),component_count=0,solid_count=0,components=[],expected_components=len(rows),expected_solids=sum(r['expected_solids'] for r in rows),batch_size=10,body_evidence='ACTUAL_CURRENT_COLD_BODY_COUNTS_AND_COM_FOUR_POINT_VECTORS_NO_REUSED_BODY_OBSERVATIONS')
        self.report['cold_inspection']=result;self.report['ui_control_before']={name:v for _,name,v in before}
        try:
            for obj,name,wanted in settings:
                applied.append(name);setattr(obj,name,wanted);require(bool(getattr(obj,name))==wanted,'UI setter failed '+name)
            model.ClearSelection2(True);result['initial_unload_api_return']=a.LightweightAllResolved()
            lookup,meta=self.metadata(model,rows);self.report['cold_metadata']=meta
            self.checkpoint('cold_all_metadata_checked',count=len(meta))
            for start in range(0,len(rows),10):
                completed=[];begin=time.monotonic()
                try:
                    for row in rows[start:start+10]:
                        self.ram_floor();c=lookup[row['id']];self.report['active_component']=row['id']
                        if c.GetSuppression2()!=2:c.SetSuppression2(2)
                        require(c.GetSuppression2()==2,'Single part resolution failed '+row['id'])
                        observed=self._measure_resolved(c,row,row['native_sha256'])
                        observed['measurement_session']=str(self.report_path);result['components'].append(observed);completed.append(observed)
                        result['component_count']+=1;result['solid_count']+=observed['solid_count'];c=None
                finally:
                    gc.collect();unload=a.LightweightAllResolved()
                    for row in completed:
                        row['final_suppression_state']=lookup[row['id']].GetSuppression2();require(row['final_suppression_state'] in (1,4),'Measured part did not unload')
                    self.checkpoint('cold_batch_persisted',completed=result['component_count'],unload_api_return=unload,elapsed_s=time.monotonic()-begin,memory=self.memory_snapshot())
            checked=check_rows(result['components'],rows);require(checked['status']=='PASS','Independent current body/vector replay failed')
            deps=model.GetDependencies2(False,True,False) or [];require(len(deps)%2==0,'Malformed dependency table')
            paths=[deps[i+1] for i in range(0,len(deps),2)];require({norm(p) for p in paths}=={norm(r['native_path']) for r in rows},'Native dependencies differ')
            result.update(status='PASS_CURRENT_COLD_READBACK',dependency_paths=paths,unique_dependencies=len(set(norm(p) for p in paths)),completed_all_components=True)
            self.report.pop('active_component',None);self.checkpoint('complete_cold_measurements_before_ui_restore')
        finally:
            restored=[]
            for obj,name,wanted in reversed(before):
                if name not in applied:continue
                try:setattr(obj,name,wanted);restored.append(dict(property=name,expected=wanted,actual=bool(getattr(obj,name)),restored=bool(getattr(obj,name))==wanted))
                except Exception as e:restored.append(dict(property=name,restored=False,error=repr(e)))
            self.report['ui_control_restore']=restored;self.checkpoint('ui_controls_restored_without_redraw');require(all(r['restored'] for r in restored),'UI restoration incomplete')
        return result

    def integrate(self,state,info,parent_rows):
        target=R/f'native/WP08_ROBOT_{state.upper()}.SLDASM';work=R/f'native/work/WP08_WORK_{state.upper()}.SLDASM'
        require(not target.exists() and not work.exists(),'Existing candidate native file protected')
        parent=Path(info['parent_assembly_path']);require(sha(parent)==info['parent_assembly_sha256'],'Parent changed')
        work.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(parent,work)
        self.checkpoint('parent_copied',source=str(parent),work=str(work),source_sha256=sha(parent),work_sha256=sha(work))
        opened=self.sw.OpenDoc6(str(work),2,193,'',0,0);require(isinstance(opened,tuple) and len(opened)==3 and opened[0] is not None and opened[1]==0,'Parent copy open failed')
        model=self.wrap(opened[0],'IModelDoc2');opened=None;self.activate(model,work);a=self.wrap(model,'IAssemblyDoc');a.LightweightAllResolved()
        lookup,before=self.metadata(model,parent_rows);self.report['parent_actual_metadata']=before
        old_ids=set(lookup);replacement=set(info['replaced_ids']);added_ids=set(info['added_ids']);rows=info['instances'];expected={r['id']:r for r in rows}
        exact={f'hold_fold_mast_{k}' for k in (0,1)}|{f'hold_shoe_guide_{k}_{x}' for k in (0,1) for x in (-10,10)}
        require(replacement==exact and replacement<=old_ids and len(added_ids)==28 and not added_ids&old_ids,'Delta contract invalid')
        require(set(expected)==old_ids|added_ids,'Final ID contract invalid')
        model.ClearSelection2(True)
        for ident in sorted(replacement):require(lookup[ident].Select4(True,None,False),'Cannot select exact replacement '+ident)
        extension=self.wrap(model.Extension,'IModelDocExtension');require(extension.DeleteSelection2(0),'Exact instance deletion failed');model.ClearSelection2(True)
        remaining_rows=[r for r in parent_rows if r['id'] not in replacement]
        rem_lookup,remaining=self.metadata(model,remaining_rows)
        require(set(rem_lookup)==old_ids-replacement,'Unexpected instance deleted')
        prior={r['id']:r for r in before};stable=('id','path','sha256','transform_sw16','fixed','visible')
        require(all(all(r[key]==prior[r['id']][key] for key in stable) for r in remaining),'Surviving identity/path/hash/transform/fixed state changed')
        self.report['after_exact_deletion']=dict(deleted_ids=sorted(replacement),retained_ids=sorted(rem_lookup),unchanged_survivor_metadata=True)
        lookup=rem_lookup=before=remaining=None;gc.collect();self.checkpoint('six_only_removed_and_survivors_preserved',remaining=len(remaining_rows))
        new=[r for r in rows if r['id'] in replacement|added_ids];require(len(new)==34,'Expected 34 responsibility instances')
        transforms=[v for row in new for v in t16(row['T_S_local'])]
        raw=a.AddComponents3(self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR,[r['native_path'] for r in new]),self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8,transforms),self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR,['']*len(new))) or []
        require(len(raw)==len(new),'Insertion incomplete')
        model.ClearSelection2(True)
        for item,row in zip(raw,new):
            comp=self.wrap(item,'IComponent2');comp.ComponentReference=row['id'];comp.Name2=re.sub(r'[ .()/\\]','_',row['id']);require(comp.Select4(True,None,False),'Cannot select inserted component')
        a.FixComponent();model.ClearSelection2(True)
        props=self.wrap(extension.CustomPropertyManager(''),'ICustomPropertyManager')
        for key,value in dict(WP08_STATE=state,WP08_INSTANCES=len(rows),WP08_MANIFEST_SHA256=self.report['manifest_sha256'],WP08_STATUS='FIXED_POSE_RETENTION_DELTA_CANDIDATE',WP08_MOTION_MODEL='NONE_FIXED_POSES',WP08_BASELINE='WP07_EXECUTED_THREE_STATE').items():props.Add3(key,30,str(value),2)
        model.EditRebuild3();new_lookup,warm=self.metadata(model,rows);self.report['warm_preflight']=dict(component_count=len(warm),components=warm)
        require(all(sum(r['id']==f'hold_saddle_{k}' for r in warm)==1 for k in (0,1)),'Saddle context duplicate')
        self.report['native_save']=self.save_new(model,target);digest=self.report['native_save']['sha256'];self.report['final_native_sha256']=digest
        self.close_own_saved(model,target,digest);new_lookup=raw=item=comp=props=extension=a=model=None;gc.collect();self.checkpoint('saved_closed_before_cold_readback',native_sha256=digest)
        cold,self.report['cold_open']=reuse.open_readonly(self,target)
        self.inspect_delta(cold,rows,target);self.report['cold_inspection_native_sha256']=digest
        require(sha(target)==digest and sha(parent)==info['parent_assembly_sha256'],'Saved or parent bytes changed during cold read')
        self.report['left_open_dirty_flag']=bool(val(cold,'GetSaveFlag'));self.report['no_save_after_cold']=True
        self.report['status']='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN';self.checkpoint('native_state_complete',state=state,component_count=len(rows),solid_count=sum(r['expected_solids'] for r in rows))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('state',choices=['service','parking','released']);args=ap.parse_args()
    output=R/f'results/NATIVE_{args.state.upper()}.json';require(not output.exists(),'Existing execution receipt protected')
    mp=R/'results/INTEGRATION_MANIFEST.json';m=read(mp);info=copy.deepcopy(m['states'][args.state]);parent=read(m['base_manifest'])['states'][args.state]['instances']
    info['instances']=expected_rows(info)
    visibility={r['id']:r['visible'] for r in read(info['parent_receipt_path'])['cold_inspection']['components']}
    for row in parent:row['expected_visible']=visibility[row['id']]
    report=dict(schema='WP08_NATIVE_RETENTION_DELTA_EXECUTION',status='RUNNING',state=args.state,manifest_sha256=sha(mp),progress=[],save_attempts=[],full_STEP_verified=False,global_collision_verified=False,continuous_motion_verified=False,manufacturing_release=False,source_geometry_changed=False)
    builder=None
    try:
        reuse.require_outer_guard(report);pins=dict(m['input_sha256_after'])
        for p in (mp,Path(__file__),Path(reuse.__file__),Path(oldbase.__file__),Path(swbase.__file__),R/'tools/check_native_delta.py'):pins[str(p.resolve())]=sha(p)
        for p,d in pins.items():require(sha(p)==d,'Pinned input changed '+p)
        report['input_sha256_before']=pins
        allowed={oldbase.normalized(r['native_path']):r['native_sha256'] for s in m['states'].values() for r in s['instances']}
        for s in m['states'].values():allowed[oldbase.normalized(s['parent_assembly_path'])]=s['parent_assembly_sha256']
        for p in (R/'results').glob('NATIVE_*.json'):
            if p==output:continue
            d=read(p)
            if d.get('status')=='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN':allowed[oldbase.normalized(d['native_save']['path'])]=d['native_save']['sha256']
        # Parent old replaced parts may be resident as dependencies too.
        for s in read(m['base_manifest'])['states'].values():
            for row in s['instances']:allowed[oldbase.normalized(row['native_path'])]=row['native_sha256']
        builder=Builder(output,report);require(int(val(builder.sw,'GetProcessID'))==26208,'Existing singleton PID changed')
        builder.checkpoint('attached_existing_session',documents=[d for _,d in builder.documents()])
        builder.close_registered(allowed);builder.sw.Visible=True;builder.sw.UserControl=True
        builder.integrate(args.state,info,parent)
        report['inputs_unchanged']=all(sha(p)==d for p,d in pins.items());require(report['inputs_unchanged'],'Input changed during native write')
        report['input_sha256_after']=pins;builder.checkpoint('completed')
    except Exception as exc:
        report.update(status='FAILED',error=str(exc),traceback=traceback.format_exc());output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');raise
    finally:
        if builder and builder.initialized:builder.pythoncom.CoUninitialize()
if __name__=='__main__':main()
