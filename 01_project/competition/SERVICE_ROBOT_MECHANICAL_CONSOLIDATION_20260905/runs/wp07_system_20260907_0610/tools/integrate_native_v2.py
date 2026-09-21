"""WP07 native integration with final save preceding the complete cold inspection.

Only the new run's assembly is edited. The original SERVICE worker/script is not
modified. This entry replaces the base module's Integrator binding explicitly
before invoking its existing main, so this class executes for the next state.
"""
from pathlib import Path
import math
import re
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import integrate_native as base
from integrate_native import require,sha,normalized,val,IDENTITY16,t16,R


class IntegratorV2(base.Integrator):
    def warm_preflight(self,model,rows):
        """Check insertion bookkeeping and transforms without repeated body/point COM calls."""
        assembly=self.wrap(model,'IAssemblyDoc')
        components=assembly.GetComponents(True) or []
        expected={r['id']:r for r in rows};actual=[];hashes={}
        require(len(components)==len(expected)==597,'Warm component count mismatch')
        for item in components:
            component=self.wrap(item,'IComponent2');identity=component.ComponentReference
            require(identity in expected,'Unexpected warm component identity')
            row=expected[identity];path=Path(val(component,'GetPathName')).resolve()
            require(normalized(path)==normalized(row['native_path']),'Warm dependency path mismatch')
            key=str(path)
            if key not in hashes:
                hashes[key]=sha(path)
            require(hashes[key]==row['native_sha256'],'Warm native dependency hash mismatch')
            matrix=list(self.wrap(component.Transform2,'IMathTransform').ArrayData)
            require(len(matrix)==16 and all(math.isfinite(x) for x in matrix),'Invalid warm transform')
            error=max(abs(a-b) for a,b in zip(matrix,t16(row['T_S_local'])))
            require(error<1e-8 and component.IsFixed(),'Warm fixed transform mismatch')
            actual.append(dict(id=identity,path=str(path),sha256=hashes[key],transform_max_error=error,fixed=True))
        require(len({p['id'] for p in actual})==597,'Duplicate warm component identity')
        return dict(status='PASS_WARM_METADATA_PREFLIGHT_ONLY',component_count=597,components=actual,
                    inspected_document_path=val(model,'GetPathName'),expected_solid_total_from_manifest=978,
                    actual_body_count_measured=False,actual_COM_basis_points_measured=False)

    def integrate(self,state,info,removed,replaced):
        self.report['implementation']=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__),
            base_path=str(Path(base.__file__).resolve()),base_sha256=sha(base.__file__),
            class_name='IntegratorV2',order='WARM_PREFLIGHT_SAVE_EXPORT_RESTORE_FINAL_SAVE_CLOSE_FULL_COLD')
        target=R/'native'/('WP07_ROBOT_'+state.upper()+'.SLDASM')
        work=R/'native/work'/('WP07_WORK_'+state.upper()+'.SLDASM')
        step=R/'native'/('WP07_ROBOT_'+state.upper()+'.step')
        for path in (target,work,step):
            require(not path.exists(),'Existing output protected: '+str(path))
        parent=Path(info['parent_assembly_path'])
        require(sha(parent)==info['parent_assembly_sha256'],'Parent assembly hash changed')
        work.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(parent,work)
        self.checkpoint('parent_copied',state=state,parent=str(parent),work=str(work),sha256=sha(work))
        opened=self.sw.OpenDoc6(str(work),2,193,'',0,0)
        require(isinstance(opened,tuple) and len(opened)==3 and opened[0] is not None and opened[1]==0,
                'Copied assembly open failed')
        model=self.wrap(opened[0],'IModelDoc2');self.activate(model,work)
        assembly=self.wrap(model,'IAssemblyDoc')
        components=assembly.GetComponents(True) or []
        require(len(components)==585,'Parent is not a 585-instance assembly')
        lookup={self.wrap(x,'IComponent2').ComponentReference:self.wrap(x,'IComponent2') for x in components}
        require(len(lookup)==585,'Duplicate parent component identities')
        old_ids=set(removed)|set(replaced)
        require(len(old_ids)==12 and old_ids<=set(lookup),'Incorrect exact-deletion contract')
        model.ClearSelection2(True)
        for identity in sorted(old_ids):
            require(lookup[identity].Select4(True,None,False),'Cannot select exact old instance')
        extension=self.wrap(model.Extension,'IModelDocExtension')
        require(extension.DeleteSelection2(0),'Exact component deletion failed')
        model.ClearSelection2(True)
        remain={self.wrap(x,'IComponent2').ComponentReference for x in assembly.GetComponents(True) or []}
        require(remain==set(lookup)-old_ids and len(remain)==573,'Deletion changed the wrong components')
        self.checkpoint('exact_twelve_removed',state=state,remaining=573)
        rows=info['instances'];new=[r for r in rows if r['id'] not in remain]
        require(len(new)==24,'Expected exactly 24 inserted components')
        for row in new:
            require(max(abs(a-b) for a,b in zip(t16(row['T_S_local']),IDENTITY16))<1e-12,
                    'WP06 global source requires identity transform')
        added=assembly.AddComponents3(
            self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR,[r['native_path'] for r in new]),
            self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8,IDENTITY16*24),
            self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR,['']*24)) or []
        require(len(added)==24,'Incomplete component insertion')
        for raw,row in zip(added,new):
            component=self.wrap(raw,'IComponent2');component.ComponentReference=row['id']
            component.Name2=re.sub(r'[ .()/\\]','_',row['id'])
            require(component.Select4(True,None,False),'Cannot select inserted component')
        assembly.FixComponent();model.ClearSelection2(True)
        props=self.wrap(extension.CustomPropertyManager(''),'ICustomPropertyManager')
        for key,value in dict(WP07_STATE=state,WP07_INSTANCES=597,WP07_STATUS='FIXED_POSE_INTEGRATION_CANDIDATE',
                             WP07_MANIFEST_SHA256=self.report['manifest_sha256'],WP07_MOTION_MODEL='NONE_FIXED_POSES').items():
            props.Add3(key,30,str(value),2)
        model.EditRebuild3();model.ShowNamedView2('',7);model.ViewZoomtofit2();model.GraphicsRedraw2()
        self.report['warm_preflight']=self.warm_preflight(model,rows)
        self.report['native_save']=self.save_new(model,target)
        self.activate(model,target)
        # Export requires resolved geometry. No warm per-body or four-point loop is repeated.
        model.ClearSelection2(True);resolution=assembly.ResolveAllLightweight()
        visibility=[]
        try:
            for raw in assembly.GetComponents(True) or []:
                component=self.wrap(raw,'IComponent2');old_visibility=component.Visible
                if old_visibility!=1:
                    visibility.append((component,old_visibility));component.Visible=1
            model.ClearSelection2(True)
            self.report['step_export']=self.save_new(model,step)
            self.report['step_export'].update(all_components_intended=True,component_count=597,
                resolution_api_return=resolution,changed_visibility_count=len(visibility),
                actual_step_completeness='PENDING_INDEPENDENT_READBACK')
        finally:
            for component,old_visibility in visibility:
                component.Visible=old_visibility
        require(sha(target)==self.report['native_save']['sha256'],'Native assembly changed during neutral export')
        require(normalized(val(model,'GetPathName'))==normalized(target),'Native document path changed after STEP export')
        if val(model,'GetSaveFlag'):
            saved=model.Save3(1,0,0)
            require(isinstance(saved,tuple) and saved[0] and saved[1]==0,'Final display-restored save failed')
            self.report['display_restored_save']=dict(api_return=list(saved),sha256=sha(target))
        final_sha=sha(target)
        self.report['final_native_sha256']=final_sha
        self.close_own_saved(model,target,final_sha)
        self.checkpoint('final_native_saved_closed_before_full_cold',state=state,sha256=final_sha)
        opened=self.sw.OpenDoc6(str(target),2,193,'',0,0)
        require(isinstance(opened,tuple) and len(opened)==3 and opened[0] is not None and opened[1]==0,
                'Final native cold reopen failed')
        cold=self.wrap(opened[0],'IModelDoc2');self.activate(cold,target)
        self.report['cold_open']=dict(errors=opened[1],warnings=opened[2],native_sha256=final_sha,
                                     after_last_native_save=True)
        self.report['cold_inspection']=self.inspect(cold,rows,target)
        require(self.report['cold_inspection']['component_count']==597 and self.report['cold_inspection']['solid_count']==978,
                'Final cold component/body totals differ')
        self.report['cold_inspection_native_sha256']=final_sha
        cold.ShowNamedView2('',7);cold.ViewZoomtofit2();cold.GraphicsRedraw2()
        bmp=R/'results'/('WP07_'+state.upper()+'.bmp')
        self.report['screenshot']=dict(path=str(bmp),saved=bool(cold.SaveBMP(str(bmp),1600,1200)))
        require(sha(target)==final_sha,'Final native bytes changed during cold inspection')
        require(sha(parent)==info['parent_assembly_sha256'],'Parent assembly changed during integration')
        self.report['parent_assembly_unchanged_after']=True
        self.report['left_open_dirty_flag']=bool(val(cold,'GetSaveFlag'))
        self.report['status']='PASS_FIXED_POSE_WP06_INTEGRATION_NATIVE_COLD_CHECK'
        self.checkpoint('whole_state_saved_final_cold_verified_exported',state=state,instances=597,solids=978,
                        final_native_sha256=final_sha,no_native_save_after_cold=True)
        return cold,target,step


def main():
    # base.main resolves this module-global binding when it constructs its builder.
    base.Integrator=IntegratorV2
    require(base.Integrator is IntegratorV2,'V2 class dispatch was not installed')
    base.main()


if __name__=='__main__':
    main()
