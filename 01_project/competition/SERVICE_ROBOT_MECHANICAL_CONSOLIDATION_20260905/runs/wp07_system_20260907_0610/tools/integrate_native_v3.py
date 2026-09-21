"""WP07 V3: componentwise cold inspection and explicit native-only delivery.

Run parking/released with --skip-neutral-export under run_guard.py. In that mode
there is no ResolveAllLightweight call and no full STEP export. Existing SERVICE
recovery evidence is preferred over its immutable interrupted receipt. V2 remains
unchanged and is used only for explicitly requested, resource-gated neutral export.
"""
from pathlib import Path
import argparse
import gc
import re
import shutil
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import integrate_native_v2 as v2
import resume_service as recovery
from integrate_native import R, require, sha, normalized, val, t16, IDENTITY16


class IntegratorV3(recovery.ComponentwiseIntegrator, v2.IntegratorV2):
    skip_neutral_export = True

    def inspect(self, model, rows, expected_path):
        return recovery.ComponentwiseIntegrator.inspect(self, model, rows, expected_path)

    def integrate(self, state, info, removed, replaced):
        if not self.skip_neutral_export:
            require(self.psutil.virtual_memory().available >= 3072*1024**2,
                    'Explicit full native STEP export needs this attempt\'s declared 3072 MiB available-memory headroom')
            return v2.IntegratorV2.integrate(self, state, info, removed, replaced)
        self.report['implementation'] = dict(path=str(Path(__file__).resolve()), sha256=sha(__file__),
            superclass='IntegratorV2', inspector='ComponentwiseIntegrator',
            order='WARM_METADATA_SAVE_CLOSE_READONLY_COMPONENTWISE_COLD', neutral_export=False)
        target = R/'native'/('WP07_ROBOT_'+state.upper()+'.SLDASM')
        work = R/'native/work'/('WP07_WORK_'+state.upper()+'.SLDASM')
        for path in (target, work):
            require(not path.exists(), 'Existing output protected: '+str(path))
        parent = Path(info['parent_assembly_path'])
        require(sha(parent) == info['parent_assembly_sha256'], 'Parent assembly hash changed')
        work.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parent, work)
        self.checkpoint('parent_copied', state=state, parent=str(parent), work=str(work), sha256=sha(work))
        opened = self.sw.OpenDoc6(str(work), 2, 193, '', 0, 0)
        require(isinstance(opened, tuple) and len(opened) == 3 and opened[0] is not None and opened[1] == 0,
                'Copied assembly open failed')
        model = self.wrap(opened[0], 'IModelDoc2')
        opened = None
        self.activate(model, work)
        assembly = self.wrap(model, 'IAssemblyDoc')
        # Drop geometry residency before changing the exact twelve instances.
        self.report['initial_unload_api_return'] = assembly.LightweightAllResolved()
        raw = assembly.GetComponents(True) or []
        require(len(raw) == 585, 'Expected original 585 instances')
        lookup = {}
        for item in raw:
            component = self.wrap(item, 'IComponent2')
            identity = component.ComponentReference
            require(identity not in lookup, 'Duplicate parent component identity')
            lookup[identity] = component
        old_ids = set(removed) | set(replaced)
        require(len(old_ids) == 12 and old_ids <= set(lookup), 'Exact deletion contract mismatch')
        old_all = set(lookup)
        model.ClearSelection2(True)
        for identity in sorted(old_ids):
            require(lookup[identity].Select4(True, None, False), 'Cannot select exact old instance: '+identity)
        extension = self.wrap(model.Extension, 'IModelDocExtension')
        require(extension.DeleteSelection2(0), 'Exact deletion failed')
        model.ClearSelection2(True)
        remain = {self.wrap(x, 'IComponent2').ComponentReference for x in assembly.GetComponents(True) or []}
        require(remain == old_all-old_ids and len(remain) == 573, 'Deletion changed wrong instances')
        # Remove wrappers for deleted components before loading replacements.
        lookup = raw = item = component = None
        gc.collect()
        self.checkpoint('exact_twelve_removed', remaining=573, memory=self.memory_snapshot())
        rows = info['instances']
        new = [row for row in rows if row['id'] not in remain]
        require(len(new) == 24, 'Expected exactly 24 replacement/new instances')
        for row in new:
            require(max(abs(a-b) for a, b in zip(t16(row['T_S_local']), IDENTITY16)) < 1e-12,
                    'WP06 global source requires identity transform')
        added = assembly.AddComponents3(
            self.VARIANT(self.pythoncom.VT_ARRAY | self.pythoncom.VT_BSTR, [r['native_path'] for r in new]),
            self.VARIANT(self.pythoncom.VT_ARRAY | self.pythoncom.VT_R8, IDENTITY16*24),
            self.VARIANT(self.pythoncom.VT_ARRAY | self.pythoncom.VT_BSTR, ['']*24)) or []
        require(len(added) == 24, 'Incomplete insertion')
        for item, row in zip(added, new):
            component = self.wrap(item, 'IComponent2')
            component.ComponentReference = row['id']
            component.Name2 = re.sub(r'[ .()/\\]', '_', row['id'])
            require(component.Select4(True, None, False), 'Cannot select new instance for fixed pose')
        assembly.FixComponent()
        model.ClearSelection2(True)
        props = self.wrap(extension.CustomPropertyManager(''), 'ICustomPropertyManager')
        for key, value in dict(WP07_STATE=state, WP07_INSTANCES=597,
                              WP07_STATUS='FIXED_POSE_INTEGRATION_CANDIDATE',
                              WP07_MANIFEST_SHA256=self.report['manifest_sha256'],
                              WP07_MOTION_MODEL='NONE_FIXED_POSES').items():
            props.Add3(key, 30, str(value), 2)
        model.EditRebuild3()
        self.report['warm_preflight'] = self.warm_preflight(model, rows)
        self.report['native_save'] = self.save_new(model, target)
        final_sha = self.report['native_save']['sha256']
        self.report['final_native_sha256'] = final_sha
        self.report['full_step_export_status'] = 'SKIPPED_BY_EXPLICIT_NATIVE_ONLY_SCOPE'
        self.report['full_native_step_verified'] = False
        self.report['source_full_step_is_not_native_roundtrip'] = True
        self.close_own_saved(model, target, final_sha)
        # Release all warm component/model wrappers; they must not retain geometry
        # while the final assembly is independently reopened.
        added = item = component = props = extension = assembly = model = None
        gc.collect()
        self.checkpoint('final_native_saved_closed_before_componentwise_cold', state=state, sha256=final_sha,
                        memory=self.memory_snapshot())
        cold, self.report['cold_open'] = recovery.open_readonly(self, target)
        self.report['cold_inspection'] = self.inspect(cold, rows, target)
        self.report['cold_inspection_native_sha256'] = final_sha
        cold.ShowNamedView2('', 7)
        cold.ViewZoomtofit2()
        cold.GraphicsRedraw2()
        bmp = R/'results'/('WP07_'+state.upper()+'.bmp')
        self.report['screenshot'] = dict(path=str(bmp), saved=bool(cold.SaveBMP(str(bmp), 1600, 1200)))
        require(sha(target) == final_sha, 'Final native bytes changed after cold inspection')
        require(sha(parent) == info['parent_assembly_sha256'], 'Parent assembly changed')
        self.report['left_open_dirty_flag'] = bool(val(cold, 'GetSaveFlag'))
        self.report['no_native_save_after_cold'] = True
        self.report['status'] = 'PASS_NATIVE_FIXED_POSE_COMPONENTWISE_COLD__FULL_STEP_NOT_VERIFIED'
        self.checkpoint('native_only_state_complete', state=state, instances=597, solids=978,
                        final_native_sha256=final_sha)
        return cold, target, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', choices=('parking', 'released'))
    parser.add_argument('--skip-neutral-export', action='store_true')
    args = parser.parse_args()
    mfpath = R/'results/INTEGRATION_MANIFEST.json'
    manifest, mfsha = recovery.read_json(mfpath), sha(mfpath)
    output = R/'results'/('NATIVE_'+args.state.upper()+'.json')
    require(not output.exists(), 'Existing receipt protected: '+str(output))
    report = dict(status='RUNNING', state=args.state, manifest_sha256=mfsha,
                  progress=[], save_attempts=[], skip_neutral_export=args.skip_neutral_export)
    builder = None
    try:
        recovery.require_outer_guard(report)
        allowed, receipts = recovery.registered_inputs(manifest, mfsha, include_service_recovery=True)
        parent = manifest['states'][args.state]['parent_assembly_path']
        pins = dict(allowed)
        pins.update(receipts)
        pins[parent] = manifest['states'][args.state]['parent_assembly_sha256']
        pins[str(mfpath)] = mfsha
        for module in (Path(__file__).resolve(), Path(v2.__file__), Path(recovery.__file__), Path(v2.base.__file__)):
            pins[str(module)] = sha(module)
        for path, digest in pins.items():
            require(sha(path) == digest, 'Pinned native input or receipt changed: '+path)
        report['input_pins'] = pins
        recovery.persist(output, report)
        builder = IntegratorV3(output, report)
        builder.skip_neutral_export = args.skip_neutral_export
        require(int(val(builder.sw, 'GetProcessID')) == 26208, 'Unexpected existing SolidWorks PID')
        builder.close_registered(allowed)
        builder.sw.Visible = True
        builder.sw.UserControl = True
        builder.integrate(args.state, manifest['states'][args.state], manifest['removed_ids'], manifest['replaced_ids'])
        report['inputs_unchanged'] = all(sha(path) == digest for path, digest in pins.items())
        require(report['inputs_unchanged'], 'Pinned input changed during V3 native integration')
        builder.checkpoint('completed')
    except Exception as exc:
        report.update(status='FAILED', error=str(exc), traceback=traceback.format_exc())
        recovery.persist(output, report)
        raise
    finally:
        if builder and builder.initialized:
            builder.pythoncom.CoUninitialize()


if __name__ == '__main__':
    main()
