from pathlib import Path
import sys,json,re,traceback,importlib.util,argparse
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
FROZEN=R.parent/'wp07_system_20260907_0610/tools/build_retention_native.py'
ADAPTER=R.parent/'wp08_retention_delta_20260907_1228/tools/build_rear_native.py'
s=importlib.util.spec_from_file_location('wp09_frozen_builder',FROZEN)
frozen=importlib.util.module_from_spec(s);s.loader.exec_module(frozen)
require,sha,normalized,val=frozen.require,frozen.sha,frozen.normalized,frozen.val
TEMPLATES,IDENTITY16=frozen.TEMPLATES,frozen.IDENTITY16
bbox_max_error,job_linear_tolerance_mm=frozen.bbox_max_error,frozen.job_linear_tolerance_mm
class ModuleBuilder(frozen.Builder):
    def inspect_assembly(self,model,rows,path):
        result=super().inspect_assembly(model,rows,path)
        result['coordinate_frame']=self.report['coordinate_frame']
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
            for name, value in {'WP09_INSTANCE_ID':row['id'], 'WP09_SOURCE_SHA256':row['source_sha256'],
                                'WP09_COORDINATES':self.report['coordinate_frame'],
                                'WP09_STATUS':'LOCAL_PREFAB_CANDIDATE_NOT_MECHANICAL_RELEASE',
                                'WP09_REPRESENTATION_ROLE':row['representation_role'],
                                'WP09_CONTEXT_ONLY':str(row.get('context_only',False))}.items():
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
            for name,value in {'WP09_STATUS':'LOCAL_PREFAB_FIXED_CANDIDATE_NOT_MECHANICAL_RELEASE',
                               'WP09_COMPONENT_COUNT':len(rows), 'WP09_INPUT_COORDINATES':self.report['coordinate_frame'],
                               'WP09_MATE_MODEL':'NONE_FIXED_IDENTITY'}.items():
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
    ap=argparse.ArgumentParser();ap.add_argument('module',choices=['battery_mount','a3200','mips']);args=ap.parse_args();kind=args.module
    ep=R/'results'/kind/'EMISSION.json';em=json.loads(ep.read_text())
    cp=R/'results'/kind/'CHECK.json';ch=json.loads(cp.read_text())
    require(str(ch.get('status','')).startswith('PASS'),'Independent local check has not passed')
    checked_inputs={normalized(k):v for k,v in ch.get('input_sha256_before',{}).items()}
    require(checked_inputs.get(normalized(ep))==sha(ep),'Independent check is not bound to this emission')
    out=R/'results'/(kind+'_NATIVE.json');require(not out.exists(),'Native receipt protected')
    folder=R/'native'/kind;target=folder/('WP09_'+kind.upper()+'.SLDASM');neutral=folder/'native_roundtrip.step'
    rows=[dict(id=k,step_path=v['path'],source_sha256=v['sha256'],native_path=str(folder/'parts'/(k+'.SLDPRT')),
      expected_solids=1,expected_local_bbox_mm=v['bbox_mm'],representation_role=v['representation_role'],
      context_only=k.startswith('CONTEXT_') or v['representation_role']=='FUNCTIONAL_ENVELOPE')
      for k,v in em['parts'].items()]
    require(len(rows)==em['instances'],'Incomplete emission membership')
    for path in [target,neutral,*[Path(x['native_path']) for x in rows]]:
        require(path.resolve().is_relative_to((R/'native').resolve()) and not path.exists(),'Existing/outside native target')
    pins={str(p):sha(p) for p in [ep,cp,FROZEN,Path(__file__),R/'tools/prepare_native_builder.py',ADAPTER]}
    c=json.loads(Path(em['contract_path']).read_text())
    pins.update(c['source_inputs']);pins[em['contract_path']]=em['contract_sha256'];pins[em['producer_path']]=em['producer_sha256']
    pins.update({r['step_path']:r['source_sha256'] for r in rows})
    require(all(sha(p)==v for p,v in pins.items()),'Input hash mismatch')
    frame=em.get('frame','S_WORLD_MM')+'_IDENTITY'
    report=dict(schema='WP09_NATIVE_LOCAL',status='BUILDING',module=kind,coordinate_frame=frame,
      progress=[],parts=[],save_attempts=[],input_sha256_before=pins,integrated_into_wp08=False,
      actual_equipment_selected=False,pressure_system_designed=False,electrical_complete=False,
      physical_assembly_completed=False,manufacturing_release=False,mate_based_motion_model=False,
      geometry_roundtrip_equivalence_verified=False)
    b=None;prefs=None;command=None
    try:
        import psutil
        ancestors=[dict(pid=p.pid,command=p.cmdline()) for p in psutil.Process().parents() if any(Path(x).name.lower()=='run_guard.py' for x in p.cmdline())]
        require(ancestors,'Guard required');report['outer_guard_processes']=ancestors
        report['guard_scope']='CHILD_PYTHON_JOB_CAPPED;_EXISTING_SOLIDWORKS_SEPARATE_RAM_FLOOR'
        b=ModuleBuilder(out,report)
        allowed={}
        for rp in (R/'results').glob('*_NATIVE.json'):
            if rp==out:continue
            d=json.loads(rp.read_text())
            if d.get('status')!='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY':continue
            a=d['assembly_save'];allowed[normalized(a['path'])]=a['sha256']
            for row in d['parts']:
                a=row['native_save'];allowed[normalized(a['path'])]=a['sha256']
        docs=b.documents();report['documents_before']=[d for _,d in docs]
        for doc,d in docs:
            key=normalized(d['path']) if d['path'] else ''
            require(key in allowed and not d['dirty'] and sha(d['path'])==allowed[key],'Unknown or dirty open document; left untouched')
        for doc,d in docs:b.close_own_saved(doc,Path(d['path']),allowed[normalized(d['path'])])
        require(not b.documents(),'Open docs remain')
        sw=b.sw;sw.Visible=True;sw.UserControl=True;command=sw.CommandInProgress
        prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)},
          strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},
          integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (577,578,579,580)})
        for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k==111)
        for k,name in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(TEMPLATES/name))
        for k,v in {577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
        sw.CommandInProgress=False
        for row in rows:b.import_part(row)
        b.assemble(rows,target,neutral)
        require(all(sha(p)==v for p,v in pins.items()),'Input changed')
        report.update(status='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY',input_sha256_after=pins,
          input_files_unchanged=True,component_count=len(rows))
        b.checkpoint('completed')
    except Exception as exc:
        report.update(status='FAILED',error=str(exc),traceback=traceback.format_exc())
        if b:b.checkpoint('failed')
        else:out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    finally:
        if b:
            try:
                if prefs:
                    for k,v in prefs['toggles'].items():b.sw.SetUserPreferenceToggle(k,v)
                    for k,v in prefs['strings'].items():b.sw.SetUserPreferenceStringValue(k,v)
                    for k,v in prefs['integers'].items():b.sw.SetUserPreferenceIntegerValue(k,v)
                if command is not None:b.sw.CommandInProgress=command
                report['session_preferences_restored']=True
            except Exception as exc:report.update(status='FAILED',session_preferences_restored=False,restore_error=repr(exc))
            b.checkpoint('detached_without_exiting_owned_visible_session')
            if b.initialized:b.pythoncom.CoUninitialize()
if __name__=='__main__':main()

