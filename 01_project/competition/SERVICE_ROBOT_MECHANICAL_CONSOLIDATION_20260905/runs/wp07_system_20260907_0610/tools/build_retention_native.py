"""WP07 native LOCAL_MAST_FRAME retention prefabrication candidates, source only.

prepare --station 0 --tag c03_v1 --existing-document SAVED.SLDASM
        --existing-sha256 HASH [--expected-sw-pid PID]
build inputs/retention_native_c03_v1_station0.json

Root exclusively executes build under serialized CAD control. Each job contains
exactly 17 existing C02 STEP pieces plus the original parking saddle context.
All STEP coordinates are already mast-local millimetres; component Transform2
is identity. SW geometric metres are explicitly converted to mm for bbox/basis
checks. All generated native/results/job paths remain within this R7 directory.

Uses the frozen, actually exercised WP06 53-part importer conventions. Never
edits the 597-part whole assembly or WP06. Only an explicitly named, hash-bound,
clean existing assembly can be closed. No generic dirty-document recovery.
Native readability, units and positioning do not prove source transfer material
equivalence, whole-assembly neighbour clearance, continuous motion or release.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import traceback
from pathlib import Path


R = Path(__file__).resolve().parents[1]
TYPELIB = '{83A33D31-27C5-11CE-BFD4-00400513BB57}'
TEMPLATES = Path('C:/ProgramData/SolidWorks/SOLIDWORKS 2024/templates')
IDENTITY16 = [1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.]


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def normalized(path):
    return str(Path(path).resolve()).replace('\\','/').casefold()


def val(obj, name, *args):
    result = getattr(obj, name)
    return result(*args) if callable(result) and not hasattr(result, '_oleobj_') else result


def output_path(path, suffix, domain):
    p = Path(path).resolve()
    require(p.is_relative_to((R/domain).resolve()), 'Output outside permitted '+domain+'/: '+str(p))
    require(p.suffix.casefold() == suffix.casefold(), 'Wrong output extension: '+str(p))
    require(not p.exists(), 'Pre-existing output will not be overwritten: '+str(p))
    return p


def preflight(job, job_path):
    validate_retention_job(job)
    rows = job['parts']
    require(isinstance(rows, list) and len(rows) == 18, 'Expected exactly 18 retention local parts')
    require(len({p['id'] for p in rows}) == len(rows), 'Duplicate part IDs')
    require(len({re.sub(r'[ .()/\\]', '_', p['id']) for p in rows}) == len(rows), 'Component name sanitization collision')
    inputs = {str(job_path):sha(job_path), str(Path(__file__).resolve()):sha(__file__)}
    for path,digest in job['provenance_inputs'].items():
        require(sha(path)==digest,'Frozen retention provenance changed: '+path)
        inputs[str(Path(path).resolve())]=digest
    checked = []
    for row in rows:
        source = Path(row['step_path']).resolve()
        require(source.is_file() and source.suffix.casefold() in ('.step','.stp'), 'Actual source STEP is absent')
        target = output_path(row['native_path'], '.sldprt', 'native')
        require(type(row['expected_solids']) is int and row['expected_solids'] > 0, 'Invalid expected solid count')
        digest = sha(source)
        if row.get('source_sha256'):
            require(digest == row['source_sha256'], 'Source SHA differs from job contract: '+row['id'])
        inputs[str(source)] = digest
        checked.append(dict(row, step_path=str(source), native_path=str(target), source_sha256=digest))
    assembly = output_path(job['assembly_path'], '.sldasm', 'native')
    neutral = output_path(job['roundtrip_step'], '.step', 'native')
    report = output_path(job['output'], '.json', 'results')
    outputs = [Path(p['native_path']) for p in checked]+[assembly, neutral, report]
    require(len(set(normalized(p) for p in outputs)) == len(outputs), 'Duplicate output targets')
    require(not ({normalized(p) for p in outputs} & {normalized(p) for p in inputs}), 'Output aliases an input')
    previous = Path(job['expected_existing_document']).resolve()
    require(previous.is_file() and previous.suffix.casefold() == '.sldasm', 'Expected saved existing assembly is absent')
    require(sha(previous) == job['expected_existing_sha256'], 'Existing service assembly SHA differs from authorization')
    inputs[str(previous)] = job['expected_existing_sha256']
    for template in ('gb_part.prtdot','gb_assembly.asmdot','gb_a4.drwdot'):
        require((TEMPLATES/template).is_file(), 'Installed SolidWorks template missing: '+template)
    require(job.get('recover_own_failed_import') is None,
            'Retention builder never recovers or closes an unsaved failed-import document')
    return checked, assembly, neutral, report, previous, inputs, None


class Builder:
    def __init__(self, report_path, report):
        # Imports happen only in execution. A singleton must exist before any dispatch.
        import pythoncom
        import psutil
        import win32com.client
        from win32com.client import gencache, VARIANT
        self.pythoncom, self.psutil, self.VARIANT = pythoncom, psutil, VARIANT
        self.report_path, self.report = report_path, report
        self.sw = None
        self.initialized = False
        pythoncom.CoInitialize()
        self.initialized = True
        self.types = gencache.GetModuleForTypelib(TYPELIB, 0, 32, 0)
        require(self.types is not None, 'Existing generated SolidWorks 2024 wrappers are unavailable')
        existing = [p.info['pid'] for p in psutil.process_iter(['pid','name'])
                    if (p.info.get('name') or '').casefold() == 'sldworks.exe']
        require(len(existing) == 1, 'Exactly one pre-existing SolidWorks PID is required before attachment')
        self.report['attachment_attempt'] = dict(existing_pids=existing, route='ROT')
        try:
            active = win32com.client.GetActiveObject('SldWorks.Application')
        except Exception as exc:
            self.report['attachment_attempt'].update(route='EXISTING_SINGLETON_DISPATCHEX_WITH_PID_PROOF',
                                                     rot_error=repr(exc))
            # This host's verified singleton path is used only after finding one
            # existing PID; an unexpected returned PID fails before document work.
            active = win32com.client.DispatchEx('SldWorks.Application')
        self.sw = self.wrap(active, 'ISldWorks')
        returned_pid = int(val(self.sw, 'GetProcessID'))
        now = [p.info['pid'] for p in psutil.process_iter(['pid','name'])
               if (p.info.get('name') or '').casefold() == 'sldworks.exe']
        self.report['attachment_attempt'].update(returned_pid=returned_pid, pids_after_attachment=now)
        require(returned_pid == existing[0] and set(now) == set(existing),
                'Attachment did not return the exact existing singleton; no document operation is permitted')

    def wrap(self, obj, name):
        if obj is None:
            return None
        cls = getattr(self.types, name)
        return cls(obj._oleobj_.QueryInterface(cls.CLSID, self.pythoncom.IID_IDispatch))

    def checkpoint(self, stage, **fields):
        event = dict(stage=stage, utc=dt.datetime.now(dt.timezone.utc).isoformat(), **fields)
        self.report['progress'].append(event)
        temp = self.report_path.with_name(self.report_path.name+'.tmp')
        temp.write_text(json.dumps(self.report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temp, self.report_path)
        print(json.dumps(event, ensure_ascii=False, allow_nan=False), flush=True)

    def ram_floor(self):
        require(self.psutil.virtual_memory().available >= 512*1024**2, 'Available memory is below the 512 MiB floor')

    def documents(self):
        raw = val(self.sw, 'GetDocuments')
        objects = [] if raw is None else list(raw)
        docs = []
        for item in objects:
            doc = self.wrap(item, 'IModelDoc2')
            docs.append((doc, dict(title=val(doc, 'GetTitle'), path=val(doc, 'GetPathName'),
                                   document_type=val(doc, 'GetType'), dirty=bool(val(doc, 'GetSaveFlag')))))
        return docs

    def attach_and_close_expected(self, job, previous, recovery=None):
        processes = [p.info for p in self.psutil.process_iter(['pid','name'])
                     if (p.info.get('name') or '').casefold() == 'sldworks.exe']
        pid = int(val(self.sw, 'GetProcessID'))
        revision = str(val(self.sw, 'RevisionNumber'))
        require(len(processes) == 1 and processes[0]['pid'] == pid, 'SolidWorks process is not the unique existing instance')
        require(revision.split('.')[:2] == ['32','5'], 'Expected existing SolidWorks 32.5, got '+revision)
        if job.get('expected_sw_pid') is not None:
            require(pid == job['expected_sw_pid'], 'Existing SolidWorks PID differs from job contract')
        documents = self.documents()
        self.report['session'] = dict(mode='ATTACHED_EXISTING_ONLY', sw_pid=pid, revision=revision,
                                      documents_before=[d for _,d in documents])
        self.checkpoint('session_inspected')
        require(len(documents) <= 1, 'Unexpected additional open documents; none will be closed')
        for doc, data in documents:
            is_saved_service = bool(data['path']) and normalized(data['path']) == normalized(previous)
            require(is_saved_service, 'Unexpected open document; it will not be closed')
            require(data['document_type'] == 2 and data['dirty'] is False,
                    'Expected service assembly is dirty or not an assembly; it will not be closed')
            require(sha(previous) == job['expected_existing_sha256'], 'Existing document changed before authorized close')
            # Re-read its flag immediately before closing only this exact saved document.
            require(not val(doc, 'GetSaveFlag'), 'Expected service document became dirty; not closing')
            self.sw.CloseDoc(data['title'])
            self.checkpoint('closed_expected_saved_service', path=str(previous), sha256=sha(previous))
        require(not self.documents(), 'Unexpected documents remain; local build will not proceed')
        self.sw.Visible = True
        self.sw.UserControl = True

    def part_facts(self, model):
        # Official GetUnits returns [LengthUnit,...]; swLengthUnit_e.swMM=0.
        # https://help.solidworks.com/2024/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swLengthUnit_e.html
        units=list(val(model,'GetUnits'))
        require(bool(units) and int(units[0])==0,'Native document length unit must be swMM=0')
        part = self.wrap(model, 'IPartDoc')
        bodies = part.GetBodies2(0, False) or []
        sheets = part.GetBodies2(1, False) or []
        measured = []
        for raw in bodies:
            body = self.wrap(raw, 'IBody2')
            mass = body.GetMassProperties(1.0)
            box = [[],[]]
            for axis in range(3):
                for side, sign in enumerate((-1,1)):
                    direction = [0.,0.,0.]
                    direction[axis] = sign
                    extreme = body.GetExtremePoint(*direction)
                    require(extreme[0] is True, 'Actual body extreme point query failed')
                    box[side].append(float(extreme[axis+1])*1000)
            measured.append(dict(volume_mm3=float(mass[3])*1e9, bounds_mm=box,
                                 face_count=val(body, 'GetFaceCount')))
        result = dict(document_units_raw=units,document_length_unit='mm',geometric_COM_length_unit='m',solid_count=len(bodies), sheet_count=len(sheets), bodies=measured,
                      volume_mm3=math.fsum(x['volume_mm3'] for x in measured), bounds_mm=None)
        if measured:
            result['bounds_mm'] = [[min(x['bounds_mm'][0][i] for x in measured) for i in range(3)],
                                   [max(x['bounds_mm'][1][i] for x in measured) for i in range(3)]]
        return result

    def save_new(self, model, path):
        require(not path.exists(), 'Refusing to overwrite an existing native/neutral file: '+str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        extension = self.wrap(model.Extension, 'IModelDocExtension')
        result = extension.SaveAs(str(path), 0, 1, None, 0, 0)
        receipt = dict(path=str(path), api_return=list(result) if isinstance(result, tuple) else repr(result))
        if isinstance(result, tuple) and len(result) >= 3:
            receipt.update(ok=bool(result[0]), errors=result[1], warnings=result[2])
        self.report['save_attempts'].append(receipt)
        self.checkpoint('save_attempt', **receipt)
        require(isinstance(result, tuple) and result[0] is True and result[1] == 0,
                'SolidWorks SaveAs failed: '+repr(result))
        require(path.is_file() and path.stat().st_size > 0, 'SaveAs did not produce a nonempty file')
        receipt.update(sha256=sha(path), bytes=path.stat().st_size)
        return receipt

    def close_own_saved(self, model, path, digest):
        require(normalized(val(model, 'GetPathName')) == normalized(path), 'Own document path differs before close')
        require(not val(model, 'GetSaveFlag'), 'Own newly saved document became dirty; leaving it open')
        require(sha(path) == digest, 'Own saved document SHA changed before close')
        self.sw.CloseDoc(val(model, 'GetTitle'))

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
        for name, value in {'WP07_INSTANCE_ID':row['id'], 'WP07_SOURCE_SHA256':row['source_sha256'],
                            'WP07_COORDINATES':'LOCAL_MAST_MM_IDENTITY_ASSEMBLY',
                            'WP07_STATUS':'LOCAL_PREFAB_CANDIDATE_NOT_MECHANICAL_RELEASE',
                            'WP07_REPRESENTATION_ROLE':row['representation_role'],
                            'WP07_CONTEXT_ONLY':str(row.get('context_only',False))}.items():
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

    def activate(self, model, expected_path):
        self.sw.CommandInProgress = False
        result = self.sw.ActivateDoc3(val(model, 'GetTitle'), False, 0, 0)
        require(isinstance(result,tuple) and len(result)==2 and result[0] is not None and result[1]==0,
                'Actual ActivateDoc3 returned an error or unexpected result contract')
        active = self.wrap(val(self.sw, 'ActiveDoc'), 'IModelDoc2')
        require(active is not None and normalized(val(active, 'GetPathName')) == normalized(expected_path),
                'Target native assembly is not the active document')
        active.ClearSelection2(True)
        return active, result

    def component_bodies(self, component, body_type):
        raw = component.GetBodies3(body_type)
        # Generated wrapper returns (retval: bodies array, out: BodiesInfo array).
        # len(raw) == 2 is NOT the body count, even for one actual body.
        require(isinstance(raw, tuple) and len(raw) == 2, 'Unexpected GetBodies3 return contract')
        bodies, info = raw
        require(bodies is None or isinstance(bodies, (tuple,list)), 'GetBodies3 bodies are not an array')
        require(info is None or isinstance(info, (tuple,list)), 'GetBodies3 BodiesInfo is not an array')
        bodies = [] if bodies is None else list(bodies)
        metadata = [] if info is None else list(info)
        require(not metadata or len(metadata) == len(bodies), 'GetBodies3 metadata/body array lengths differ')
        return bodies, metadata

    def inspect_assembly(self, model, rows, assembly_path):
        assembly_units=list(val(model,'GetUnits'))
        require(bool(assembly_units) and int(assembly_units[0])==0,'Assembly document length unit must be swMM=0')
        assembly = self.wrap(model, 'IAssemblyDoc')
        resolution_result = assembly.ResolveAllLightweight()
        raw_components = assembly.GetComponents(True) or []
        require(len(raw_components) == len(rows), 'Assembly component count differs from local job')
        registry = {p['id']:p for p in rows}
        math_util = self.wrap(self.sw.GetMathUtility(), 'IMathUtility')
        observed = []
        for raw in raw_components:
            self.ram_floor()
            component = self.wrap(raw, 'IComponent2')
            identity = component.ComponentReference
            require(identity in registry, 'Unregistered assembly component: '+str(identity))
            expected = registry[identity]
            path = Path(val(component, 'GetPathName')).resolve()
            require(path == Path(expected['native_path']).resolve(), 'Component native dependency path mismatch')
            if component.GetSuppression2() != 2:
                component.SetSuppression2(2)
            require(component.GetSuppression2() == 2, 'Component could not be resolved')
            transform = self.wrap(component.Transform2, 'IMathTransform')
            values = [float(x) for x in transform.ArrayData]
            require(len(values) == 16 and max(abs(x-y) for x,y in zip(values,IDENTITY16)) <= 1e-8,
                    'Mast-local component is not at identity')
            basis_errors = []
            basis_points_mm=[]
            for point_mm in ([0.,0.,0.],[10.,0.,0.],[0.,10.,0.],[0.,0.,10.]):
                point = self.wrap(math_util.CreatePoint(self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8,
                                                                   [x/1000 for x in point_mm])), 'IMathPoint')
                result = self.wrap(point.MultiplyTransform(transform), 'IMathPoint')
                measured_point=[float(x)*1000 for x in result.ArrayData]
                basis_points_mm.append(measured_point)
                basis_errors.append(max(abs(x-y) for x,y in zip(measured_point,point_mm)))
            require(max(basis_errors) <= 1e-5, 'Actual SW transform changed an identity basis point')
            bodies, bodies_info = self.component_bodies(component, 0)
            sheets, sheets_info = self.component_bodies(component, 1)
            doc = self.wrap(component.GetModelDoc2(), 'IModelDoc2')
            require(doc is not None, 'Resolved component has no actual part document')
            facts = self.part_facts(doc)
            require(len(bodies) == facts['solid_count'] == expected['expected_solids'] and not sheets and facts['sheet_count'] == 0,
                    'Actual component body count is wrong: '+identity)
            bbox_error=bbox_max_error(facts['bounds_mm'],expected['expected_local_bbox_mm'])
            require(bbox_error<=job_linear_tolerance_mm(),'Cold component geometry scale/position mismatch: '+identity)
            require(bool(component.IsFixed()), 'Component is not fixed: '+identity)
            require(sha(path) == next(x['native_save']['sha256'] for x in self.report['parts'] if x['id'] == identity),
                    'Native part changed during assembly creation')
            observed.append(dict(id=identity, name=component.Name2, path=str(path), sha256=sha(path),
                transform_sw16=values, fixed=True, resolved_solid_count=len(bodies), resolved_sheet_count=len(sheets),
                bodies_info=bodies_info, sheets_info=sheets_info, model_part_facts=facts,
                world_basis_points_mm=basis_points_mm,world_basis_max_error_mm=max(basis_errors),local_bbox_max_error_mm=bbox_error,suppression_state=component.GetSuppression2()))
            bodies = sheets = doc = None
        require(len({p['id'] for p in observed}) == len(rows), 'Duplicate component identity after inspection')
        dependency_data = model.GetDependencies2(False, True, False) or []
        require(len(dependency_data)%2 == 0, 'Malformed dependency name/path array')
        dependencies = [Path(dependency_data[i+1]).resolve() for i in range(0,len(dependency_data),2)]
        require({normalized(p) for p in dependencies} == {normalized(p['native_path']) for p in rows},
                'Assembly dependency set differs from the complete local part set')
        return dict(component_count=len(observed), components=observed,document_units_raw=assembly_units,coordinate_frame='LOCAL_MAST_MM_IDENTITY',
            resolved_solid_total=sum(p['resolved_solid_count'] for p in observed),
            dependencies=[dict(path=str(p), sha256=sha(p)) for p in dependencies],
            resolution_api_return=resolution_result, assembly_path=str(assembly_path),
            mate_based_motion_model=False, all_components_fixed_at_identity=True)

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
        for name,value in {'WP07_STATUS':'LOCAL_PREFAB_FIXED_CANDIDATE_NOT_MECHANICAL_RELEASE',
                           'WP07_COMPONENT_COUNT':len(rows), 'WP07_INPUT_COORDINATES':'LOCAL_MAST_MM',
                           'WP07_MATE_MODEL':'NONE_FIXED_IDENTITY'}.items():
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


def execute_native(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('job',type=Path)
    args = ap.parse_args(argv)
    job_path = args.job.resolve()
    job = json.loads(job_path.read_text(encoding='utf-8-sig'))
    rows,target,neutral,out,previous,inputs,recovery = preflight(job,job_path)
    out.parent.mkdir(parents=True,exist_ok=True)
    report = dict(schema='WP07_RETENTION_NATIVE_LOCAL_ASSEMBLY_V1',status='BUILDING',progress=[],parts=[],save_attempts=[],
        input_sha256_before=inputs, job_path=str(job_path), output=str(out),
        station_index=job['station_index'],coordinate_frame='LOCAL_MAST_MM',candidate_instances=17,context_instances=1,
        mechanical_evidence=job['mechanical_evidence'],engineering_status='CANDIDATE_NO_MECHANICAL_RELEASE_CREDIT',
        reused_importer_source=job['reused_importer_source'],
        physical_assembly_completed=False, manufacturing_release=False, strength_verified=False,
        continuous_motion_verified=False, mate_based_motion_model=False, geometry_roundtrip_equivalence_verified=False)
    # Claim only a new report path. Subsequent checkpoints replace our own file.
    with out.open('x',encoding='utf-8') as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    builder, old_command, prefs = None, None, None
    try:
        builder = Builder(out,report)
        builder.attach_and_close_expected(job,previous,recovery)
        sw = builder.sw
        old_command = sw.CommandInProgress
        prefs = dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)},
                     strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},
                     integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (577,578,579,580)})
        for k in prefs['toggles']:
            sw.SetUserPreferenceToggle(k,k == 111)
        for k,name in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):
            sw.SetUserPreferenceStringValue(k,str(TEMPLATES/name))
        for k,value in {577:0,578:1,579:2,580:0}.items():
            sw.SetUserPreferenceIntegerValue(k,value)
        sw.CommandInProgress = False
        for row in rows:
            builder.import_part(row)
        builder.assemble(rows,target,neutral)
        after = {p:sha(p) for p in inputs}
        require(after == inputs, 'Original inputs changed during local native assembly production')
        report.update(status='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY', input_sha256_after=after,
                      input_files_unchanged=True, component_count=len(rows))
        builder.checkpoint('completed')
    except Exception as exc:
        if report['parts'] and report['parts'][-1].get('status')=='IMPORTING' and not report['parts'][-1].get('native_save'):
            last=report['parts'][-1]
            last.update(status='IMPORT_FAILED', failed_during_import_stage=last.get('import_stage'),
                        import_stage='FAILED', import_error_message=str(exc))
        report.update(status='FAILED', error=str(exc), exception_type=type(exc).__name__, traceback=traceback.format_exc())
        if builder is not None:
            builder.checkpoint('failed',error=str(exc))
        else:
            out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        if builder is not None:
            try:
                if prefs is not None:
                    for k,value in prefs['toggles'].items():builder.sw.SetUserPreferenceToggle(k,value)
                    for k,value in prefs['strings'].items():builder.sw.SetUserPreferenceStringValue(k,value)
                    for k,value in prefs['integers'].items():builder.sw.SetUserPreferenceIntegerValue(k,value)
                if old_command is not None:builder.sw.CommandInProgress=old_command
                report['session_preferences_restored'] = True
            except Exception as exc:
                report.update(status='FAILED', restore_error=str(exc), session_preferences_restored=False)
            # Never ExitApp or broadly CloseDoc; the user's visible session remains.
            builder.checkpoint('detaching_existing_application')
            builder.sw = None
            if builder.initialized:builder.pythoncom.CoUninitialize()
    return 0 if report['status']=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY' else 1


def job_linear_tolerance_mm():
    return 1e-4


def bbox_max_error(actual, expected):
    require(actual is not None and len(actual)==2, 'Native material bbox is absent')
    target=[expected['min_mm'],expected['max_mm']]
    values=[abs(float(actual[j][i])-float(target[j][i])) for j in range(2) for i in range(3)]
    require(all(math.isfinite(x) for x in values),'Nonfinite source/native bounds')
    return max(values)


def retention_sources(station):
    """Pure-read registry; no COM/CAD, no source STEP reinterpretation."""
    require(station in (0,1),'Unknown retention station')
    receipt=R/f'results/retention_detail/station_{station}/EMISSION_RECEIPT.json'
    require(receipt.is_file(),'Generate and retain the station C02 STEP receipt first')
    emission=json.loads(receipt.read_text(encoding='utf-8-sig'))
    require(emission['station_index']==station and len(emission['parts'])==17,'Expected matching 17-piece C02 emission')
    contract_path=Path(emission['contract_path']).resolve()
    require(sha(contract_path)==emission['contract_sha256'],'Geometry contract changed since STEP emission')
    require(sha(emission['producer_path'])==emission['producer_sha256'],'Geometry producer changed since STEP emission')
    contract=json.loads(contract_path.read_text(encoding='utf-8-sig'))
    require(contract['schema']=='WP07_RETENTION_GUIDE_END_DESIGN_V2','Only the reviewed removable-collar geometry is accepted')
    provenance={str(receipt.resolve()):sha(receipt),str(contract_path):sha(contract_path),
                str(Path(emission['producer_path']).resolve()):emission['producer_sha256']}
    provenance.update(contract['source_inputs'])
    registry={}
    for name,row in emission['parts'].items():
        require(sha(row['path'])==row['sha256'],'Generated STEP changed: '+name)
        registry[name]=dict(id=name,step_path=str(Path(row['path']).resolve()),source_sha256=row['sha256'],expected_solids=1,
            expected_local_bbox_mm=row['local_bbox_mm'],representation_role=row['representation_role'],context_only=False,
            source_kind=row['kind'])
    state=contract['stations'][str(station)]['states']['parking']
    source=state['sources'][f'hold_saddle_{station}']
    T=state['T_S_mast']
    require(source['T_S_local']==T,'Original saddle is not in the shared mast-local frame')
    require(max(abs(T[i][j]-(1 if i==j else 0)) for i in range(3) for j in range(3))<=1e-12,
            'Parking context bbox conversion requires the actual identity rotation')
    require(sha(source['path'])==source['sha256'],'Parking saddle source changed')
    # Frozen metadata bounds are in spacecraft S; parking rotation is identity.
    # Subtract only its actual translation to obtain original STEP local bounds.
    bounds={key:[source['bounds_mm'][key][i]-T[i][3] for i in range(3)] for key in ('min_mm','max_mm')}
    name=f'CONTEXT_PARKING_hold_saddle_{station}'
    registry[name]=dict(id=name,step_path=str(Path(source['path']).resolve()),source_sha256=source['sha256'],expected_solids=1,
        expected_local_bbox_mm=bounds,representation_role='PHYSICAL_GEOMETRY',context_only=True,
        source_kind='ORIGINAL_PARKING_SADDLE_CONTEXT_NOT_REDESIGNED')
    require(len(registry)==18,'Native local registry must contain exactly18 unique instances')
    for row in registry.values():provenance[row['step_path']]=row['source_sha256']
    old=R.parent/'wp06_side_joint_20260907_0233/tools/build_native_local.py'
    old_sha='dcf5fb6e7f23d753d396e4675de06b9b5b792874dc43a5d075e6b2f4e1409c42'
    require(sha(old)==old_sha,'Previously verified WP06 importer source changed')
    prior=R.parent/'wp06_side_joint_20260907_0233/results/NATIVE_EXECUTION_V2.json'
    history=json.loads(prior.read_text(encoding='utf-8-sig'))
    require(history['status']=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY' and history['component_count']==53,
            'Prior 53-part importer execution evidence is not the expected result')
    provenance[str(old.resolve())]=old_sha;provenance[str(prior.resolve())]=sha(prior)
    for path,digest in provenance.items():require(sha(path)==digest,'Frozen input mismatch: '+path)
    reuse=dict(source_path=str(old.resolve()),source_sha256=old_sha,execution_receipt_path=str(prior.resolve()),
               execution_receipt_sha256=sha(prior),basis='COM conventions reused; no geometry PASS inherited')
    return registry,provenance,reuse


def mechanical_evidence(station,registry,source_provenance):
    """Record final evidence if available; missing/running checks grant no credit."""
    observed={};provenance={}
    for mode in ('local','neighbours_parking','neighbours_service','neighbours_released'):
        path=R/f'results/retention_detail_c03/station_{station}/CHECK_{mode}.json'
        if not path.is_file():
            observed[mode]=dict(status='NOT_RUN_OR_NOT_PRESENT',path=str(path));continue
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        status=data.get('status','UNKNOWN')
        if status not in ('PASS','FAIL','INCOMPLETE'):
            observed[mode]=dict(status='NOT_FINAL',observed_status=status,path=str(path));continue
        bindings={normalized(key):value for key,value in data.get('input_sha256',{}).items()}
        required={row['step_path']:row['source_sha256'] for row in registry.values()}
        required.update({key:value for key,value in source_provenance.items() if Path(key).name in
                         ('EMISSION_RECEIPT.json','RETENTION_DESIGN_CONTRACT.json','retention_detail.py')})
        missing=[key for key,value in required.items() if bindings.get(normalized(key))!=value]
        observed[mode]=dict(status=status if not missing else 'STALE_OR_MISSING_INPUT_BINDING',
            observed_status=status,path=str(path),sha256=sha(path),scope_status=data.get('scope_status'),counts=data.get('counts'),
            binding_missing_or_different=missing)
        provenance[str(path.resolve())]=sha(path)
    return dict(checks=observed,assembly_representation='LOCAL_STATIC_PREFABRICATION_CANDIDATE',
                all_mechanical_design_complete=False,physical_assembly_complete=False,
                note='Even local/neighbour PASS would not qualify true threads, loads, fixtures or complete retention motion.'),provenance


def destination(station,tag):
    require(re.fullmatch(r'[a-z][a-z0-9_]{0,15}',tag) is not None,'Tag must be1..16 lowercase identifier characters')
    return R/'native'/f'RET_S{station}_{tag}'


def validate_retention_job(job):
    require(job.get('schema')=='WP07_RETENTION_NATIVE_JOB_V1','Wrong native retention job schema')
    station=int(job['station_index']);tag=job['tag'];root=destination(station,tag)
    require(job['builder_source_sha256']==sha(__file__),'Native builder changed after job preparation')
    registry,provenance,reuse=retention_sources(station)
    require(len(job['parts'])==18 and {p['id'] for p in job['parts']}==set(registry),'Unregistered/missing/duplicate local instances')
    for row in job['parts']:
        expected=registry[row['id']]
        for key,value in expected.items():require(row.get(key)==value,'Local source registry differs for '+row['id']+': '+key)
        require(normalized(row['native_path'])==normalized(root/'parts'/(row['id']+'.SLDPRT')),'Unregistered native output path')
    require(normalized(job['assembly_path'])==normalized(root/f'WP07_RETENTION_S{station}_LOCAL_CANDIDATE.SLDASM'),'Unregistered assembly path')
    require(normalized(job['roundtrip_step'])==normalized(root/'local_assembly_roundtrip.step'),'Unregistered neutral output path')
    require(normalized(job['output'])==normalized(R/'results'/f'RETENTION_NATIVE_S{station}_{tag}.json'),'Unregistered native receipt path')
    require(all(job['provenance_inputs'].get(path)==digest for path,digest in provenance.items()),'Native job omitted frozen source provenance')
    require(job['reused_importer_source']==reuse,'Importer provenance changed')
    require(job.get('recover_own_failed_import') is None,'No generic dirty-document recovery in this builder')


def prepare_job(args):
    registry,provenance,reuse=retention_sources(args.station)
    evidence,evidence_inputs=mechanical_evidence(args.station,registry,provenance);provenance.update(evidence_inputs)
    previous=args.existing_document.resolve()
    require(previous.is_file() and previous.suffix.casefold()=='.sldasm','Explicit saved existing assembly path required')
    require(sha(previous)==args.existing_sha256,'Explicit existing assembly SHA mismatch')
    root=destination(args.station,args.tag)
    job=dict(schema='WP07_RETENTION_NATIVE_JOB_V1',station_index=args.station,tag=args.tag,
             builder_source_sha256=sha(__file__),coordinate_frame='LOCAL_MAST_MM_IDENTITY',
             parts=[dict(row,native_path=str(root/'parts'/(name+'.SLDPRT'))) for name,row in sorted(registry.items())],
             assembly_path=str(root/f'WP07_RETENTION_S{args.station}_LOCAL_CANDIDATE.SLDASM'),
             roundtrip_step=str(root/'local_assembly_roundtrip.step'),
             output=str(R/'results'/f'RETENTION_NATIVE_S{args.station}_{args.tag}.json'),
             expected_existing_document=str(previous),expected_existing_sha256=args.existing_sha256,
             provenance_inputs=provenance,reused_importer_source=reuse,mechanical_evidence=evidence)
    if args.expected_sw_pid is not None:job['expected_sw_pid']=args.expected_sw_pid
    path=R/'inputs'/f'retention_native_{args.tag}_station{args.station}.json'
    require(not path.exists(),'Existing native job is immutable; choose a new tag')
    validate_retention_job(job)
    for output in [*[p['native_path'] for p in job['parts']],job['assembly_path'],job['roundtrip_step'],job['output']]:
        require(not Path(output).exists(),'Native output already exists; choose a new tag')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(job,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(job_path=str(path),job_sha256=sha(path),part_count=18,COM_accessed=False),ensure_ascii=False))
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    prepare=sub.add_parser('prepare',help='Pure-read inputs; write only a new R7 job JSON, no COM')
    prepare.add_argument('--station',type=int,choices=(0,1),required=True)
    prepare.add_argument('--tag',required=True)
    prepare.add_argument('--existing-document',type=Path,required=True)
    prepare.add_argument('--existing-sha256',required=True)
    prepare.add_argument('--expected-sw-pid',type=int)
    build=sub.add_parser('build',help='Root-only serialized existing-session COM execution')
    build.add_argument('job',type=Path)
    args=parser.parse_args(argv)
    if args.command=='prepare':return prepare_job(args)
    return execute_native([str(args.job)])

if __name__ == '__main__':
    raise SystemExit(main())
