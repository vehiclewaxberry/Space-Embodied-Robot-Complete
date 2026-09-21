"""WP08 rear rib native local assembly; root-only guarded serial execution.
Only import_part/assemble metadata labels adapt the frozen WP07 methods.
Source-read, units, actual body extrema, save/close/reopen and dependency checks
retain their exercised APIs and numerical tolerances. No whole-star mutation.
"""
from pathlib import Path
import sys,json,re,traceback,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
FROZEN=R.parent/'wp07_system_20260907_0610/tools/build_retention_native.py'
s=importlib.util.spec_from_file_location('wp07_frozen_native_local',FROZEN)
frozen=importlib.util.module_from_spec(s);s.loader.exec_module(frozen)
require,sha,normalized,val=frozen.require,frozen.sha,frozen.normalized,frozen.val
TEMPLATES,IDENTITY16=frozen.TEMPLATES,frozen.IDENTITY16
bbox_max_error,job_linear_tolerance_mm=frozen.bbox_max_error,frozen.job_linear_tolerance_mm
sys.path.insert(0,str(R/'tools'))
import integrate_native_delta as owner
class RearBuilder(frozen.Builder):
    def inspect_assembly(self,model,rows,path):
        result=super().inspect_assembly(model,rows,path)
        result['coordinate_frame']='S_WORLD_MM_IDENTITY'
        return result
    def import_part(self, row):
            self.ram_floor()
            source, target = Path(row['step_path']), Path(row['native_path'])
            require(sha(source) == row['source_sha256'], 'STEP changed before import: '+row['id'])
            importer = self.wrap(self.sw.GetImportFileData(str(source)), 'IImportStepData')
            importer.MapConfigurationData = False
            receipt = dict(id=row['id'], source=str(source), source_sha256=row['source_sha256'], target=str(target),
                           expected_solids=row['expected_solids'], status='IMPORTING', import_stage='CALL_LOADFILE4')
            self.report['parts'].append(receipt)
            self.checkpoint('part_import_started', id=row['id'], source=str(source))
            result = self.sw.LoadFile4(str(source), 'r', importer, 0)
            # This generated wrapper returns the document retval and one in/out error
            # argument. LoadFile4 has no warning output; OpenDoc6 is a different API.
            require(isinstance(result, tuple) and len(result) == 2, 'Unexpected LoadFile4 result shape')
            receipt.update(import_errors=result[1], import_warnings=None,
                           import_warnings_status='NOT_RETURNED_BY_LOADFILE4',
                           import_stage='LOADFILE4_RETURNED', loadfile4_return_arity=2)
            model = self.wrap(result[0], 'IModelDoc2')
            require(model is not None and result[1] == 0 and val(model, 'GetType') == 1, 'STEP import failed or returned a non-part')
            extension = self.wrap(model.Extension, 'IModelDocExtension')
            extension.BreakAllExternalFileReferences2(True)
            facts = self.part_facts(model)
            receipt['facts'] = facts
            require(facts['solid_count'] == row['expected_solids'] and facts['sheet_count'] == 0,
                    'Imported native body count differs: '+row['id'])
            custom = self.wrap(extension.CustomPropertyManager(''), 'ICustomPropertyManager')
            for name, value in {'WP08_INSTANCE_ID':row['id'], 'WP08_SOURCE_SHA256':row['source_sha256'],
                                'WP08_COORDINATES':'S_WORLD_MM_IDENTITY_ASSEMBLY',
                                'WP08_STATUS':'LOCAL_PREFAB_CANDIDATE_NOT_MECHANICAL_RELEASE',
                                'WP08_REPRESENTATION_ROLE':row['representation_role'],
                                'WP08_CONTEXT_ONLY':str(row.get('context_only',False))}.items():
                custom.Add3(name, 30, str(value), 2)
            receipt['external_reference_count'] = model.ListExternalFileReferencesCount2()
            receipt['auxiliary_reference_count'] = model.ListAuxiliaryExternalFileReferencesCount()
            require(receipt['external_reference_count'] == receipt['auxiliary_reference_count'] == 0,
                    'Native part retains an external geometry dependency')
            receipt['import_stage'] = 'SAVING_NEW_NATIVE'
            saved = self.save_new(model, target)
            receipt['native_save'] = saved
            self.close_own_saved(model, target, saved['sha256'])
            opened=self.sw.OpenDoc6(str(target),1,1,'',0,0)
            require(isinstance(opened,tuple) and len(opened)==3,'Unexpected native part cold reopen result')
            require(opened[0] is not None and opened[1]==0,'Native part cold reopen failed')
            cold=self.wrap(opened[0],'IModelDoc2')
            cold_facts=self.part_facts(cold)
            require(cold_facts['solid_count']==row['expected_solids'] and cold_facts['sheet_count']==0,'Cold native part solid count differs')
            bbox_error=bbox_max_error(cold_facts['bounds_mm'],row['expected_local_bbox_mm'])
            require(bbox_error<=job_linear_tolerance_mm(),'Cold native STEP scale/position/bounds differ from actual source: '+row['id'])
            require(cold.ListExternalFileReferencesCount2()==0 and cold.ListAuxiliaryExternalFileReferencesCount()==0,'Cold part still has external geometry links')
            receipt['part_cold_reopen']=dict(errors=opened[1],warnings=opened[2],facts=cold_facts,
                expected_source_bbox_mm=row['expected_local_bbox_mm'],bbox_max_error_mm=bbox_error,
                tolerance_mm=job_linear_tolerance_mm(),source_material_equivalence_verified=False)
            self.close_own_saved(cold,target,saved['sha256'])
            receipt['status'] = 'NATIVE_PART_SAVED_CLOSED_REOPENED_VERIFIED_AND_CLOSED'
            receipt['import_stage'] = 'COMPLETED'
            self.checkpoint('part_completed', id=row['id'], solid_count=facts['solid_count'])

    def assemble(self, rows, target, neutral):
            self.ram_floor()
            model = self.wrap(self.sw.NewDocument(str(TEMPLATES/'gb_assembly.asmdot'),0,0.,0.), 'IModelDoc2')
            require(model is not None and val(model,'GetType') == 2, 'New assembly creation failed')
            assembly = self.wrap(model, 'IAssemblyDoc')
            for start in range(0,len(rows),20):
                batch = rows[start:start+20]
                paths = [p['native_path'] for p in batch]
                matrices = IDENTITY16*len(batch)
                components = assembly.AddComponents3(
                    self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR, paths),
                    self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8, matrices),
                    self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_BSTR, ['']*len(batch))) or []
                require(len(components) == len(batch), 'AddComponents3 did not add every requested part')
                model.ClearSelection2(True)
                for raw,row in zip(components,batch):
                    component = self.wrap(raw,'IComponent2')
                    component.ComponentReference = row['id']
                    component.Name2 = re.sub(r'[ .()/\\]', '_', row['id'])
                    require(component.Select4(True,None,False), 'Could not select inserted component for fixing')
                assembly.FixComponent()
                model.ClearSelection2(True)
                self.checkpoint('components_inserted_fixed_identity', added=min(start+20,len(rows)), total=len(rows))
            props = self.wrap(self.wrap(model.Extension,'IModelDocExtension').CustomPropertyManager(''),'ICustomPropertyManager')
            for name,value in {'WP08_STATUS':'LOCAL_PREFAB_FIXED_CANDIDATE_NOT_MECHANICAL_RELEASE',
                               'WP08_COMPONENT_COUNT':len(rows), 'WP08_INPUT_COORDINATES':'S_WORLD_MM',
                               'WP08_MATE_MODEL':'NONE_FIXED_IDENTITY'}.items():
                props.Add3(name,30,str(value),2)
            self.report['assembly_rebuild_api_return'] = model.EditRebuild3()
            model.ShowNamedView2('',7)
            model.ViewZoomtofit2()
            model.GraphicsRedraw2()
            self.report['warm_assembly_inspection'] = self.inspect_assembly(model,rows,target)
            self.report['assembly_save'] = self.save_new(model,target)
            self.sw.DocumentVisible(True,2)
            active, activation = self.activate(model,target)
            self.report['step_export_activation_errors'] = activation[1] if isinstance(activation,tuple) and len(activation)>1 else None
            self.report['roundtrip_export'] = self.save_new(active,neutral)
            self.report['roundtrip_export'].update(native_sha256=sha(target), active_document_confirmed=True,
                                                  all_selections_cleared=True, geometry_equivalence_not_evaluated=True)
            require(sha(target) == self.report['assembly_save']['sha256'], 'Native assembly changed while exporting STEP')
            self.close_own_saved(model,target,self.report['assembly_save']['sha256'])
            self.checkpoint('assembly_saved_exported_and_closed')
            opened = self.sw.OpenDoc6(str(target),2,1,'',0,0)
            require(isinstance(opened,tuple) and len(opened)==3, 'Unexpected native assembly reopen result')
            self.report['cold_open'] = dict(errors=opened[1],warnings=opened[2])
            cold = self.wrap(opened[0],'IModelDoc2')
            require(cold is not None and opened[1] == 0, 'Actual cold reopen failed')
            self.report['cold_assembly_inspection'] = self.inspect_assembly(cold,rows,target)
            self.activate(cold,target)
            # The warm document saved its isometric view before cold reopening.
            # Avoid post-check view edits that could dirty the final assembly.
            cold.GraphicsRedraw2()
            require(sha(target) == self.report['assembly_save']['sha256'], 'Saved assembly changed during cold inspection')
            self.report['left_open_for_user'] = dict(path=str(target), sha256=sha(target),
                active_document_confirmed=True, display='ISOMETRIC_ZOOM_TO_FIT', current_dirty_flag=bool(val(cold,'GetSaveFlag')))
            self.checkpoint('cold_assembly_verified_left_visible', component_count=len(rows))

