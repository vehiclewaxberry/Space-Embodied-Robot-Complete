"""Additive navigation pointers for CF1 (plan Task 10, last step). Refuses to run while Codex looks active.
- implementation/CURRENT_WORKING_CANDIDATE.json: adds the key 'active_layout_and_thermal' (nothing else touched).
- SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/CURRENT_candidate.md: prepends one CF1 entry in the existing style.
Every number is read from DELIVERY_STATUS_CF1.json. Plain python."""
from pathlib import Path
import json, subprocess, sys, time

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent                                   # implementation
RUN = A.parent                                 # runs/wp10_mechatronic_closure_20260908
CONS = RUN.parent.parent                       # SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905
REL = 'runs/wp10_mechatronic_closure_20260908/implementation/cf1_layout_thermal'


def codex_active(quiet_minutes=20):
    tl = subprocess.run(['tasklist'], capture_output=True, text=True, errors='replace').stdout.lower()
    if 'codex.exe' in tl:
        return 'codex.exe is running'
    newest = 0.0; newest_p = None
    for p in A.rglob('*'):
        if p.is_file() and 'cf1_layout_thermal' not in p.parts and 'logs' not in p.parts and '.git' not in p.parts:
            m = p.stat().st_mtime
            if m > newest:
                newest, newest_p = m, p
    age_min = (time.time() - newest) / 60
    if age_min < quiet_minutes:
        return 'newest non-CF1 write %.1f min ago: %s' % (age_min, newest_p)
    return None


def main():
    why = codex_active()
    if why:
        print('NOT_REGISTERED: Codex appears active (%s). Re-run when idle.' % why); return 2
    d = json.loads((C / 'DELIVERY_STATUS_CF1.json').read_text(encoding='utf-8'))
    th, pc, me = d['thermal'], d['pcb'], d['mechanical']
    straps_phrase = ('五实体对宿主无物理/OEM 件干涉（父本工具因电池 D-max 包络判 REJECTED）' if me['straps_vs_host']['physical_only_view'].startswith('CLEAR')
                     else '五实体对宿主存在物理干涉')
    nominal_phrase = ('360 W 名义点四环境 5 mm 网格全部通过' if th['acceptance_passes'] else '360 W 名义点未闭合')
    # 1 working candidate JSON (additive key only)
    wc_path = A / 'CURRENT_WORKING_CANDIDATE.json'
    wc = json.loads(wc_path.read_text(encoding='utf-8-sig'))
    wc['active_layout_and_thermal'] = dict(
        revision='CF1', kind=d['kind'], status=d['status'], date=d['date'],
        entry='cf1_layout_thermal/design/README_CF1.md', delivery_status='cf1_layout_thermal/DELIVERY_STATUS_CF1.json',
        sha256_manifest='cf1_layout_thermal/SHA256_CF1.csv', parent_electrical='ecad/revisions/v32', parent_geometry='V30',
        registered_as_active_candidate=False, whole_design_complete=False)
    wc_path.write_text(json.dumps(wc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # 2 consolidation-level markdown (prepend)
    md_path = CONS / 'CURRENT_candidate.md'
    md = md_path.read_text(encoding='utf-8')
    entry = (
        '## WP10 CF1 主输入板版图与导热路径热模型级修订（%s）\n\n'
        '[设计说明](%s/design/README_CF1.md) / [机器状态](%s/DELIVERY_STATUS_CF1.json) / [复核记录](%s/results/REVIEW_CF1.json)：'
        'V32 电气 + V30 几何之上的 Claude 增量，命名空间 `cf1_layout_thermal/`，父本零改动。'
        '3 oz 铜与 ≥8 mm 铜带使主路径损耗降 %.1f%%（铜带 %.1f A/mm²，但 Q201 焊盘入口颈 %.1f A/mm² 超 35，开放）；'
        '两条导热带接 ±Y 腹板 2 mm 内壁（实测面 S y ±101.15，接触 100%%；内壁只经离散桥块连到 8 mm 辐射板），%s，合计 %.0f g。'
        '%s（CHB %.1f °C、载板最坏 %.1f °C，最小载板余量 %.2f K）；'
        '%.1f W 未分配热下%s；所假设的模块位姿被精确窄相位拒绝（%.0f mm³ 夹持件重叠，dy 0…−6 / dz 0…+6 平移无解）。'
        '不是登记的活动候选；完整机电设计仍开放。\n\n---\n\n'
    ) % (d['date'], REL, REL, REL, pc['loss_reduction'] * 100, pc['worst_band_density_A_mm2'], pc['pad_entry_neck_density_A_mm2'],
         straps_phrase, me['aluminium_mass_kg'] * 1000, nominal_phrase, th['worst_CHB_case_C'], th['worst_carrier_C'], th['min_margins_C']['carrier_C'],
         th['unassigned_heat']['spec_listed_W'], ('仍闭合' if th['continuous_thermal_closure'] else '不闭合'),
         sum(max(v.values()) for v in me['module_pose']['physical_mm3'].values()))
    if 'WP10 CF1 主输入板版图' not in md:
        md_path.write_text(entry + md, encoding='utf-8')
    print(json.dumps(dict(registered=True, working_candidate=str(wc_path), candidate_md=str(md_path)), ensure_ascii=False)); return 0


if __name__ == '__main__':
    sys.exit(main())
