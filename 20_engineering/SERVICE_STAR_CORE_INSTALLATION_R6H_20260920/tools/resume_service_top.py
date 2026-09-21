"""Resume only the service top assembly that the R6H native run never reached.

The 2026-09-20 run saved and cold-verified all 27 parts and all four groups, then
failed at the final ('service', top_rows, SERVICE_STAR_SERVICE_R6H.SLDASM) entry
with 'Available memory is below the 512 MiB floor'. Nothing about the geometry,
the poses or the horizontal MAIN installation changes here: this only inserts the
fifteen already-verified children at their recorded transforms, fixes them, saves,
and cold-reads the result back.

The original FAILED_CLOSED delivery is never rewritten (handoff red line 1); this
writes a separate receipt so the failure and the resume both stay on record.
"""
from geometry import *
import argparse, gc, sys, traceback

DELIVERY = D / 'results/NATIVE_ASSEMBLY_DELIVERY.json'
RESUME = D / 'results/NATIVE_SERVICE_TOP_RESUME.json'
TOP_NAME = 'SERVICE_STAR_SERVICE_R6H.SLDASM'
R1 = D.parent / 'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'


def locks():
    """Every native file the top assembly will reference, with its recorded digest."""
    plan = read(D / 'inputs/NATIVE_ASSEMBLY_PLAN.json')
    dl = read(DELIVERY)
    rows = list(plan['source_native_files'])
    rows += [dict(path=x['target'], sha256=x['native_save']['sha256']) for x in dl['parts']]
    rows += [x['saved'] for x in dl['groups']]
    return plan, dl, list({str(Path(x['path']).resolve()).lower(): x for x in rows}.values())


def preflight():
    """Fail-closed readiness report; touches SolidWorks only to list open documents."""
    import psutil
    plan, dl, lk = locks()
    target = D / 'native' / TOP_NAME
    drift = [x['path'] for x in lk if sha(x['path']) != x['sha256']]
    missing = [r['id'] for r in plan['top_rows'] if not Path(r['native_path']).exists()]
    available = psutil.virtual_memory().available
    out = dict(
        schema='R6H_SERVICE_TOP_RESUME_PREFLIGHT_V1',
        prior_status=dl['status'], prior_error=dl.get('error'),
        prior_groups_cold_verified=len(dl['groups']),
        prior_service_entry_present='service' in dl,
        target=str(target), target_exists=target.exists(),
        top_rows=len(plan['top_rows']), locked_files=len(lk), locked_files_drifted=drift,
        missing_top_row_files=missing,
        available_bytes=available, available_MiB=round(available / 1024 ** 2),
        ram_floor_MiB=512, ram_floor_ok=available >= 512 * 1024 ** 2,
        expected_leaf_count=plan['expected_leaf_count'],
        expected_solid_instances=plan['expected_solid_instances'],
    )
    out['open_documents'] = []
    out['open_documents_must_be_closed'] = False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        try:
            sys.path.insert(0, str(R1 / 'tools'))
            import native_integrate as ni
            ni.configure_com()
            import win32com.client
            try:
                raw = win32com.client.GetActiveObject('SldWorks.Application')
            except Exception:
                raw = None
            out['solidworks_running'] = raw is not None
            if raw is not None:
                docs = raw.GetDocuments
                docs = docs() if callable(docs) else docs
                names = []
                for d in (list(docs) if docs else []):
                    t = d.GetTitle
                    names.append(t() if callable(t) else t)
                out['open_documents'] = names
                out['open_documents_must_be_closed'] = bool(names)
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        out['solidworks_probe_error'] = '%s: %s' % (type(e).__name__, e)
        out['open_documents_must_be_closed'] = True
    out['ready'] = bool(
        not drift and not missing and not target.exists()
        and out['ram_floor_ok'] and not out.get('open_documents_must_be_closed', True)
    )
    write(D / 'results/SERVICE_TOP_RESUME_PREFLIGHT.json', out)
    keys = ('ready', 'available_MiB', 'ram_floor_ok', 'solidworks_running', 'open_documents',
            'solidworks_probe_error', 'target_exists', 'locked_files', 'locked_files_drifted',
            'missing_top_row_files')
    print(json.dumps({k: out[k] for k in keys if k in out}, ensure_ascii=False), flush=True)
    return out


