# -*- coding: utf-8 -*-
"""R07-E2: 向 design_parameters.json 插入 transverse_retention_r07_e2 参数块（保留 CRLF 行尾）。
设计驱动（实读确认，登记于 geometric_truth_registration）：
  T1 端塞截面：WP02 源 box(20,9.8,9.8) vs WP03 rootadd 重建 box(20,7.8,7.8) vs 纵梁内孔 8×8；
  T2 X=±164 竖向 Ø4.5 对偶孔两侧均已存在（纵梁双壁贯穿 + 端塞竖向贯穿），E2 不新增任何孔；
  T3 端塞竖向孔与既有 M4 端面螺钉包络(Ø4, x∈[161,183])在塞心十字相交 → 全长沙蚕不可行
     （十字开孔销韧带 0.1 mm 结构无效），取分段短销/栓候选：上下两段各让开螺钉包络 0.1 mm。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
P = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'

BLOCK = """  "transverse_retention_r07_e2": {
    "status": "CANDIDATE_NOMINAL_GEOMETRY; material/grade/fit/preload/locking/shear_bearing_allowable/load_rating UNKNOWN",
    "provenance": {
      "ticket_id": "R07 connection_edges[1] 纵梁→端塞横向保持 (TRANSVERSE_RETENTION_UNDEFINED)",
      "issue_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json (R07 local_review connection_edges 第2边; snapshot sha256 fe90ef815f709cd8...)",
      "plan_source": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/WP03_NEXT_STAGE_MECHANICAL_PLAN_20260906.md Section 4.1 第2行：为已有穿孔落实实际紧固件、啮合/防松和装入路径；端面轴向紧固不能代替此边",
      "run": "01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918/",
      "authorized_scope": "仅 R07-E2 一边 digital_geometry 候选实体与登记；载荷/强度/配合/防松 UNKNOWN；父票 R07 不关闭；E1/E3/E4 与 A/B 支承不动"
    },
    "geometric_truth_registration": {
      "T1_plug_section": "WP02 源定义端塞 box(20,9.8,9.8)（字面构建将与纵梁 8×8 内孔单边干涉 0.9）；WP03 rootadd 重建为 box(20,7.8,7.8)（与内孔单边间隙 0.1，SLIP_FIT_CANDIDATE）；原票文字'端塞7.8对内孔8'与 WP03 重建一致；WP02 只读不改，分歧登记不静默",
      "T2_paired_holes_preexist": "X=±164 竖向 Ø4.5 对偶孔两侧均已存在：纵梁双壁贯穿（WP02 root_structure L18 bore Ø4.5×16）+ 端塞竖向贯穿（bore Ø4.5×12 @ 局部 x=-sx*3 → 全局 ∓164，WP02 L27 与 WP03 重建逐位一致保留）；E2 不新增任何孔、不修改任何既有构件",
      "T3_crossing_conflict": "端塞竖向孔轴(x=±164,y=±107.15)与既有 M4 端面螺钉包络(Ø4, x∈[161,183], y/z=±107.15)在塞心十字相交：全长竖销与 M4 螺钉几何不可共存（十字开孔销剩余韧带 0.1 mm 结构无效，已否决）；处置=分段短销/栓，上下两段尖端各让开螺钉包络 0.1 mm；螺钉装序与 E2 销无关（两段均不阻塞 Ø3.3 导孔）；螺纹啮合惯例：既有 M4 螺钉包络 Ø4 > 端塞导孔 Ø3.3 为 WP02 THREAD_ENGAGEMENT 表示（既有，非 E2 引入）"
    },
    "concept": "8 站（2 端 × 4 纵梁）分段横向保持：每站两枚短销/栓经既有 Ø4.5 对偶孔分自两端穿入，各穿一壁+入塞 1.8 mm，尖端让开 M4 螺钉包络 0.1 mm；约束端塞相对纵梁 Tx 抽出/Tz 剪切（双剪面 POSITIVE_INTENT）；sz=+1 站：外侧(+z)带头短栓+OD9 垫圈、舱内侧带头短栓+OD7 垫圈；sz=-1 站：舱内(+z)侧带头短栓+OD7 垫圈、翼侧(-z)无头压装销（压配候选+翼根叉垫板 z=-113.15 顶面零距离物理止动 REGISTERED_SECONDARY）；舱侧垫圈 OD 7 因剪力板(y≤±103.15)邻近收窄（隙 0.5）",
    "station_x_abs_mm": 164,
    "hole_diameter_mm": 4.5,
    "hole_axis_S": [0, 0, 1],
    "fastener_candidate": {
      "type": "SEGMENTED_STUB_PIN_BOLT_UNSELECTED",
      "shank_diameter_mm": 4.4,
      "hole_clearance_per_side_mm": 0.05,
      "fit": "LOCATING/TRANSITION_FIT_CANDIDATE; 过盈/压配量 UNKNOWN",
      "head": {"diameter_mm": 7, "height_mm": 4},
      "washer_out": {"outer_diameter_mm": 9, "inner_diameter_mm": 4.5, "thickness_mm": 1},
      "washer_bay": {"outer_diameter_mm": 7, "inner_diameter_mm": 4.5, "thickness_mm": 1, "note": "舱侧收窄 OD7 避剪力板(y≤±103.15)，隙 0.5"},
      "plug_engagement_per_stub_mm": 1.8,
      "tip_to_m4_screw_clearance_mm": 0.1,
      "wing_pin_to_pad_clearance_mm": 0.2,
      "material_grade_fit_preload_locking": "UNKNOWN"
    },
    "stack_z_intervals_mm": {
      "top_out": {"washer": [113.15, 114.15], "head": [114.15, 118.15], "shank": [109.25, 114.15]},
      "top_bay": {"head": [96.15, 100.15], "washer": [100.15, 101.15], "shank": [100.15, 105.05]},
      "bot_bay": {"shank": [-105.05, -100.15], "washer": [-101.15, -100.15], "head": [-100.15, -96.15]},
      "bot_wing_pin": {"shank": [-112.95, -109.25]}
    },
    "stations": [
      {"id": "H01", "sx": -1, "sy": -1, "sz": 1, "variant": "TOP_OUT_PLUS_BAY"},
      {"id": "H02", "sx": -1, "sy": 1, "sz": 1, "variant": "TOP_OUT_PLUS_BAY"},
      {"id": "H03", "sx": 1, "sy": -1, "sz": 1, "variant": "TOP_OUT_PLUS_BAY"},
      {"id": "H04", "sx": 1, "sy": 1, "sz": 1, "variant": "TOP_OUT_PLUS_BAY"},
      {"id": "H05", "sx": -1, "sy": -1, "sz": -1, "variant": "BOT_BAY_PLUS_WINGPIN"},
      {"id": "H06", "sx": -1, "sy": 1, "sz": -1, "variant": "BOT_BAY_PLUS_WINGPIN"},
      {"id": "H07", "sx": 1, "sy": -1, "sz": -1, "variant": "BOT_BAY_PLUS_WINGPIN"},
      {"id": "H08", "sx": 1, "sy": 1, "sz": -1, "variant": "BOT_BAY_PLUS_WINGPIN"}
    ],
    "dof_registration": [
      {"dof": "Tx(端塞相对纵梁轴向抽出)", "restraint": "双短销/栓各一壁剪面 + 入塞 1.8 mm 承压（双站双剪 POSITIVE_INTENT）", "level": "POSITIVE_INTENT; 剪/承压许用 UNKNOWN; SHORT_ENGAGEMENT_1.8MM_REGISTERED"},
      {"dof": "Tz(竖向相对剪切)", "restraint": "销/栓杆承压", "level": "POSITIVE_INTENT; UNKNOWN"},
      {"dof": "Ty(横向相对位移)", "restraint": "方孔套合(7.8/8 单边 0.1) + 销杆", "level": "SOCKET_PLUS_PIN; UNKNOWN"},
      {"dof": "Rx(端塞绕纵轴滚转)", "restraint": "方孔套合 + M4 轴向螺钉链 + 销", "level": "REGISTERED_SECONDARY; 残余转角 UNKNOWN"},
      {"dof": "Ry/Rz", "restraint": "方孔套合 + 双销", "level": "SOCKET_PLUS_PIN; UNKNOWN"},
      {"dof": "销自身 z 向保持", "restraint": "sz=+1 站双头正向；sz=-1 站舱侧头 + 翼侧压配候选+翼根垫板物理止动", "level": "sz=+1 POSITIVE; sz=-1 PRESS_FIT_PLUS_REGISTERED_SECONDARY_STOP; 压配 UNKNOWN"}
    ],
    "assembly_tool": {
      "insertion": "sz=+1 站：外栓自 +z 星外穿入(工具轴 z)，舱内栓自 -z 舱侧穿入；sz=-1 站：舱内栓自 +z 舱侧穿入，翼侧无头销自 -z 压入(翼根叉装入前)",
      "tool_axis_S": [0, 0, 1], "tool_travel_candidate_mm": 80,
      "sequence": "与 M4 端面螺钉/端框装序无关（短销让开螺钉包络 0.1，不阻塞 Ø3.3 导孔）；舱内栓/销建议在甲板与设备装入前的根框阶段施装；翼侧无头销须在 wing_root_fork 装入前压装；装后更换翼侧销须先拆翼根叉（NEEDS_SEQUENCE_REVIEW）",
      "exit": "反向退出；翼侧无头销退出路径与装入同轴反向"
    },
    "registered_constraints": {
      "no_new_holes": "E2 不新增任何孔、不修改任何既有构件（纵梁/端塞孔已存在）",
      "m4_screw_crossing": "全长竖销与 M4 端面螺钉十字相交不可共存（见 T3）；分段方案尖端让开 0.1 mm，装序无关",
      "shear_web_washer_od": "舱侧垫圈 OD 7（非 WP02 M4 惯例 OD 9）：剪力板内缘 y=±103.15，OD9 垫圈 y 可达 ±102.65 将相交；OD7 留隙 0.5",
      "wing_pad_zone": "sz=-1 站 -z 侧孔口下翼根叉垫板(x∈[138,174], z 顶 -113.15)零距离贴面，任何外凸保持件不可行 → 无头压装销",
      "threadless_envelope": "紧固件为无螺纹名义包络；材料/等级/配合/预紧/防松 UNKNOWN，零填充禁止"
    }
  },
"""

ANCHOR = '  "physical_inputs_pending": ['

def main():
    raw = P.read_bytes().decode('utf-8')
    if '"transverse_retention_r07_e2"' in raw:
        print('ALREADY_PRESENT'); return
    idx = raw.index(ANCHOR)
    eol = '\r\n' if '\r\n' in raw else '\n'
    block = BLOCK.replace('\n', eol)
    new = raw[:idx] + block + raw[idx:]
    json.loads(new)
    P.write_bytes(new.encode('utf-8'))
    print('INSERTED eol=%r bytes=%d' % (eol, len(new.encode('utf-8'))))
    data = json.loads(P.read_bytes().decode('utf-8'))
    e2 = data['transverse_retention_r07_e2']
    print('stations:', len(e2['stations']))

if __name__ == '__main__':
    main()
