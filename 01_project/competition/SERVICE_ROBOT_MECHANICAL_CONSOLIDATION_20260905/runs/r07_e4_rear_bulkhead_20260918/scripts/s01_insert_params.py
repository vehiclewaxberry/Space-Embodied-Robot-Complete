# -*- coding: utf-8 -*-
"""R07-E4: 向 design_parameters.json 插入 rear_bulkhead_clamp_r07_e4 参数块（保留 CRLF 行尾）。
第3边 端框→后发射保留隔框（ADAPTER_CONNECTION_REDESIGN）：
  实读：隔框 x[-189,-183] 与后端框 x[-183,-177] 面贴合于 x=-183（Common=0.0 零体积，当前无夹紧）；
  四角 (y,z)=(±107.15,±107.15) 隔框 Ø8 窗口与 M4 端框接口（Ø4.5 孔）同轴，M4×22 螺钉头 x[-187,-183]
   recessed 在窗口内（径向隙 0.5），仅夹端框→端塞，隔框游离——即原票"尚未形成夹紧堆栈"。
  方案：阶梯夹套（筒 OD7.9×6 入窗口 + 法兰 OD12×2 压隔框外面，ID Ø4.5）+ 后场 4 螺钉包络
  M4×22→M4×30（锚点 x=-183→-191，尖端 x=-161 与端塞啮合不变）；不新增任何孔（窗口/M4 接口均既有）。
  供应方侧（保留体积/窗口外段/肋）保持参数化，不臆造部署器孔系；前端框无隔框 OUT_OF_SCOPE_REGISTERED。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
P = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'

BLOCK = """  "rear_bulkhead_clamp_r07_e4": {
    "status": "CANDIDATE_NOMINAL_GEOMETRY; material/grade/preload/locking/effective_thread_engagement/bearing_allowable/load_rating UNKNOWN",
    "provenance": {
      "ticket_id": "R07 connection_edges 第3边 端框→后发射保留隔框：隔框Ø8窗口与M4端框接口尚未形成新的连接/夹紧堆栈 (ADAPTER_CONNECTION_REDESIGN)",
      "issue_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json (R07 local_review connection_edges 第3边; snapshot sha256 fe90ef815f709cd8...)",
      "plan_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/WP03_NEXT_STAGE_MECHANICAL_PLAN_20260906.md Section 4.1 第4行：星内侧连接先闭合；供应方侧按待确认 ICD 保持参数化，不臆造部署器孔系",
      "run": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918/",
      "authorized_scope": "仅 R07-E4 一边（后端框→后发射保留隔框）digital_geometry 候选实体与登记；保持器机构/供应方部署器接口不属本工作包；父票 R07 不关闭；E1/E2/E3 与 A/B 支承不动"
    },
    "corner_geometry_readback": {
      "axis_S": [1, 0, 0], "corner_yz_S_mm": [-107.15, 107.15],
      "bulkhead": "rear_launch_bulkhead Box(6,226.3,226.3)-Box(8,158,158) @x=-186 → 体 x[-189,-183]；四角 Ø8 窗口（深10过钻）既有，本包不改",
      "end_frame": "RB_end_frame_-1 Box(6,226.3,226.3)-Box(8,202.3,202.3) @x=-180 → 体 x[-183,-177]；四角 Ø4.5 X 向孔（深8过钻）既有 M4 接口，本包不改",
      "end_screw_current": "RB_end_screw_-1_* M4×22 包络：头 x[-187,-183] recessed 于 Ø8 窗口（径向隙 0.5），杆 x[-183,-161] 拧入端塞 Ø3.3 导孔（螺纹啮合惯例）",
      "end_plug": "RB_end_plug_-1_* x[-177,-157]（WP03 重建 7.8×7.8），Ø3.3 X 向导孔既有",
      "fit_truth": "隔框∩端框 Common=0.0（面贴合 x=-183 零体积，贴合区=端框环带扣除四角窗口）；隔框∩螺钉=0.0；隔框当前仅贴合无夹紧——原票缺口实读确认"
    },
    "clamp_sleeve": {
      "concept": "阶梯夹套：筒 OD7.9×6 滑入既有 Ø8 窗口（x[-189,-183]，隙 0.05/边），法兰 OD12×2 压隔框外面（x[-191,-189]，承压环 8→12），ID Ø4.5 过 M4 杆（隙 0.25/边）；4 套正定位（FOUR_SLEEVE_POSITIVE）",
      "barrel_od_mm": 7.9, "barrel_length_mm": 6, "flange_od_mm": 12, "flange_thickness_mm": 2, "id_diameter_mm": 4.5,
      "material": "AL_DENSITY_CANDIDATE 2.7e-6（E1 防压套先例：真实铝候选 CAD_ESTIMATE）；材料牌号/压溃/承压 UNKNOWN",
      "no_new_holes": "本边不新增任何孔——Ø8 窗口与 M4 端框接口均既有（ADAPTER_CONNECTION_REDESIGN 仅新增夹套+延长螺钉包络）"
    },
    "rear_screw": {
      "concept": "后场 4 件 M4 端面螺钉包络延长 22→30：锚点（头下面）x=-183→-191（压套法兰），头 x[-195,-191]，杆 x[-191,-161]；尖端 x=-161 与端塞啮合段 x[-177,-161] 逐位不变（E2 螺纹惯例对复算应逐位一致）；前场 4 件 M4×22 不动",
      "thread": "M4_UNSELECTED", "length_mm": 30, "length_before_mm": 22, "shank_diameter_mm": 4,
      "head_diameter_mm": 7, "head_height_mm": 4, "anchor_abs_x_mm": 191, "tip_x_S_mm": -161,
      "pn_candidate": "WP01-MT-M4X30-E4-ENVELOPE_WP03",
      "material_grade_preload_locking_engagement": "UNKNOWN"
    },
    "stack_order": ["螺钉头 Ø7×4（x[-195,-191]）", "夹套法兰 OD12×2（x[-191,-189]，承压隔框外面）",
                    "隔框 6（x[-189,-183]，Ø8 窗口+夹套筒）", "端框 6（x[-183,-177]，Ø4.5 孔）",
                    "端塞啮合（x[-177,-161]，Ø4 入 Ø3.3 螺纹惯例）"],
    "supplier_side": "隔框外侧（Ø8 窗口外段、launch_interface_reserved_volume x[-215,-195] r60、rear 肋 x[-195,-189]）保持参数化占位不动；不臆造部署器孔系；ICD UNKNOWN；角区径向 151.5 > 保留体积 r60 → 头/法兰不入侵",
    "front_cover_scope": "OUT_OF_SCOPE_REGISTERED：前端框（sx=+1）无隔框；front_service_cover（x[183,185]）孔系 Ø3.4@(±101,±101) 与角区 M4 接口（±107.15）不同轴；原票仅指后端框→隔框，不擅自扩范围",
    "e2_corner_avoidance": "E2 分段销在 (x=-164, y=±107.15) Z 向角区站位，与 E4 堆栈 x∈[-195,-183] bbox 间隙 ~16.8 不交；装序无冲突（不同 x 站位）",
    "assembly_order": "端框/端塞链（E2 已闭环）→ 隔框就位贴合端框后面(x=-183) → 4 夹套自 -x 插入窗口（法兰朝外）→ M4×30 自 -x 拧入（过套 ID→端框孔→端塞 Ø3.3）→ 肋/供应方侧；工具轴 X，行程候选 ~50mm",
    "groups": [
      {"id": "1_1", "sy": 1, "sz": 1},
      {"id": "1_-1", "sy": 1, "sz": -1},
      {"id": "-1_1", "sy": -1, "sz": 1},
      {"id": "-1_-1", "sy": -1, "sz": -1}
    ],
    "registered_constraints": {
      "threadless_envelope": "紧固件为无螺纹名义包络；材料/等级/预紧/防松/有效啮合 UNKNOWN，零填充禁止",
      "front_screws_untouched": "前场 4 件 RB_end_screw_1_* M4×22 包络不动；前端框无隔框",
      "thread_convention_preservation": "螺钉延长仅在头侧（x<-183），端塞∩螺钉重叠区（x[-177,-161]）不变 → E2/E3 结转的 8 对螺纹惯例复算应逐位一致，差异如实登记不覆盖",
      "ab_support_untouched": "rear_vertical/horizontal_rib（A/B 支承）与 launch_interface_reserved_volume 不动"
    }
  },
"""

ANCHOR = '  "physical_inputs_pending": ['

def main():
    raw = P.read_bytes().decode('utf-8')
    if '"rear_bulkhead_clamp_r07_e4"' in raw:
        print('ALREADY_PRESENT'); return
    idx = raw.index(ANCHOR)
    eol = '\r\n' if '\r\n' in raw else '\n'
    block = BLOCK.replace('\n', eol)
    new = raw[:idx] + block + raw[idx:]
    json.loads(new)
    P.write_bytes(new.encode('utf-8'))
    print('INSERTED eol=%r bytes=%d' % (eol, len(new.encode('utf-8'))))
    data = json.loads(P.read_bytes().decode('utf-8'))
    e4 = data['rear_bulkhead_clamp_r07_e4']
    print('groups:', len(e4['groups']), 'screw len:', e4['rear_screw']['length_mm'])

if __name__ == '__main__':
    main()
