"""Build a new, fixed-identity WP06 local assembly in the existing SolidWorks.

Usage: python build_native_local.py job.json
Required job fields: parts[{id,step_path,native_path,expected_solids}],
assembly_path, roundtrip_step, output, expected_existing_document,
expected_existing_sha256. All source STEP geometry is already in world mm.
Optional expected_sw_pid pins the already-running application's process ID.

No empty-session launch, installation, queue polling, ExitApp, invented mates, or
design-source imports. The known local ROT fallback is accepted only if it returns
the exact sole PID observed before attachment. Existing outputs are rejected before
attaching. Only this run's native/
and results/ outputs are written. Unexpected or dirty existing documents are
never closed. The new cold-checked SLDASM remains visible for user inspection.
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
    rows = job['parts']
    require(isinstance(rows, list) and 0 < len(rows) <= 60, 'Expected 1 to 60 local parts')
    require(len({p['id'] for p in rows}) == len(rows), 'Duplicate part IDs')
    require(len({re.sub(r'[ .()/\\]', '_', p['id']) for p in rows}) == len(rows), 'Component name sanitization collision')
    inputs = {str(job_path):sha(job_path), str(Path(__file__).resolve()):sha(__file__)}
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
    recovery = None
    requested = job.get('recover_own_failed_import')
    if requested is not None:
        prior_path = Path(requested['prior_receipt_path']).resolve()
        require(prior_path.is_relative_to((R/'results').resolve()) and prior_path.is_file(),
                'Recovery requires an existing run-local failure receipt')
        require(prior_path != report, 'Recovery must write a new report; the failed receipt is immutable')
        prior_hash = sha(prior_path)
        require(prior_hash == requested['prior_receipt_sha256'], 'Recovery prior-receipt SHA mismatch')
        prior = json.loads(prior_path.read_text(encoding='utf-8-sig'))
        require(prior.get('status') == 'FAILED' and prior.get('parts'), 'Recovery receipt is not a failed import run')
        last = prior['parts'][-1]
        source = Path(requested['source_path']).resolve()
        require(source.is_file() and normalized(last.get('source','')) == normalized(source),
                'Recovery source does not match the latest part in the failed receipt')
        require(not last.get('native_save'), 'Recovery cannot close a previously saved native part')
        require(last.get('status') in ('IMPORTING','IMPORT_FAILED'), 'Failure did not leave an owned import-stage part')
        explicit_failed_stage = last.get('import_stage') == 'FAILED'
        legacy_return_shape_failure = (last.get('status') == 'IMPORTING'
            and prior.get('error') == 'Unexpected LoadFile4 result shape'
            and 'builder.import_part' in prior.get('traceback','') and not prior.get('save_attempts'))
        require(explicit_failed_stage or legacy_return_shape_failure,
                'Receipt does not prove the specific owned failed import stage')
        require(sha(source) == last.get('source_sha256'), 'Recovery source changed after the failed import')
        require(any(normalized(p['step_path']) == normalized(source) for p in checked),
                'Recovery source is not in this new import job')
        backup = None
        if requested.get('backup_path'):
            backup = output_path(requested['backup_path'], '.sldprt', 'native')
            require(normalized(backup) not in {normalized(p) for p in outputs}, 'Recovery backup conflicts with a new output')
            require(normalized(backup) not in {normalized(p) for p in inputs}, 'Recovery backup conflicts with an input')
        recovery = dict(source_path=str(source), source_sha256=sha(source),
            prior_receipt_path=str(prior_path), prior_receipt_sha256=prior_hash,
            prior_sw_pid=prior.get('session',{}).get('sw_pid'),
            owner_stage_proof='EXPLICIT_IMPORT_FAILED' if explicit_failed_stage else 'LEGACY_LOADFILE4_RETURN_SHAPE_FAILURE',
            expected_title=requested.get('title'), backup_path=None if backup is None else str(backup))
        inputs[str(prior_path)] = prior_hash
        inputs[str(source)] = recovery['source_sha256']
    return checked, assembly, neutral, report, previous, inputs, recovery


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

    def recover_failed_import(self, doc, data, recovery, current_pid):
        require(data['document_type'] == 1, 'Owned failed-import recovery requires a part document')
        if recovery.get('prior_sw_pid') is not None:
            require(recovery['prior_sw_pid'] == current_pid, 'Failed import belongs to a different SolidWorks PID')
        require(sha(recovery['prior_receipt_path']) == recovery['prior_receipt_sha256'],
                'Recovery receipt changed before document handling')
        require(sha(recovery['source_path']) == recovery['source_sha256'], 'Recovery source changed before handling')
        if data['path']:
            require(normalized(data['path']) == normalized(recovery['source_path']),
                    'Open document path is not the owned failed-import source')
        else:
            require(bool(recovery.get('expected_title')) and data['title'] == recovery['expected_title'],
                    'Empty-path document title is not explicitly authorized for preserved recovery')
            require(Path(data['title']).stem.casefold() == Path(recovery['source_path']).stem.casefold(),
                    'Empty-path document title does not correspond to the owned import source')
            require(bool(recovery.get('backup_path')),
                    'Empty-path document will remain open: a new recovery backup path is required')
        action = dict(**recovery, document_before=data, preserved_before_close=False)
        self.report['failed_import_recovery'] = action
        self.checkpoint('owned_failed_import_recovery_verified', source=recovery['source_path'], dirty=data['dirty'])
        if recovery.get('backup_path'):
            backup = Path(recovery['backup_path'])
            action['backup_before_save_facts'] = self.part_facts(doc)
            action['backup_save'] = self.save_new(doc, backup)
            action['preserved_before_close'] = True
            # Saving preserves all current contents, including any edits to this
            # failed-import document; closure requires the saved path and clean flag.
            self.close_own_saved(doc, backup, action['backup_save']['sha256'])
            action['closed_path'] = str(backup)
        else:
            # Explicitly authorized old import-stage recovery with a real source
            # path only. Empty-path/title-only documents never reach this branch.
            require(bool(data['path']) and normalized(val(doc,'GetPathName')) == normalized(recovery['source_path']),
                    'Owned source document path changed before recovery close')
            self.sw.CloseDoc(data['title'])
            action['closed_path'] = data['path']
        action['status'] = 'OWNED_FAILED_IMPORT_RECOVERED'
        self.checkpoint('owned_failed_import_recovered', preserved_before_close=action['preserved_before_close'])

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
            if not is_saved_service and recovery is not None:
                self.recover_failed_import(doc,data,recovery,pid)
                continue
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
        result = dict(solid_count=len(bodies), sheet_count=len(sheets), bodies=measured,
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
        for name, value in {'WP06_INSTANCE_ID':row['id'], 'WP06_SOURCE_SHA256':row['source_sha256'],
                            'WP06_COORDINATES':'WORLD_MM_IDENTITY_ASSEMBLY',
                            'WP06_STATUS':'DIGITAL_JOINT_CANDIDATE_NOT_MANUFACTURING_RELEASE'}.items():
            custom.Add3(name, 30, str(value), 2)
        receipt['external_reference_count'] = model.ListExternalFileReferencesCount2()
        receipt['auxiliary_reference_count'] = model.ListAuxiliaryExternalFileReferencesCount()
        require(receipt['external_reference_count'] == receipt['auxiliary_reference_count'] == 0,
                'Native part retains an external geometry dependency')
        receipt['import_stage'] = 'SAVING_NEW_NATIVE'
        saved = self.save_new(model, target)
        receipt['native_save'] = saved
        self.close_own_saved(model, target, saved['sha256'])
        receipt['status'] = 'NATIVE_PART_SAVED_AND_CLOSED'
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
                    'World-coordinate component is not at identity')
            basis_errors = []
            for point_mm in ([0.,0.,0.],[10.,0.,0.],[0.,10.,0.],[0.,0.,10.]):
                point = self.wrap(math_util.CreatePoint(self.VARIANT(self.pythoncom.VT_ARRAY|self.pythoncom.VT_R8,
                                                                   [x/1000 for x in point_mm])), 'IMathPoint')
                result = self.wrap(point.MultiplyTransform(transform), 'IMathPoint')
                basis_errors.append(max(abs(float(x)*1000-y) for x,y in zip(result.ArrayData,point_mm)))
            require(max(basis_errors) <= 1e-5, 'Actual SW transform changed an identity basis point')
            bodies, bodies_info = self.component_bodies(component, 0)
            sheets, sheets_info = self.component_bodies(component, 1)
            doc = self.wrap(component.GetModelDoc2(), 'IModelDoc2')
            require(doc is not None, 'Resolved component has no actual part document')
            facts = self.part_facts(doc)
            require(len(bodies) == facts['solid_count'] == expected['expected_solids'] and not sheets and facts['sheet_count'] == 0,
                    'Actual component body count is wrong: '+identity)
            require(bool(component.IsFixed()), 'Component is not fixed: '+identity)
            require(sha(path) == next(x['native_save']['sha256'] for x in self.report['parts'] if x['id'] == identity),
                    'Native part changed during assembly creation')
            observed.append(dict(id=identity, name=component.Name2, path=str(path), sha256=sha(path),
                transform_sw16=values, fixed=True, resolved_solid_count=len(bodies), resolved_sheet_count=len(sheets),
                bodies_info=bodies_info, sheets_info=sheets_info, model_part_facts=facts,
                world_basis_max_error_mm=max(basis_errors), suppression_state=component.GetSuppression2()))
            bodies = sheets = doc = None
        require(len({p['id'] for p in observed}) == len(rows), 'Duplicate component identity after inspection')
        dependency_data = model.GetDependencies2(False, True, False) or []
        require(len(dependency_data)%2 == 0, 'Malformed dependency name/path array')
        dependencies = [Path(dependency_data[i+1]).resolve() for i in range(0,len(dependency_data),2)]
        require({normalized(p) for p in dependencies} == {normalized(p['native_path']) for p in rows},
                'Assembly dependency set differs from the complete local part set')
        return dict(component_count=len(observed), components=observed,
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
        for name,value in {'WP06_STATUS':'LOCAL_FIXED_DIGITAL_ASSEMBLY_NOT_MANUFACTURING_RELEASE',
                           'WP06_COMPONENT_COUNT':len(rows), 'WP06_INPUT_COORDINATES':'WORLD_MM',
                           'WP06_MATE_MODEL':'NONE_FIXED_IDENTITY'}.items():
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
        cold.ShowNamedView2('',7)
        cold.ViewZoomtofit2()
        cold.GraphicsRedraw2()
        require(sha(target) == self.report['assembly_save']['sha256'], 'Saved assembly changed during cold inspection')
        self.report['left_open_for_user'] = dict(path=str(target), sha256=sha(target),
            active_document_confirmed=True, display='ISOMETRIC_ZOOM_TO_FIT', current_dirty_flag=bool(val(cold,'GetSaveFlag')))
        self.checkpoint('cold_assembly_verified_left_visible', component_count=len(rows))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('job',type=Path)
    args = ap.parse_args(argv)
    job_path = args.job.resolve()
    job = json.loads(job_path.read_text(encoding='utf-8-sig'))
    rows,target,neutral,out,previous,inputs,recovery = preflight(job,job_path)
    out.parent.mkdir(parents=True,exist_ok=True)
    report = dict(schema='WP06_NATIVE_LOCAL_ASSEMBLY_V1',status='BUILDING',progress=[],parts=[],save_attempts=[],
        input_sha256_before=inputs, job_path=str(job_path), output=str(out),
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


if __name__ == '__main__':
    raise SystemExit(main())
