"""Copy and patch fixed-pose WP05 assemblies with exactly the verified WP06 delta.

Never write a parent or dependency. Existing unsaved/unregistered documents stop
the job. DeleteSelection2(0) is scoped to twelve explicit top-level instances;
AddComponents3 inserts only 24 global-coordinate WP06 parts at identity.
"""
from pathlib import Path
import sys, json, shutil, re, datetime as dt, traceback
R=Path(__file__).resolve().parents[1]
W6=R.parent/'wp06_side_joint_20260907_0233'
sys.path.insert(0,str(W6/'tools'))
from build_native_local import Builder,require,sha,normalized,val,IDENTITY16

def t16(T):
    return [T[i][j] for j in range(3) for i in range(3)]+[T[i][3]/1000 for i in range(3)]+[1.,0.,0.,0.]

class Integrator(Builder):
    def close_registered(self,allowed):
        docs=self.documents()
        for _,d in docs:
            require(d['path'] and normalized(d['path']) in allowed,'Unregistered open document; preserving: '+str(d))
            require(not d['dirty'],'Unsaved document; preserving: '+d['path'])
            require(sha(d['path'])==allowed[normalized(d['path'])], 'Open document hash changed: '+d['path'])
        # Assemblies first; the application may automatically unload dependencies.
        for typ in (2,1):
            for doc,d in self.documents():
                if d['document_type']!=typ:continue
                require(not val(doc,'GetSaveFlag'),'Document became dirty before close')
                self.sw.CloseDoc(d['title'])
        require(not self.documents(),'Documents remain after scoped close')
        self.checkpoint('registered_clean_documents_closed',count=len(docs))

    def inspect(self,m,rows,expected_path):
        a=self.wrap(m,'IAssemblyDoc'); m.ClearSelection2(True)
        resolution=a.ResolveAllLightweight()
        raw=a.GetComponents(True) or []
        require(len(raw)==len(rows),'Instance count differs')
        lookup={r['id']:r for r in rows}; observed=[]
        util=self.wrap(self.sw.GetMathUtility(),'IMathUtility')
        hashes={}
        for item in raw:
            self.ram_floor(); c=self.wrap(item,'IComponent2'); ident=c.ComponentReference
            require(ident in lookup,'Unexpected ComponentReference: '+str(ident)); e=lookup[ident]
            path=Path(val(c,'GetPathName')).resolve()
            require(normalized(path)==normalized(e['native_path']),'Dependency path changed: '+ident)
            digest=hashes.setdefault(str(path),sha(path))
            require(digest==e['native_sha256'],'Native dependency changed: '+ident)
            if c.GetSuppression2()!=2:c.SetSuppression2(2)
            require(c.GetSuppression2()==2,'Cannot resolve: '+ident)
            transform=self.wrap(c.Transform2,'IMathTransform'); values=list(transform.ArrayData)
            error=max(abs(x-y) for x,y in zip(values,t16(e['T_S_local'])))
            require(error<1e-8 and c.IsFixed(),'Fixed pose mismatch: '+ident)
            basis_error=0.
            for p in ([0.,0.,0.],[10.,0.,0.],[0.,10.,0.],[0.,0.,10.]):
                point=self.wrap(util.CreatePoint(self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8,[x/1000 for x in p])),'IMathPoint')
                q=list(self.wrap(point.MultiplyTransform(transform),'IMathPoint').ArrayData)
                T=e['T_S_local']; wanted=[sum(T[i][j]*p[j] for j in range(3))+T[i][3] for i in range(3)]
                basis_error=max(basis_error,max(abs(q[i]*1000-wanted[i]) for i in range(3)))
            require(basis_error<=1e-5,'Actual basis point transform mismatch: '+ident)
            doc=self.wrap(c.GetModelDoc2(),'IModelDoc2'); require(doc is not None,'No part document')
            part=self.wrap(doc,'IPartDoc'); bodies=part.GetBodies2(0,False) or []; sheets=part.GetBodies2(1,False) or []
            require(len(bodies)==e['expected_solids'] and not sheets,'Actual body count mismatch: '+ident)
            observed.append(dict(id=ident,path=str(path),sha256=digest,transform_sw16=values,
                world_basis_error_mm=basis_error,solid_count=len(bodies),sheet_count=len(sheets),fixed=True,visible=c.Visible))
            if len(observed)%100==0:self.checkpoint('actual_components_inspected',inspected=len(observed),total=len(rows))
        require(len({o['id'] for o in observed})==len(rows),'Duplicate IDs')
        deps=m.GetDependencies2(False,True,False) or []
        require(len(deps)%2==0,'Malformed dependencies')
        paths=[deps[i+1] for i in range(0,len(deps),2)]
        require({normalized(p) for p in paths}=={normalized(r['native_path']) for r in rows},'Dependency set differs')
        return dict(component_count=len(observed),solid_count=sum(o['solid_count'] for o in observed),components=observed,
                    unique_dependencies=len(paths),resolution_return=resolution,assembly_path=str(expected_path),
                    scope='NATIVE_FIXED_POSE_IDENTITY_PATH_HASH_BODY_COUNT; NOT_CONTINUOUS_MOTION_OR_GLOBAL_COLLISION')

    def integrate(self,state,info,removed,replaced):
        target=R/'native'/('WP07_ROBOT_'+state.upper()+'.SLDASM')
        work=R/'native/work'/('WP07_WORK_'+state.upper()+'.SLDASM')
        step=R/'native'/('WP07_ROBOT_'+state.upper()+'.step')
        for p in (target,work,step):require(not p.exists(),'Existing output protected: '+str(p))
        parent=Path(info['parent_assembly_path']); require(sha(parent)==info['parent_assembly_sha256'],'Parent hash changed')
        work.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(parent,work)
        self.checkpoint('parent_copied',state=state,parent=str(parent),work=str(work),sha256=sha(work))
        opened=self.sw.OpenDoc6(str(work),2,193,'',0,0)
        require(isinstance(opened,tuple) and len(opened)==3 and opened[0] is not None and opened[1]==0,'Copied assembly open failed')
        m=self.wrap(opened[0],'IModelDoc2'); self.activate(m,work); a=self.wrap(m,'IAssemblyDoc')
        raw=a.GetComponents(True) or []; require(len(raw)==585,'Parent is not 585 instances')
        lookup={self.wrap(x,'IComponent2').ComponentReference:self.wrap(x,'IComponent2') for x in raw}
        require(len(lookup)==585,'Parent duplicate IDs')
        ids=set(removed)|set(replaced); require(len(ids)==12 and ids<=lookup.keys(),'Incorrect deletion contract')
        m.ClearSelection2(True)
        for ident in sorted(ids):require(lookup[ident].Select4(True,None,False),'Cannot select exact old instance '+ident)
        ex=self.wrap(m.Extension,'IModelDocExtension')
        require(ex.DeleteSelection2(0),'Exact-instance deletion failed')
        m.ClearSelection2(True)
        left=a.GetComponents(True) or []
        remain={self.wrap(x,'IComponent2').ComponentReference for x in left}
        require(remain==set(lookup)-ids and len(remain)==573,'Deletion affected wrong instances')
        self.checkpoint('exact_twelve_removed',state=state,remaining=len(remain))
        rows=info['instances']; new=[r for r in rows if r['id'] not in remain]
        require(len(new)==24,'Expected exactly 24 inserts')
        for r in new:require(max(abs(x-y) for x,y in zip(t16(r['T_S_local']),IDENTITY16))<1e-12,'Nonidentity WP06 source')
        added=a.AddComponents3(self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR,[r['native_path'] for r in new]),
            self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8,IDENTITY16*len(new)),
            self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR,['']*len(new))) or []
        require(len(added)==24,'Incomplete insert')
        for item,r in zip(added,new):
            c=self.wrap(item,'IComponent2');c.ComponentReference=r['id'];c.Name2=re.sub(r'[ .()/\\]','_',r['id'])
            require(c.Select4(True,None,False),'Cannot select inserted part')
        a.FixComponent();m.ClearSelection2(True)
        props=self.wrap(ex.CustomPropertyManager(''),'ICustomPropertyManager')
        for k,v in dict(WP07_STATE=state,WP07_INSTANCES=597,WP07_STATUS='FIXED_POSE_INTEGRATION_CANDIDATE',
                        WP07_MANIFEST_SHA256=self.report['manifest_sha256'],WP07_MOTION_MODEL='NONE_FIXED_POSES').items():props.Add3(k,30,str(v),2)
        m.EditRebuild3();m.ShowNamedView2('',7);m.ViewZoomtofit2();m.GraphicsRedraw2()
        self.report['warm_inspection']=self.inspect(m,rows,target)
        require(self.report['warm_inspection']['solid_count']==978,'Solid count should be 978')
        saved=self.save_new(m,target);self.report['native_save']=saved
        self.close_own_saved(m,target,saved['sha256'])
        opened=self.sw.OpenDoc6(str(target),2,193,'',0,0)
        require(opened[0] is not None and opened[1]==0,'Cold reopen failed')
        cold=self.wrap(opened[0],'IModelDoc2');self.activate(cold,target)
        self.report['cold_inspection']=self.inspect(cold,rows,target)
        self.report['cold_open']={'errors':opened[1],'warnings':opened[2]}
        cold.ShowNamedView2('',7);cold.ViewZoomtofit2();cold.GraphicsRedraw2()
        bmp=R/'results'/('WP07_'+state.upper()+'.bmp')
        self.report['screenshot']={'path':str(bmp),'saved':bool(cold.SaveBMP(str(bmp),1600,1200))}
        # Export every instance, including functional envelopes, then restore display.
        ca=self.wrap(cold,'IAssemblyDoc'); visibility=[]
        for item in ca.GetComponents(True) or []:
            c=self.wrap(item,'IComponent2');visibility.append((c,c.Visible));c.Visible=1
        cold.ClearSelection2(True);self.report['step_export']=self.save_new(cold,step)
        for c,v in visibility:c.Visible=v
        require(sha(target)==saved['sha256'],'Saved native changed during export/inspection')
        # Visibility toggles may set a dirty flag. Save only this owned final file,
        # preserving the restored display; no dependency save is requested.
        if val(cold,'GetSaveFlag'):
            q=cold.Save3(1,0,0);require(q[0] and q[1]==0,'Could not persist restored visibility')
            self.report['display_restored_save']={'api_return':list(q),'sha256':sha(target)}
        self.report['final_native_sha256']=sha(target)
        self.checkpoint('whole_state_saved_cold_verified_exported',state=state,instances=597,solids=978)
        self.report['status']='PASS_FIXED_POSE_WP06_INTEGRATION_NATIVE_COLD_CHECK'
        return cold,target,step

