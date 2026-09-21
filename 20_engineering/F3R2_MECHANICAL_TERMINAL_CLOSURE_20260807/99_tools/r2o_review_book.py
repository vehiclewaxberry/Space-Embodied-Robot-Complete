# -*- coding: utf-8 -*-
"""F3R2 human review book: one self-contained HTML page a reviewer can read
without opening the CAD.

It shows what was measured, what was NOT measured, and every open item, with
the numbers taken straight from the machine verdicts.  Screenshots are embedded
so the page survives being moved.
"""
import base64
import json
import sys
import traceback
from pathlib import Path

import r2_common as C

OUT = C.REVIEW2 / "F3R2_HUMAN_REVIEW_BOOK.html"
RAW = C.SHOT2 / "RAW"


def load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def img(name):
    p = RAW / (name + ".png")
    if not p.is_file():
        return "<p class='miss'>[missing render: %s]</p>" % name
    b = base64.b64encode(p.read_bytes()).decode("ascii")
    return "<img src='data:image/png;base64,%s' alt='%s'>" % (b, name)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def main():
    try:
        gate = load(C.GATE2 / "F3R2_FINAL_GATE.json")
        g3a = load(C.CLR2 / "G3A_NATIVE_INTERFERENCE_RESULTS.json")
        nat = load(C.CLR2 / "G3A_NATIVE_ATTEMPTS.json")
        sc = load(C.CLR2 / "G3A_INSTRUMENT_SELFCHECK.json")
        ps = load(C.CFG2 / "F3R2_POSE_SEARCH.json")
        pe = load(C.CFG2 / "F3R2_POSE_EVALUATION.json")
        wr = load(C.SUP2 / "F3R2_WING_ROOT_INTERFACE.json")
        sup = load(C.SUP2 / "F3R2_STOW_SUPPORT_DEFINITION.json")
        g4 = load(C.HDRM2 / "F3R2_ARM_HDRM_DEFINITION.json")
        g5 = load(C.CLR2 / "F3R2_CONTINUOUS_CLEARANCE_RESULTS.json")
        dt = load(C.THREAD2 / "F3R2_DIGITAL_THREAD.json")
        shots = load(C.SHOT2 / "F3R2_SHOT_REPORT.json")

        H = []
        A = H.append
        A("""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>F3R2 机械终局闭合 — 人工评审书</title><style>
body{font-family:"Segoe UI","Microsoft YaHei",sans-serif;max-width:1180px;
margin:0 auto;padding:28px;color:#1a1a1a;line-height:1.55}
h1{border-bottom:3px solid #234;padding-bottom:8px}
h2{margin-top:34px;border-left:5px solid #234;padding-left:10px}
h3{margin-top:22px;color:#234}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
th,td{border:1px solid #ccd;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#eef1f5}
.pass{color:#0a7a30;font-weight:600}.fail{color:#b00;font-weight:600}
.hold{color:#a15c00;font-weight:600}.na{color:#666;font-style:italic}
.box{background:#f7f9fb;border-left:4px solid #468;padding:10px 14px;
margin:14px 0}
.warn{background:#fff7ec;border-left:4px solid #d18000}
.bad{background:#fdf0f0;border-left:4px solid #b00}
img{max-width:100%;border:1px solid #ccd;margin:8px 0}
figure{margin:16px 0}figcaption{font-size:13px;color:#445;margin-top:4px}
code{background:#eef1f5;padding:1px 5px;border-radius:3px;font-size:13px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
</style></head><body>""")

        A("<h1>F3R2 机械终局闭合 — 人工评审书</h1>")
        A("<p><b>任务</b>：<code>F3R2_G3_TO_G8_MECHANICAL_TERMINAL_CLOSURE</code>"
          " &nbsp; <b>日期</b>：2026-08-07 &nbsp; <b>评审状态</b>："
          "<span class='hold'>%s</span></p>"
          % esc(gate.get("review_status", "?")))
        A("<div class='box'><b>机器裁决</b><br>%s</div>"
          % "<br>".join("<code>%s</code>" % esc(v)
                        for v in gate.get("verdict", [])))
        A("<p>判据：<b>%s / %s</b> 通过。未闭合项 <b>%s</b> 条（下方第 8 节逐条列出，"
          "均<u>不</u>计为通过）。</p>"
          % (gate.get("criteria_passed"), gate.get("criteria_total"),
             len(gate.get("open_items", []))))

        # ---- 1 判据表 ----
        A("<h2>1. 判据逐条</h2><table><tr><th>判据</th><th>结果</th>"
          "<th>证据</th></tr>")
        for k, v in (gate.get("criteria") or {}).items():
            A("<tr><td><code>%s</code></td><td class='%s'>%s</td>"
              "<td><small>%s</small></td></tr>"
              % (esc(k), "pass" if v["pass"] else "fail",
                 "PASS" if v["pass"] else "FAIL",
                 esc(json.dumps(v.get("evidence"), ensure_ascii=False))[:400]))
        A("</table>")

        # ---- 2 度量权威 ----
        A("<h2>2. 度量的权威边界（先读这一节）</h2>")
        A("<div class='bad'><b>SolidWorks 原生 B-rep 干涉本轮未取得。</b><br>"
          "本机四次尝试全部失败：2 次低内存致死 RPC、1 次挂死 17 分钟、"
          "1 次低内存致死。逐条记录见 "
          "<code>05_clearance/G3A_NATIVE_ATTEMPTS.json</code>。<br>"
          "本书中所有间隙数值为 <b>CAD 网格层级</b>（镶嵌挠度 0.5 mm），"
          "<u>不是</u>原生裁决，也不得被引用为原生裁决。</div>")
        A("<table><tr><th>量</th><th>权威</th><th>说明</th></tr>")
        A("<tr><td>拓扑 / 关节轴 / 限位 / FK</td><td>accepted B601 URDF</td>"
          "<td>只读，SHA-256 <code>408147DD…A3</code></td></tr>")
        A("<tr><td>机械几何 / 间隙</td><td>B51 <b>CAD</b> 连杆</td>"
          "<td>来自哈希绑定的 G2 分配置 STEP</td></tr>")
        A("<tr><td>配合尺寸（销/孔）</td><td>OpenCascade 解析曲面</td>"
          "<td>镶嵌会把 Ø8 圆柱变成 8×8 方料，故不用网格判断</td></tr></table>")
        A("<div class='warn'><b>CAD 臂 ≠ URDF 碰撞网格。</b> 逐链接对拍（同一挂载变换、"
          "同一 q=0）偏差沿链增长：link2 1.4 mm → link6 <b>46.1 mm</b>；"
          "而 URDF 的 base_link 反而大 <b>55.8 mm</b>（保留了集成时被替换的原厂底板）。"
          "机械间隙必须用 CAD 网格算，运动学必须用 URDF，二者不可混引。</div>")

        # ---- 3 仪器自检 ----
        A("<h2>3. 离线仪器自检（先证明工具，再信结果）</h2><table>"
          "<tr><th>检查</th><th>结果</th><th>实测</th></tr>")
        for k, v in (sc.get("checks") or {}).items():
            det = {kk: vv for kk, vv in v.items()
                   if kk in ("max_abs_deviation", "max_abs_delta_mm", "roles",
                             "fk_gripper_origin_travel_mm")}
            A("<tr><td>%s</td><td class='%s'>%s</td><td><small>%s</small>"
              "</td></tr>" % (esc(k), "pass" if v.get("pass") else "fail",
                              "PASS" if v.get("pass") else "FAIL",
                              esc(json.dumps(det, ensure_ascii=False))[:200]))
        A("</table>")

        # ---- 4 干涉 ----
        A("<h2>4. G3-A 八配置干涉定位</h2>")
        A("<p>共登记 <b>3136</b> 对；判为真实（干涉或过近）<b>%s</b> 条 = "
          "同一 3 对 × 6 个 stow 系配置。</p>"
          % g3a.get("total_interference_or_too_close"))
        A("<table><tr><th>配置</th><th>臂位姿来源</th><th>筛查对</th>"
          "<th>网格评估</th><th>真实事件</th><th>最小间隙 mm</th></tr>")
        for c, v in (g3a.get("per_configuration") or {}).items():
            cls = "fail" if v.get("interference_or_too_close") else "pass"
            A("<tr><td><b>%s</b></td><td><small>%s</small></td><td>%s</td>"
              "<td>%s</td><td class='%s'>%s</td><td>%s</td></tr>"
              % (esc(c), esc(v.get("mesh_set")), v.get("pairs_screened"),
                 v.get("pairs_mesh_evaluated"), cls,
                 v.get("interference_or_too_close"), v.get("min_gap_mm")))
        A("</table>")
        A("<div class='box'><b>读法</b>：展开态与服务态<b>零干涉</b>"
          "（最小 2.714 mm，且该最小值出现在 base_link 与 Central_Boss 之间——"
          "那是螺接安装面，不是间隙缺陷）。全部真实事件集中在收拢系六个配置，"
          "且都是臂与<b>鞍座占位框</b>的贴面接触（0.001–0.319 mm）。</div>")

        # ---- 5 姿态 ----
        A("<h2>5. G3-B 姿态冻结</h2>")
        A("<div class='warn'><b>as-built 姿态 q=0 不能作控制起始点</b>："
          "joint2 与 joint3 的上限恰为 0.000°，q=0 正压在机械止挡上，"
          "关节裕度 0.0°。这是判据抓出来的，因此该姿态 runtime=false。</div>")
        A("<table><tr><th>姿态</th><th>q_deg</th><th>runtime</th>"
          "<th>关节裕度°</th><th>运动链→本体 mm</th><th>臂→翼 mm</th>"
          "<th>夹爪→本体 mm</th></tr>")
        rows = []
        for nm in ("Q_AS_BUILT_REFERENCE", "Q_STOW_ENGINEERING_CANDIDATE"):
            e = (pe.get("poses") or {}).get(nm, {})
            rows.append((nm, e, False))
        for nm in ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"):
            e = ((ps.get("results") or {}).get(nm, {}).get("chosen") or {}) \
                .get("evaluation", {})
            rows.append((nm, e, True))
        for nm, e, rt in rows:
            A("<tr><td><b>%s</b></td><td><small>%s</small></td>"
              "<td class='%s'>%s</td><td>%s</td><td>%s</td><td>%s</td>"
              "<td>%s</td></tr>"
              % (esc(nm), esc(e.get("q_deg")), "pass" if rt else "na",
                 "是" if rt else "否",
                 e.get("nearest_joint_limit_margin_deg"),
                 e.get("min_moving_link_to_bus_mm"),
                 e.get("min_arm_to_wing_mm"),
                 e.get("min_gripper_to_bus_mm")))
        A("</table>")
        hg = ((ps.get("results") or {}).get("Q_DEPLOYED_HOME", {})
              .get("chosen") or {}).get("gate", {})
        A("<h3>Q_DEPLOYED_HOME 判据</h3><table><tr><th>#</th><th>结果</th></tr>")
        for k, v in hg.items():
            cls = "pass" if v is True else ("na" if not isinstance(v, bool)
                                            else "fail")
            A("<tr><td>%s</td><td class='%s'>%s</td></tr>"
              % (esc(k), cls, esc(v)))
        A("</table>")
        A("<div class='warn'>第 9 项<b>运动链脱离本体</b>是本轮补加的。原始"
          "“臂—本体最小距离”被固定不动的 base_link 主导，三个姿态恒为 27.405 mm，"
          "对姿态不敏感，属 fail-open 指标。相机项为 "
          "<code>NOT_EVALUATED</code>，<b>不计为通过</b>。</div>")

        # ---- 6 接口 ----
        A("<h2>6. G3-C / G3-D / G4 接口与硬件</h2>")
        A("<h3>翼根（D-F3R1-06）</h3>")
        A("<div class='box'>B-rep 实测：销 <b>r=4.000 真圆柱</b>、耳孔 "
          "<b>r=4.200</b>、扭簧 r=4.2/8.0，三者严格同轴于 x 轴、|y|=143.15、z=0。"
          "翼板为 6 面平板，<b>完全没有耳片</b> —— 30.0 mm 缺口在翼板侧。<br>"
          "本轮产出接口定义 <b>%s</b> 个零件、<b>%s g</b>（双侧），状态 "
          "<span class='hold'>%s</span>。</div>"
          % (len(wr.get("parts", [])), wr.get("mass_both_sides_g"),
             esc(wr.get("status"))))
        A("<h3>G07 / G08 / Mid</h3>")
        A("<div class='box'>三个既有块经 B-rep 证实为 10 面纯平面盒，"
          "无摇篮、无垫、无定位特征 → 降级 <code>ENVELOPE_REFERENCE_ONLY</code>。<br>"
          "真实对手面由<b>网格搜索</b>找到（非 bbox 选面）：</div>")
        A("<table><tr><th>位</th><th>承托的臂件</th><th>对手面 z</th>"
          "<th>既有块顶 z</th><th>高度修正</th><th>名义间隙</th></tr>")
        for tag, s in (sup.get("supports") or {}).items():
            if s.get("status") != "DEFINED":
                A("<tr><td>%s</td><td colspan=5 class='fail'>%s</td></tr>"
                  % (esc(tag), esc(s.get("status"))))
                continue
            A("<tr><td><b>%s</b></td><td><small>%s</small></td><td>%s</td>"
              "<td>%s</td><td>%+.3f</td><td>%s mm</td></tr>"
              % (esc(tag), esc(s["supported_arm_part"]),
                 s["counterface_z_mm"], s["existing_block_top_z_mm"],
                 s["required_height_change_mm"], s["nominal_gap_mm"]))
        A("</table>")
        A("<h3>G4 成熟度</h3><table><tr><th>项</th><th>状态</th></tr>")
        for k, v in (g4.get("maturity_summary") or {}).items():
            A("<tr><td>%s</td><td class='hold'>%s</td></tr>"
              % (esc(k), esc(v)))
        A("</table>")
        A("<div class='bad'><b>夹爪</b>：CAD 中是<b>单一实体</b>，"
          "accepted URDF 声明两个移动指（0–71.5 mm）。本轮<b>不</b>把这个单实体"
          "当作可动双指展示；所有夹爪间隙仅对该闭合外观实体成立，"
          "<b>张开态未验证</b>。</div>")

        # ---- 7 路径 ----
        A("<h2>7. G5 连续路径</h2>")
        if g5:
            A("<table><tr><th>路径段</th><th>状态</th><th>样本</th>"
              "<th>最差 mm</th><th>通过</th></tr>")
            for key in ("official_path", "engineering_path"):
                for s in g5.get(key, []):
                    if not s.get("swept"):
                        A("<tr><td>%s</td><td class='na' colspan=4>%s</td>"
                          "</tr>" % (esc(s["segment"]), esc(s["status"])))
                    else:
                        A("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                          "<td class='%s'>%s</td></tr>"
                          % (esc(s["segment"]), esc(s["status"]),
                             s.get("samples"), s.get("worst_critical_mm"),
                             "pass" if s.get("pass") else "fail",
                             s.get("pass")))
            A("</table>")
            A("<div class='box'>%s</div>"
              % esc(json.dumps(g5.get("summary"), ensure_ascii=False)))
        else:
            A("<p class='fail'>G5 结果缺失。</p>")

        # ---- 8 未闭合项 ----
        A("<h2>8. 未闭合项（逐条，均不计为通过）</h2><table>"
          "<tr><th>ID</th><th>项</th><th>原因</th><th>阻断了什么</th></tr>")
        for o in gate.get("open_items", []):
            A("<tr><td><b>%s</b></td><td>%s</td><td><small>%s</small></td>"
              "<td><small>%s</small></td></tr>"
              % (esc(o["id"]), esc(o["item"]), esc(o.get("why")),
                 esc(o.get("blocks"))))
        A("</table>")

        # ---- 9 质量 ----
        A("<h2>9. G6 外部质量预算</h2>")
        b = (dt.get("mass_budget") or {})
        A("<p>合计 <b>%s g</b>（范围 %s – %s g）。来源层级：tier-3 CAD 体积×密度 "
          "%s g，tier-4 类别估计 %s g。<b>无</b>实测、<b>无</b>厂商确认值。"
          "accepted 臂质量惯量<b>未修改</b>。</p>"
          % (b.get("total_g"), b.get("min_estimate_g"), b.get("max_estimate_g"),
             b.get("tier3_cad_volume_g"), b.get("tier4_estimate_g")))
        A("<table><tr><th>分组</th><th>g</th></tr>")
        for g, m in (b.get("by_group_g") or {}).items():
            A("<tr><td>%s</td><td>%s</td></tr>" % (esc(g), m))
        A("</table>")

        # ---- 10 截图 ----
        A("<h2>10. 见证截图</h2>")
        A("<p>渲染的是<b>实际被测量的几何</b>，姿态由与间隙分析同一个相对变换施加。"
          "配色：臂=钢蓝，本体=浅灰，太阳翼=琥珀，<b>鞍座占位框=红</b>，"
          "参考体=半透明紫。</p>")
        for s in shots.get("shots", []):
            A("<figure>%s<figcaption><b>%s</b> — %s</figcaption></figure>"
              % (img(s["id"]), esc(s["id"]), esc(s.get("caption"))))

        A("<h2>11. 复现</h2><pre><code>cd 20_engineering/"
          "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/99_tools\n"
          "python r2a2_reference_audit.py     # baseline 健康\n"
          "python r2c_selfcheck.py            # 仪器自检\n"
          "python r2d_g3a_offline.py          # G3-A 八配置干涉\n"
          "python r2e_g3b_poses.py            # 基线姿态评估\n"
          "python r2f_g3b_search.py           # 姿态搜索\n"
          "python r2g_g3b_freeze.py           # 姿态冻结\n"
          "python r2h_g3c_wingroot.py         # 翼根接口\n"
          "python r2i_g3d_supports.py         # 承托件\n"
          "python r2j_g4_hdrm_camera.py       # HDRM/相机/线束/夹爪\n"
          "python r2k_g5_paths.py             # 连续路径\n"
          "python r2l_g6_thread.py            # 质量与数字线程\n"
          "python r2m_shots.py                # 截图\n"
          "python r2n_final_gate.py           # 最终 Gate\n"
          "# 原生 B-rep 干涉（需 >= 6 GB 可用内存）：\n"
          "python r2b3_g3a_chunked.py &lt;CONFIG&gt;\n"
          "</code></pre>")
        A("</body></html>")

        OUT.write_text("\n".join(H), encoding="utf-8")
        print("written:", OUT, OUT.stat().st_size, "bytes")
        print("shots embedded:", len(shots.get("shots", [])))
    except Exception:
        print(traceback.format_exc()[-2500:])
        sys.exit(1)


if __name__ == "__main__":
    main()