def run():
    assert not RESUME.exists(), 'Resume receipt already written'
    plan, dl, lk = locks()
    assert dl['status'] == 'FAILED_CLOSED' and 'service' not in dl, 'Unexpected prior delivery state'
    target = D / 'native' / TOP_NAME
    assert not target.exists(), 'Service top already exists'
    rows = plan['top_rows']

    sys.path.insert(0, str(R1 / 'tools'))
    import native_integrate as ni
    ni.OUT = D
    import build_integrated as bi
    bi.OUT = D

    report = dict(
        schema='R6H_SERVICE_TOP_RESUME_V1', status='RUNNING', progress=[], save_attempts=[],
        resumed_from=str(DELIVERY), resumed_from_sha256=sha(DELIVERY),
        resumed_from_status=dl['status'], resumed_from_error=dl.get('error'),
        plan_sha256=sha(D / 'inputs/NATIVE_ASSEMBLY_PLAN.json'),
        coordinate_frame='STEP_WORLD_S_MM_IDENTITY_ONCE',
        geometry_changed=False, poses_changed=False, new_parts=0,
        horizontal_MAIN=True, board_out_of_plane_tilt_deg=0,
        STOP_installed=False, AUX_installed=False, electrical_connections_completed=False,
        whole_design_complete=False, ready_to_power=False, flight_ready=False)

    ni.configure_com()
    b = ni.PrototypeBuilder(RESUME, report)
    sw = b.sw
    prefs = {k: sw.GetUserPreferenceToggle(k) for k in (111, 291, 691)}
    try:
        assert all(sha(x['path']) == x['sha256'] for x in lk), 'Source native file drift'
        report['locked_files'] = len(lk)
        b.checkpoint('source_locks_verified', files=len(lk))
        for k in prefs:
            sw.SetUserPreferenceToggle(k, k == 111)
        sw.DocumentVisible(False, 2)
        sw.CommandInProgress = True
        saved = bi.make(b, rows, target, 'service')
        sw.CommandInProgress = False
        b.checkpoint('service_saved')

        opened = sw.OpenDoc6(str(target), 2, 195, '', 0, 0)
        assert opened[0] is not None and opened[1] == 0, opened
        doc = b.wrap(opened[0], 'IModelDoc2')
        asm = b.wrap(doc, 'IAssemblyDoc')
        lookup = b.identity_inventory(asm, rows)
        checked = []
        for r in rows:
            c = lookup[r['id']]
            assert ni.m.normalized(c.GetPathName()) == ni.m.normalized(r['native_path']), r['id']
            actual = list(b.wrap(c.Transform2, 'IMathTransform').ArrayData)
            err = max(abs(x - y) for x, y in zip(actual, ni.h.t16(r['T_S_local'])))
            assert err < 1e-8 and c.IsFixed(), (r['id'], err)
            checked.append(dict(id=r['id'], native_path=r['native_path'],
                                transform_max_error=err, fixed=True))
        ext = b.wrap(doc.Extension, 'IModelDocExtension')
        report['service'] = dict(
            id='service', saved=saved, cold_errors=opened[1], cold_warnings=opened[2],
            direct_children=len(rows), needs_rebuild2=int(ext.NeedsRebuild2), children=checked)
        b.close_own_saved(doc, target, saved['sha256'])
        lookup = doc = asm = None
        gc.collect()
        b.checkpoint('service_cold_verified')

        report['source_native_files_unchanged'] = all(sha(x['path']) == x['sha256'] for x in lk)
        assert report['source_native_files_unchanged']
        report['status'] = 'PASS_R6H_SERVICE_TOP_RESUMED_AND_COLD_VERIFIED'
        b.checkpoint('complete')
    except Exception as e:
        report.update(status='FAILED_CLOSED', error=str(e), traceback=traceback.format_exc())
        b.checkpoint('failed')
        raise
    finally:
        try:
            for k, v in prefs.items():
                sw.SetUserPreferenceToggle(k, v)
            sw.CommandInProgress = False
            sw.DocumentVisible(True, 1)
            sw.DocumentVisible(True, 2)
        except Exception as cleanup_error:
            report['cleanup_error'] = str(cleanup_error)
            b.checkpoint('cleanup_failed_preserved_original_result')
        b.pythoncom.CoUninitialize()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['preflight', 'run'])
    a = ap.parse_args()
    {'preflight': preflight, 'run': run}[a.mode]()
