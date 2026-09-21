from pathlib import Path
R=Path(__file__).resolve().parents[1];source=R/'tools/build_module_native_bounded_v3.py';t=source.read_text()
t=t.replace("ap.add_argument('--emission',type=Path);a=ap.parse_args()","ap.add_argument('--emission',type=Path);ap.add_argument('--native-folder');a=ap.parse_args()")
t=t.replace("folder=R/'native'/kind;target=","folder=R/'native'/(a.native_folder or kind);m.require(folder.resolve().is_relative_to((R/'native').resolve()),'Native output outside run');target=")
t=t.replace("c=json.loads(Path(em['contract_path']).read_text())","rows.sort(key=lambda x:(x['id']!='WP09_BAT_-152_-78_screw',x['id']))\n    c=json.loads(Path(em['contract_path']).read_text())")
t=t.replace("(111,291,691)","(111,291,691,690,769)")
t=t.replace("for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k==111)",
"""report['import_toggle_before']={str(k):v for k,v in prefs['toggles'].items()}
        for k in prefs['toggles']:
            sw.SetUserPreferenceToggle(k,k==111)
            m.require(bool(sw.GetUserPreferenceToggle(k))==(k==111),'Import toggle readback differs')
        report['import_toggle_during']={str(k):sw.GetUserPreferenceToggle(k) for k in prefs['toggles']}
        report['neutral_import_basis']='Disable STEP-neutral run diagnostics (690) and analytic conversion (769), as well as legacy291 and 3D interconnect691; no native/source tolerance change.'
""".rstrip())
t=t.replace("report['session_preferences_restored']=True","report['import_toggle_after']={str(k):b.sw.GetUserPreferenceToggle(k) for k in prefs['toggles']} if prefs else {}\n                report['session_preferences_restored']=True")
p=R/'tools/build_module_native_bounded_v4.py';assert not p.exists();compile(t,str(p),'exec');p.write_text(t,encoding='utf-8');print(p)

