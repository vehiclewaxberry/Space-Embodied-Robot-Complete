"""P0: register the verified-but-unregistered V32 Kelvin correction (no design changes)."""
from pathlib import Path
import csv, hashlib, json, datetime

A = Path(__file__).resolve().parents[1]
R = A / 'results/kelvin_v32'
D = A / 'ecad/revisions/v32'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def main():
    files = sorted([p for p in R.rglob('*') if p.is_file() and p.name != 'SHA256_V32.csv'] +
                   [p for p in D.rglob('*') if p.is_file()])
    rows = [(p.relative_to(A).as_posix(), p.stat().st_size, sha(p)) for p in files]
    with (R / 'SHA256_V32.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['path', 'bytes', 'sha256']); w.writerows(rows)
    val = read(R / 'VALIDATION.json'); build = read(R / 'NATIVE_BUILD.json')
    drc = read(R / 'MAIN_INPUT_DRC.json'); erc = read(R / 'SYSTEM_ERC.json'); ce = read(R / 'COUNTEREXAMPLES.json')
    assert val['passed'] and build['passed'] and ce['passed']
    assert drc['unconnected_items'] == [] and drc['violations'] == []
    erc_viol = sum(len(s.get('violations', [])) for s in erc.get('sheets', []))
    status = dict(
        revision='V32',
        registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        registered_by='Claude Fable 5.1 (P0 registration only; no design change)',
        status='KELVIN_EDA_CONNECTION_CORRECTION_VERIFIED__REGISTERED__NO_RELEASE_CREDIT',
        scope=val['scope'],
        parent='V30 physical candidate + V31 input closure; same WP10 candidate',
        kelvin_items_closed=4,
        mechanism='duplicate_pad_numbers_are_jumpers on R201/R202 (WSLP2726 split Kelvin lands); copper/pad/drill fingerprint unchanged',
        board_sha256=build['board_sha256'], original_board_sha256=build['original_board_sha256'],
        system_ERC_violations=erc_viol, system_ERC_sheets=val['checks'][13]['sheets'] if len(val['checks']) > 13 else None,
        main_input_DRC_unconnected=len(drc['unconnected_items']), main_input_DRC_violations=len(drc['violations']),
        DRC_ignored_rules_still_inherited=[x['key'] for x in drc['ignored_checks']],
        negative_controls_passed=len(ce['cases']), independent_checks=val['checks_run'],
        electrical_refs=val['active_component_count'], pin_network_records=val['active_pin_record_count'],
        full_system_PCB_schematic_parity_checked=val['full_system_PCB_schematic_parity_checked'],
        hardware_tests=0, native_whole_spacecraft_rebuilds=0, whole_design_complete=False, manufacturing_release=False,
        evidence=[dict(path=str((R / n).relative_to(A).as_posix()), sha256=sha(R / n)) for n in
                  ['VALIDATION.json', 'NATIVE_BUILD.json', 'MAIN_INPUT_DRC.json', 'SYSTEM_ERC.json', 'COUNTEREXAMPLES.json']],
        file_manifest='results/kelvin_v32/SHA256_V32.csv', file_count=len(rows))
    (A / 'DELIVERY_STATUS_V32.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # navigation: working candidate pointer
    wc_path = A / 'CURRENT_WORKING_CANDIDATE.json'
    wc = read(wc_path)
    wc['electrical_revision'] = dict(revision='V32', kind='KELVIN_EDA_CONNECTION_CORRECTION',
                                     sources='ecad/revisions/v32', results='results/kelvin_v32',
                                     status='DELIVERY_STATUS_V32.json', ECAD_updated=True, native_CAD_updated=False,
                                     whole_design_complete=False)
    wc_path.write_text(json.dumps(wc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # navigation: CURRENT_candidate.md (prepend, keep BOM if present)
    cc = A.parents[1] / 'CURRENT_candidate.md'
    raw = cc.read_bytes(); bom = raw.startswith(b'\xef\xbb\xbf'); text = raw.decode('utf-8-sig')
    entry = ('## WP10 V32 Kelvin 连接修正登记（2026-09-11，P0 登记）\n\n'
             '主输入板 4 项 Kelvin 分裂盘“未连接”DRC 项已用 KiCad 10 器件内部连接焊盘机制关闭：'
             '[机器状态](runs/wp10_mechatronic_closure_20260908/implementation/DELIVERY_STATUS_V32.json) / '
             '[独立验证 18 项](runs/wp10_mechatronic_closure_20260908/implementation/results/kelvin_v32/VALIDATION.json) / '
             '[反例 2 例](runs/wp10_mechatronic_closure_20260908/implementation/results/kelvin_v32/COUNTEREXAMPLES.json)。'
             '系统 ERC 0 违规（13 页），主输入板 DRC 0 违规 0 未连接，铜/焊盘/钻孔指纹不变，211 位号/677 针脚记录不变。'
             '本条目只登记已存在回执；不改设计、不给整机、制造或上电信用。V33 版图/热路修订另见后续条目。\n\n---\n\n')
    cc.write_bytes((b'\xef\xbb\xbf' if bom else b'') + (entry + text).encode('utf-8'))
    print(json.dumps(dict(files=len(rows), erc_violations=erc_viol, status=status['status']), ensure_ascii=False))


if __name__ == '__main__':
    main()