def main():
    mp=R/'results/INTEGRATION_MANIFEST.json';manifest=json.loads(mp.read_text())
    ep=R/'results/rear_rib/EMISSION.json';emission=json.loads(ep.read_text())
    cp=R/'results/rear_rib/CHECK.json';checks=json.loads(cp.read_text())
    require(checks.get('status')=='PASS_LOCAL_REAR_RIB_NOMINAL_GEOMETRY_ONLY','Rear local geometric checker must pass its declared scope before native import')
    out=R/'results/REAR_RIB_NATIVE.json';require(not out.exists(),'Native receipt protected')
    folder=R/'native/REAR_RIB_LOCAL';target=folder/'WP08_RIGHT_REAR_RIB.SLDASM';neutral=folder/'native_roundtrip.step'
    rows=[]
    for ident,row in emission['parts'].items():
        rows.append(dict(id=ident,step_path=row['path'],source_sha256=row['sha256'],native_path=str(folder/'parts'/(ident+'.SLDPRT')),
            expected_solids=1,expected_local_bbox_mm=row['bbox_mm'],representation_role=row['representation_role'],context_only=ident.startswith('CONTEXT_')))
    require(len(rows)==11 and sum(r['context_only'] for r in rows)==1,'Local membership differs')
    for path in [target,neutral,*[Path(r['native_path']) for r in rows]]:
        require(path.is_relative_to((R/'native').resolve()) and not path.exists(),'Existing/outside native target')
    pins={str(p):sha(p) for p in (mp,ep,cp,FROZEN,Path(__file__),Path(owner.__file__))}
    pins.update(json.loads(Path(emission['contract_path']).read_text())['source_inputs'])
    pins[emission['producer_path']]=emission['producer_sha256'];pins[emission['contract_path']]=emission['contract_sha256']
    for row in rows:pins[row['step_path']]=row['source_sha256']
    require(all(sha(p)==d for p,d in pins.items()),'Source hash changed')
    report=dict(schema='WP08_REAR_RIB_NATIVE_LOCAL',status='BUILDING',progress=[],parts=[],save_attempts=[],input_sha256_before=pins,
        coordinate_frame='S_WORLD_MM_IDENTITY',candidate_instances=10,context_instances=1,
        integrated_into_wp08_three_state=False,physical_assembly_completed=False,manufacturing_release=False,strength_verified=False,
        continuous_motion_verified=False,mate_based_motion_model=False,geometry_roundtrip_equivalence_verified=False,
        source_adaptation='Only native custom-property namespace/coordinate labels changed in copied frozen import_part/assemble methods; no mechanical PASS inherited')
    builder=None;prefs=None;oldcommand=None
    try:
        owner.reuse.require_outer_guard(report)
        builder=RearBuilder(out,report);require(int(val(builder.sw,'GetProcessID'))==26208,'Existing singleton changed')
        allowed={normalized(r['native_path']):r['native_sha256'] for state in manifest['states'].values() for r in state['instances']}
        for p in (R/'results').glob('NATIVE_*.json'):
            d=json.loads(p.read_text())
            if d.get('status')=='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN':allowed[normalized(d['native_save']['path'])]=d['native_save']['sha256']
        owner.oldbase.Integrator.close_registered(builder,allowed)
        sw=builder.sw;oldcommand=sw.CommandInProgress
        prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)},strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (577,578,579,580)})
        for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k==111)
        for k,name in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(TEMPLATES/name))
        for k,value in {577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,value)
        sw.CommandInProgress=False
        for row in rows:builder.import_part(row)
        builder.assemble(rows,target,neutral)
        require(all(sha(p)==d for p,d in pins.items()),'Source changed during native build')
        report.update(status='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY',input_sha256_after=pins,input_files_unchanged=True,component_count=len(rows))
        builder.checkpoint('completed')
    except Exception as exc:
        report.update(status='FAILED',error=str(exc),traceback=traceback.format_exc())
        if builder:builder.checkpoint('failed')
        else:out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    finally:
        if builder:
            try:
                if prefs:
                    for k,v in prefs['toggles'].items():builder.sw.SetUserPreferenceToggle(k,v)
                    for k,v in prefs['strings'].items():builder.sw.SetUserPreferenceStringValue(k,v)
                    for k,v in prefs['integers'].items():builder.sw.SetUserPreferenceIntegerValue(k,v)
                if oldcommand is not None:builder.sw.CommandInProgress=oldcommand
                report['session_preferences_restored']=True
            except Exception as exc:report.update(status='FAILED',session_preferences_restored=False,restore_error=str(exc))
            builder.checkpoint('detached_without_exiting_existing_session')
            if builder.initialized:builder.pythoncom.CoUninitialize()
if __name__=='__main__':main()