def main():
    state=sys.argv[1]; mfpath=R/'results/INTEGRATION_MANIFEST.json';mf=json.loads(mfpath.read_text(encoding='utf-8'))
    reportpath=R/'results'/('NATIVE_'+state.upper()+'.json');require(not reportpath.exists(),'Receipt already exists')
    report=dict(status='RUNNING',state=state,manifest_sha256=sha(mfpath),progress=[],save_attempts=[])
    b=None
    try:
        allowed={}
        old=json.loads((W6/'results/DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
        for row in old['files']:
            if Path(row['path']).suffix.lower() in ('.sldprt','.sldasm'):allowed[normalized(W6/row['path'])]=row['sha256']
        for v in mf['states'].values():
            for row in v['instances']:allowed[normalized(row['native_path'])]=row['native_sha256']
        for p in (R/'native').glob('WP07_ROBOT_*.SLDASM'):
            receipt=R/'results'/('NATIVE_'+p.stem.removeprefix('WP07_ROBOT_')+'.json')
            require(receipt.exists(),'Unregistered candidate assembly')
            oldreport=json.loads(receipt.read_text(encoding='utf-8'));require(oldreport.get('status','').startswith('PASS_'),'Earlier candidate not completed')
            allowed[normalized(p)]=oldreport['final_native_sha256']
        for path,digest in allowed.items():require(sha(path)==digest,'Pinned input changed: '+path)
        b=Integrator(reportpath,report);require(int(val(b.sw,'GetProcessID'))==26208,'Unexpected existing SW PID')
        b.close_registered(allowed);b.sw.Visible=True;b.sw.UserControl=True
        info=mf['states'][state]
        b.integrate(state,info,mf['removed_ids'],mf['replaced_ids'])
        report['inputs_unchanged']=all(sha(p)==h for p,h in allowed.items())
        require(report['inputs_unchanged'],'Input integrity failure')
        b.checkpoint('completed')
    except Exception as exc:
        report.update(status='FAILED',error=str(exc),traceback=traceback.format_exc())
        reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    finally:
        if b and b.initialized:b.pythoncom.CoUninitialize()
if __name__=='__main__':main()
