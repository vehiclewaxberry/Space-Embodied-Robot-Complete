# -*- coding: utf-8 -*-
"""阶段一收口两包独立复验：汇总四组证据，签发两份 REVIEW_VERDICT，并刷新整组边车。
裁决语义：仅证明"被审 run 声明的证据链在本审阅独立重放/复算下成立"；
不构成整星设计完成或制造放行（whole_design_complete=false, manufacturing_release=false）。"""
import json, subprocess, time
from pathlib import Path
from sc_common import (REV, ROOT, write_json, sidecar, sha256_file,
                       R17_AFTER, R17_BEFORE_BOM, BASELINE_STRUCTURE_RECEIPT_SHA,
                       PARAMS_SHA, E4_SOURCE_SHA, POSE_SCREEN_V2_SHA)

EV = REV / 'evidence'
NOW = time.strftime('%Y-%m-%dT%H:%M:%S%z')


def load(name):
    return json.loads((EV / name).read_text(encoding='utf-8'))


def head_commit():
    r = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(ROOT), capture_output=True, timeout=30)
    return r.stdout.decode('utf-8', 'replace').strip()


def main():
    a1 = load('review_a1_r17_negctl.json')
    a234 = load('review_a2a3a4_static.json')
    b12 = load('review_b1b2_validator.json')
    b34 = load('review_b3b4_r14_clean.json')
    assert a1['verdict'] == a234['verdict'] == b12['verdict'] == b34['verdict'] == 'PASS', '证据组存在非 PASS'

    basis_pins = {
        'r17_after_hashes': R17_AFTER,
        'r17_before_bom_sha256': R17_BEFORE_BOM,
        'baseline_service_structure_receipt_sha256': BASELINE_STRUCTURE_RECEIPT_SHA,
        'design_parameters_sha256': PARAMS_SHA,
        'e4_source_sha256': E4_SOURCE_SHA,
        'pose_screen_v2_sha256': POSE_SCREEN_V2_SHA,
        'review_head_commit_at_review': head_commit(),
    }

    common_tail = {
        'whole_design_complete': False,
        'manufacturing_release': False,
        'generated_at': NOW,
        'verdict_semantics': (
            '本裁决为独立复验裁决：审阅者以只读方式对被审 run 的声明证据链进行独立重放/复算，'
            '证实其在本审阅口径下成立；不升级任何科学/工程结论，不构成整星设计完成证明或制造放行。'
            'PASS_WITH_OBSERVATIONS = 全部独立复验判据通过，但登记有不影响通过判据的观察项。'),
    }

    # ---------- 裁决 1：R17 导出链 ----------
    verdict_r17 = {
        'review': 'STAGE1_CLOSURE_INDEPENDENT_REVERIFY/R17_EXPORT_CHAIN',
        'review_run': REV.name,
        'reviewed_run': 'r17_export_chain_20260919',
        'reviewed_commit': 'de892b81',
        'reviewer_role': 'INDEPENDENT_REVIEWER_READ_ONLY',
        'scope': ('WP03 阶段一收口工作包 A：BOM 交接来源时序生产修复（export_parts_and_bom.py 重写 '
                  '+ README 顺序说明）。纯软件/溯源任务，无 CAD 几何改动。审阅只读：不改候选、不执行 git 提交。'),
        'basis_pins': basis_pins,
        'sub_verdicts': {
            'A1_negative_control_replay': {
                'verdict': 'PASS', 'detail': a1['summary'],
                'note': ('沙箱复刻最小 20_engineering 相对布局，HANDOFF 哈希键按沙箱路径重定基（值不变）。'
                         '对照 --bom-only exit 0 且 BOM/INTERFACES 字节==live；6 负控全 exit 2 + 预期违例码 '
                         '+ BOM/INTERFACES 字节恢复（NC1b 实证 _restore None 分支：预先不存在则拒绝后仍不存在）。')},
            'A2_cad_free_import_probe': {
                'verdict': 'PASS',
                'note': ('独立探针子进程（新鲜沙箱重建后）证实 --bom-only 路径进程内 sys.modules 无 '
                         'build123d/OCP/cadgen/vtk/spacecraft_model/dynamics_handoff/numpy，与被审证据互锁。')},
            'A3a_deliverable_snapshots': {
                'verdict': 'PASS',
                'note': '交付物 9 项 before==inputs 快照、after==live（DYNAMICS_SUMMARY_ZH.md 无快照属预期）。'},
            'A3b_bom_content_audit': {
                'verdict': 'PASS',
                'note': ('BOM 497 行 15 列；214 分配/283 空单元；无 0 填；'
                         'allocated_mass_reference 全为 results/DYNAMICS_HANDOFF.json。')},
            'A3c_fail_closed_code_reading': {
                'verdict': 'PASS',
                'note': ('备份先于任何写；except Exception 全恢复；写入在所有校验之后；--bom-only 仍走全部校验。'
                         '发现语义边界见观察项 OA1。')},
            'A4_ticket_field_nonrewrite': {
                'verdict': 'PASS',
                'note': ('issues.json 的 R17 票字段 current_BOM_is_proven_stale=false / production_fix_applied=false '
                         '未被回写（票字段留 owner）；改前备份 inputs/BOM.csv==cfb4df9a…，staleness_audit 在位。')},
            'B4_workspace_cleanliness_cross': {
                'verdict': 'PASS',
                'note': ('git status 全仓仅 3 条 ??（本审阅 run 目录 + 验证器链 2 个新文件），无任何跟踪文件被改动；'
                         'ENG 目录 6 份回执/交接哈希与 R17 后钉固态逐位一致。'),
                'evidence': 'review_b3b4_r14_clean.json::B4_workspace_cleanliness'},
        },
        'key_results': {
            'negative_controls_replayed': '6/6 exit 2 + 预期违例码 + 字节恢复',
            'positive_control': '--bom-only exit 0，BOM/INTERFACES 字节==live（a6ce5bff…/f432955d…）',
            'spotcheck_consistency': '5/5（A2/A3a/A3b/A3c/A4）',
        },
        'observations': [
            {'id': 'OA1', 'severity': 'DOCUMENTATION',
             'text': ('"任一失配 exit 2"的严格语义只覆盖校验拒绝路径（HandoffRejected）。非 HandoffRejected 异常'
                      '（如 dynamics_handoff 子进程非零返回）同样恢复交付物字节，但以 traceback 退出、exit≠2。'
                      '建议 README/验收文档注明该语义边界。')},
            {'id': 'OA2', 'severity': 'EXPECTED_BEHAVIOR',
             'text': ('NC8 类注入变异会连带触发实例集合/owner 覆盖面错配码（一次变异多码检出）。'
                      '属预期行为，与被审 NC2/NC7 的多码检出同型，非误报。')},
        ],
        'limitations_carried_from_candidate': [
            'ticket_closure=NOT_CLOSED：R17 票字段不回写，留 owner/审阅（本审阅确认未回写，见 A4）。',
            '修复链覆盖面以 8/8 负控（本审阅独立重放其中 6 类）与真实链复跑为界；不证明交接语义之外的工程正确性。',
        ],
        'verdict': 'R17_INDEPENDENT_REVERIFY_PASS_WITH_OBSERVATIONS',
    }
    verdict_r17.update(common_tail)

    # ---------- 裁决 2：验证器 R14 ----------
    verdict_r14 = {
        'review': 'STAGE1_CLOSURE_INDEPENDENT_REVERIFY/VALIDATOR_R14',
        'review_run': REV.name,
        'reviewed_run': 'validator_integration_r14_20260919',
        'reviewed_commit': 'd29b06d6',
        'reviewer_role': 'INDEPENDENT_REVIEWER_READ_ONLY',
        'scope': ('WP03 阶段一收口工作包 B：严格表面验证器真实接入（快照绑定 + URDF 派生配对合同）'
                  '+ R14 参数扰动机检对照。审阅只读：不改候选、不执行 git 提交。'),
        'basis_pins': basis_pins,
        'sub_verdicts': {
            'B1_negative_control_replay': {
                'verdict': 'PASS', 'detail': b12['summary'],
                'note': ('live 模块 importlib 加载 + 深拷贝变异 aggregate() 重放：7/7 检出'
                         '（INPUT_STALE/SCRIPT_HASH_STALE/SNAPSHOT_BINDING_MISMATCH/NO_COMPLETION_EVENT/'
                         'NAN_OR_FLOAT_RESULT/DUPLICATE_PAIR_ID/DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED）。'
                         'NC5 集成面边界见观察项 OB1。')},
            'B2a_urdf_pair_derivation': {
                'verdict': 'PASS',
                'note': ('xml.etree 独立解析 live+快照 URDF（双钉固相等）：10 link、9 相邻关节、'
                         'C(10,2)=45−9=36、指/指延期 1、必需 35；合同集合与审阅推导逐键相等。')},
            'B2b_live_aggregator_replay': {
                'verdict': 'PASS',
                'note': ('strict_surface_integration.py 对 live POSE_SCREEN + 快照绑定重放：overall PASS / '
                         'protocol PASS / mechanical DISJOINT_WITHIN_DECLARED_SCOPE / 36/1/3，与被审证据一致；'
                         'POSE_SCREEN live sha==07670f67…。')},
            'B2c_sandbox_full_chain_rerun': {
                'verdict': 'PASS',
                'note': ('真实入口沙箱全链重跑（含 27MB STL 复刻）：exit 0、worker_rc 0、合同 36/35 与 live 相等；'
                         '3 个 EXISTING_CANDIDATE 姿态逐姿态逐配对（links+surface_intersection 排序比对）与 live 全等；'
                         '2 个 SOURCE_REFERENCE 参考姿态不经 worker（status 前缀 SOURCE_REFERENCE_35_BODY_PAIRS_…）；'
                         '沙箱绑定重算后汇总器 PASS/DISJOINT。')},
            'B3a_rename_bijection': {
                'verdict': 'PASS', 'detail': b34['B3a_rename_bijection']['pass'],
                'note': '实例 487 不变；差集恰 4 删 *_deck_fastener_*_-50 + 4 增 _-45，改名双射成立。'},
            'B3b_local_effect': {
                'verdict': 'PASS',
                'note': ('责任件逐行比对：diff 行恰=被审 C2 responsible_parts 集合（上下甲板 + segment0 四角材）；'
                         'COM x 负移 measured==claimed 且与解析 |dx|=n_hole·m_hole·5/mass 在 1% 内'
                         '（甲板 −0.0013631501956428 vs 解析 −0.0013631501956439；角材 −0.010256 级）；'
                         'segment1 角材+剪力网 spot 6 件逐位不变；4 改名 fastener parent/mount/pn 映射、COM +5.000 mm。'
                         'mass_kg/volume_mm3 个别行 1 ULP 浮点和序噪声见观察项 OB4。')},
            'B3c_legacy_field_inert': {
                'verdict': 'PASS',
                'note': 'legacy 扰动回执与基线顶层仅 dependency_sha256 不同，且其中仅 design_parameters.json 键不同。'},
            'B3d_restore_bit_identical': {
                'verdict': 'PASS',
                'note': ('复现回执文件 sha==d220c702…==live service_structure_instances.json；'
                         'design_parameters.json==324b49c7…；git diff HEAD（ENG 目录）为空。')},
            'B3e_bom_unpolluted': {
                'verdict': 'PASS',
                'note': 'live BOM.csv==a6ce5bff…（R17 后交付态），扰动试验未回写 BOM。'},
            'B4_workspace_cleanliness': {
                'verdict': 'PASS',
                'note': ('全仓 git status 仅 3 条 ??（本审阅 run 目录 + strict_surface_integration.py + '
                         'results/STRICT_SURFACE_INTEGRATION.json）；__cadgen__ 缓存由 .gitignore:19 覆盖不计；'
                         'ENG 目录无残留；6 份回执/交接哈希与 R17 后钉固态一致。')},
        },
        'key_results': {
            'negative_controls_replayed': '7/7 检出（被审登记 11/11；本审阅覆盖其中 7 个代表性面）',
            'positive_control': '沙箱全链重跑 3 姿态 × 36 对与 live 逐位一致；汇总器 PASS/DISJOINT_WITHIN_DECLARED_SCOPE',
            'derivation_chain': 'URDF→10 link→36 非相邻对→延期 1→必需 35，双钉固独立复算逐键相等',
            'perturbation_compare': 'R14 扰动 6/6 判据独立复算通过（B3a–B3e + B4）',
        },
        'observations': [
            {'id': 'OB1', 'severity': 'INTEGRATION_BOUNDARY',
             'text': ('require_physical_view 为独立守卫函数，aggregate()/main() 主路径不调用它'
                      '（全仓 grep 仅被被审 s03 脚本与本审阅调用）；NC5（exploded 视图拒绝）证明的是守卫单元行为，'
                      '非集成面。对照：R17 链 BOM 侧有 view==\'complete\' 检查；validator 链 POSE_SCREEN 消费侧'
                      '无视图字段概念。建议后续将守卫接入主路径或注明边界。')},
            {'id': 'OB2', 'severity': 'PROCESS',
             'text': ('strict_surface_integration.py 与 results/STRICT_SURFACE_INTEGRATION.json 为 untracked 新文件'
                      '（未 git add）。非半更新（既有跟踪文件零改动），但在提交链之外，后续收口提交时应纳入。')},
            {'id': 'OB3', 'severity': 'EXPECTED_BEHAVIOR',
             'text': ('R14 扰动回执 sha 变化仅因 dependency provenance 如实记录 design_parameters.json 哈希变化'
                      '（几何零效应）。该口径已核实合理，非回执不稳定。')},
            {'id': 'OB4', 'severity': 'NUMERICS',
             'text': ('B3b 责任件中 2/6 行（upper_equipment_deck、lower_deck_angle_1_0）的 mass_kg/volume_mm3 '
                      '在基线与扰动回执间相差 1 ULP（相对 ≤2.06e-16），为浮点求和序噪声；'
                      '候选"mass_kg 不变"在物理层成立、字节层非逐位。本审阅判据取相对容差 1e-12。')},
        ],
        'limitations_carried_from_candidate': [
            '机械碰撞验收为 DISJOINT_WITHIN_DECLARED_SCOPE：UNKNOWN 范围已声明（指/指对、相邻 link 对、闭体包含、连续路径），不零填。',
            '协议 PASS 不构成整星安全或发射收拢证明。',
            '负控被审登记 11/11；本审阅独立重放 7/7 个代表面（NC1/NC4a/NC4b/NC4c/NC6a/NC7/NC5），未重放 NC2/NC3/NC5b/NC6b/NC6c。',
        ],
        'verdict': 'VALIDATOR_R14_INDEPENDENT_REVERIFY_PASS_WITH_OBSERVATIONS',
    }
    verdict_r14.update(common_tail)

    write_json(REV / 'REVIEW_VERDICT_R17.json', verdict_r17)
    write_json(REV / 'REVIEW_VERDICT_VALIDATOR_R14.json', verdict_r14)

    # ---------- 整组边车刷新与复核 ----------
    targets = sorted((REV / 'scripts').glob('*.py')) + \
              sorted(p for p in (REV / 'evidence').glob('*.json')) + \
              [REV / 'REVIEW_VERDICT_R17.json', REV / 'REVIEW_VERDICT_VALIDATOR_R14.json']
    refreshed = {}
    for p in targets:
        refreshed[sidecar(p)] = Path(p).name
    # 复核：边车内容与文件实况一致
    mism = []
    for p in targets:
        sc = Path(str(p) + '.sha256')
        body = sc.read_bytes().decode('utf-8')
        h, rel = body.rstrip('\n').split('  ', 1)
        if h != sha256_file(p) or rel != p.resolve().relative_to(REV).as_posix():
            mism.append(p.name)
    print('verdicts written; sidecars refreshed:', len(targets), 'mismatch:', mism or 'NONE')
    for p in (REV / 'REVIEW_VERDICT_R17.json', REV / 'REVIEW_VERDICT_VALIDATOR_R14.json'):
        print(' -', json.loads(p.read_text(encoding='utf-8'))['verdict'], p.name)


if __name__ == '__main__':
    main()
