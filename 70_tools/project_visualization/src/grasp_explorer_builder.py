"""VIZ-Gate 0 Stage 3 -- self-contained interactive grasp-geometry explorer.

Writes 40_evidence/artifacts/visualization/grasp_geometry_explorer_v0.html:
  * plotly.js 6.3.0 bundle INLINED (plotly.offline.get_plotlyjs, no CDN --
    the file opens fully offline; a strict scan for external references runs
    after writing);
  * the read-only geometry/evidence payload from grasp_candidate_renderer
    embedded as JSON (96 roll rows / 24 groups / 72 cases, ~80 KB);
  * controls: grasp point P1/P2/P3 x phase tc0/30/60/90 x task mode 5D/6D x
    roll slider (-90..+90 step 30) + velocity selector for the per-case panel;
  * linked panel with the TWO permanent status badges (geometry line +
    dynamics line, never merged), four-class reason coloring
    (display_semantics_v1.yaml), cond / collision margin / M_PCS /
    scenario_hash, and the 3-speed case mini-table;
  * footer: git commit, snapshot hash inventory (expandable), and the frozen
    statement "admissible 0/72, gate REPEAT_E1_5".

Semantic red line: no SAFE/UNSAFE red-green binary anywhere; UNKNOWN is not
unsafe; missing evidence is not physical unsafety; no SAFE candidate and no
Top-3 are claimed.
"""
import _viz_bootstrap as vb  # noqa: F401  (env pins BEFORE numpy)
import json
import os
import re

from plotly.offline import get_plotlyjs

import grasp_candidate_renderer as gcr

OUT_HTML = os.path.join(vb.REPO_ROOT, "artifacts", "visualization",
                        "grasp_geometry_explorer_v0.html")

# display_semantics_v1.yaml color language (kept literal here so the HTML is
# reviewable stand-alone; values match the YAML)
COLORS = {
    "PHYSICAL_LIMIT_EXCEEDED": "#c8443c",
    "FLEX_SOLVER_UNKNOWN": "#e0b400",
    "MISSING_FRESH_EVIDENCE": "#7d93b2",
    "VERIFIED_SAFE": "#4c9f70",
    "geometry_verified": "#4c9f70",
    # Geometry hard-screen failure is orange, distinct from the red reserved
    # for a numerically proven physical-limit exceedance.
    "geometry_fail": "#d97706",
    "dynamics_unverified": "#9e9e9e",
    "frame_x": "#d62728", "frame_y": "#2ca02c", "frame_z": "#1f77b4",
    "debris": "#8f8f86",
}

CLS_ZH = {
    "PHYSICAL_LIMIT_EXCEEDED": "物理超限（已有数值证明真实超限）",
    "FLEX_SOLVER_UNKNOWN": "柔性求解不可判定（ANCF 失败，无法判定）",
    "MISSING_FRESH_EVIDENCE": "证据缺失（本轮未完成动态证据计算）",
    "VERIFIED_SAFE": "已验证安全（当前为空集）",
}


def build_html():
    payload = gcr.build_payload()
    data_json = json.dumps(payload, ensure_ascii=False,
                           separators=(",", ":")).replace("</", "<\\/")
    colors_json = json.dumps(COLORS)
    cls_zh_json = json.dumps(CLS_ZH, ensure_ascii=False)
    meta = payload["meta"]
    plotlyjs = get_plotlyjs()

    snap_rows = "\n".join(
        f"<tr><td>{f['source']}</td><td class='mono'>{f['sha256']}</td></tr>"
        for f in meta["snapshot_files"])

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>E1.5 抓取候选几何浏览器 v0 — REPEAT_E1_5（admissible 0/72）</title>
<style>
 * { box-sizing: border-box; }
 body { margin:0; font-family:"Microsoft YaHei","Segoe UI",sans-serif;
        background:#f5f6f8; color:#222; }
 header { background:#243447; color:#fff; padding:10px 18px; }
 header h1 { margin:0; font-size:17px; font-weight:600; }
 header .sub { font-size:12px; color:#b8c4d4; margin-top:3px; }
 .gatebanner { display:inline-block; background:#7d93b2; color:#fff;
   border-radius:4px; padding:1px 8px; font-size:12px; margin-left:8px; }
 main { display:flex; gap:12px; padding:12px 18px; align-items:stretch; }
 #plot { flex:1 1 auto; min-width:520px; height:640px; background:#fff;
   border:1px solid #d8dde4; border-radius:6px; }
 aside { flex:0 0 400px; display:flex; flex-direction:column; gap:10px; }
 .card { background:#fff; border:1px solid #d8dde4; border-radius:6px;
   padding:10px 12px; }
 .card h2 { margin:0 0 8px 0; font-size:13px; color:#243447; }
 .ctlrow { display:flex; gap:6px; align-items:center; margin-bottom:7px;
   flex-wrap:wrap; }
 .ctlrow label { font-size:12px; color:#555; width:64px; flex:none; }
 .seg { display:flex; gap:4px; flex-wrap:wrap; }
 .seg button { border:1px solid #b9c2cc; background:#eef1f4; color:#333;
   border-radius:4px; padding:3px 10px; font-size:12px; cursor:pointer; }
 .seg button.on { background:#243447; color:#fff; border-color:#243447; }
 input[type=range] { flex:1; }
 .badge { display:block; border-radius:4px; padding:6px 9px; font-size:12.5px;
   color:#fff; margin-bottom:6px; line-height:1.45; }
 table.kv { width:100%; border-collapse:collapse; font-size:12px; }
 table.kv td { padding:2.5px 4px; border-bottom:1px solid #eef0f3;
   vertical-align:top; }
 table.kv td:first-child { color:#666; width:118px; }
 .mono { font-family:Consolas,monospace; font-size:11px; }
 table.spd { width:100%; border-collapse:collapse; font-size:11.5px;
   margin-top:4px; }
 table.spd th, table.spd td { padding:3px 5px; border-bottom:1px solid #eef0f3;
   text-align:left; }
 table.spd tr.cur { outline:2px solid #243447; }
 .chip { display:inline-block; width:10px; height:10px; border-radius:2px;
   margin-right:4px; vertical-align:-1px; }
 footer { padding:10px 18px 18px; font-size:11.5px; color:#555; }
 footer table { border-collapse:collapse; font-size:10.5px; }
 footer td { padding:1.5px 8px 1.5px 0; border-bottom:1px solid #e3e6ea; }
 details summary { cursor:pointer; color:#243447; font-weight:600; }
 .note { font-size:11px; color:#777; margin-top:4px; line-height:1.5; }
 .legend { font-size:11.5px; line-height:1.7; }
</style>
</head>
<body>
<header>
 <h1>E1.5 抓取候选几何浏览器 v0
   <span class="gatebanner">gate REPEAT_E1_5 · admissible 0/72</span></h1>
 <div class="sub">几何证据（快照只读）交互查看 —— 四类科学原因着色，非 SAFE/UNSAFE 红绿二分；
   UNKNOWN ≠ 不安全，证据缺失 ≠ 物理不安全；本轮不存在“已验证安全”候选，亦无 Top-3。</div>
</header>
<main>
 <div id="plot"></div>
 <aside>
  <div class="card">
   <h2>工况选择</h2>
   <div class="ctlrow"><label>抓取点</label><div class="seg" id="segP"></div></div>
   <div class="ctlrow"><label>捕获相位</label><div class="seg" id="segT"></div></div>
   <div class="ctlrow"><label>任务模式</label><div class="seg" id="segM"></div></div>
   <div class="ctlrow"><label>接近速度</label><div class="seg" id="segV"></div></div>
   <div class="ctlrow"><label>roll 滑条</label>
     <input type="range" id="roll" min="-90" max="90" step="30" value="0">
     <span id="rollVal" class="mono" style="width:118px"></span></div>
   <div class="note" id="rollNote"></div>
  </div>
  <div class="card">
   <h2>状态徽章（两行恒显）</h2>
   <span class="badge" id="badgeGeom"></span>
   <span class="badge" id="badgeDyn"></span>
  </div>
  <div class="card">
   <h2>联动数据面板（快照只读）</h2>
   <table class="kv" id="kv"></table>
   <table class="spd" id="spd"></table>
   <div class="note">三速度行均为同一几何组；格前色块 = 科学原因四分类。</div>
  </div>
  <div class="card legend" id="legend"></div>
 </aside>
</main>
<footer>
 <div>git commit <span class="mono">__COMMIT__</span> ·
   E1.5 evidence source_commit <span class="mono">__SRC_COMMIT__</span> ·
   数据目录 <span class="mono">__SNAPDIR__</span> ·
   重算分类 3/3/66/0 · <b>admissible 0/72, gate REPEAT_E1_5</b></div>
 <div class="note">目标姿态旋转为恒角速度模型；转轴 [1, 0.15, 0.4] @ 3 deg/s 为
   <b>E1 context</b>（E1.5 快照未重申该值，对 E1.5 属证据缺失）。
   debris 简化体 Ø1.32 m × 2.5 m（端环 z=±0.95 m）。
   B601 末端位置由快照 selected_q_json 经 sim_05 b601_model FK 计算（只读导入，8 行全部命中捕获点 &lt;2 mm）。</div>
 <details><summary>快照哈希清单（22 个 E1.5 证据文件，SHA-256）</summary>
  <table><tr><th style="text-align:left">source path</th><th style="text-align:left">sha256</th></tr>
__SNAP_ROWS__
  </table>
 </details>
</footer>
<script>__PLOTLYJS__</script>
<script>
"use strict";
const DATA = __DATA__;
const C = __COLORS__;
const CLS_ZH = __CLS_ZH__;

const state = { pid:"P1", tc:0, mode:"pose_6d", v:5, roll:0 };

// ------------------------------------------------ small linear algebra
function xform(T, p) {
  return [T[0][0]*p[0]+T[0][1]*p[1]+T[0][2]*p[2]+T[0][3],
          T[1][0]*p[0]+T[1][1]*p[1]+T[1][2]*p[2]+T[1][3],
          T[2][0]*p[0]+T[2][1]*p[1]+T[2][2]*p[2]+T[2][3]];
}
function fmt(x, d) { return (x===null||x===undefined) ? "—（无记录）" : x.toFixed(d); }

function groupKey() { return state.pid + "|tc=" + state.tc + "|" + state.mode; }
function caseId(v) {
  const t = ("0"+state.tc).slice(-2);
  return state.pid + "_tc" + t + "_v" + (v||state.v) + "mm_" + state.mode;
}
function rollRow() {
  const g = DATA.groups[groupKey()];
  if (state.mode === "approach_5d") return g.rolls[0];      // UNCONSTRAINED single row
  return g.rolls.find(r => Math.abs(r.roll - state.roll) < 1e-6) || g.rolls[0];
}

// ------------------------------------------------ traces
function dashedSegments(p0, dir, halfLen, nDash) {
  const xs=[], ys=[], zs=[];
  for (let i=0;i<nDash;i++) {
    const a = -halfLen + (2*halfLen)*(i/nDash);
    const b = a + (2*halfLen)/(nDash*1.8);
    xs.push(p0[0]+a*dir[0], p0[0]+b*dir[0], null);
    ys.push(p0[1]+a*dir[1], p0[1]+b*dir[1], null);
    zs.push(p0[2]+a*dir[2], p0[2]+b*dir[2], null);
  }
  return {x:xs, y:ys, z:zs};
}

function buildTraces() {
  const pl = DATA.placements[state.pid + "|" + state.tc];
  const T = pl.T_S_D;
  const row = rollRow();
  const traces = [];

  // debris cylinder (simplified body, SSOT dims)
  const V = DATA.debris.verts.map(p => xform(T, p));
  traces.push({type:"mesh3d",
    x:V.map(p=>p[0]), y:V.map(p=>p[1]), z:V.map(p=>p[2]),
    i:DATA.debris.faces.map(f=>f[0]), j:DATA.debris.faces.map(f=>f[1]),
    k:DATA.debris.faces.map(f=>f[2]),
    color:C.debris, opacity:0.35, flatshading:true, hoverinfo:"skip",
    lighting:{ambient:0.55, diffuse:0.6, specular:0.05},
    name:"debris Ø1.32×2.5 m", showlegend:false});

  // rim rings at z = ±0.95 (grasp rims)
  for (const ring of DATA.debris.rings) {
    const R = ring.map(p => xform(T, p));
    traces.push({type:"scatter3d", mode:"lines",
      x:R.map(p=>p[0]), y:R.map(p=>p[1]), z:R.map(p=>p[2]),
      line:{color:"#6b6b64", width:3}, hoverinfo:"skip", showlegend:false});
  }

  // P1/P2/P3 markers (geometry annotations, neutral grey = 动力学未着色)
  const pids = Object.keys(DATA.debris.grasp_points_D);
  const P = pids.map(k => xform(T, DATA.debris.grasp_points_D[k]));
  traces.push({type:"scatter3d", mode:"markers+text",
    x:P.map(p=>p[0]), y:P.map(p=>p[1]), z:P.map(p=>p[2]),
    text:pids, textposition:"top center", textfont:{size:11, color:"#333"},
    marker:{size:pids.map(k=>k===state.pid?8:5),
            color:pids.map(k=>k===state.pid?"#243447":"#9e9e9e"),
            symbol:"circle", line:{color:"#fff", width:1}},
    hovertemplate:"%{text}<extra></extra>", showlegend:false});

  // grasp local frame triad at the commanded grasp point (roll applied)
  const p = row.p_S, L = 0.30;
  const axes = [["x", C.frame_x], ["y", C.frame_y], ["z", C.frame_z]];
  for (const [ax, col] of axes) {
    const d = row.triad[ax];
    traces.push({type:"scatter3d", mode:"lines+text",
      x:[p[0], p[0]+L*d[0]], y:[p[1], p[1]+L*d[1]], z:[p[2], p[2]+L*d[2]],
      line:{color:col, width:5},
      text:["", ax+"_G"], textfont:{size:10, color:col},
      hoverinfo:"skip", showlegend:false});
  }

  // approach arrow: chaser closes along -z_G (outward normal reversed)
  const n = row.triad.z;
  traces.push({type:"scatter3d", mode:"lines",
    x:[p[0]+0.60*n[0], p[0]+0.16*n[0]],
    y:[p[1]+0.60*n[1], p[1]+0.16*n[1]],
    z:[p[2]+0.60*n[2], p[2]+0.16*n[2]],
    line:{color:"#243447", width:6}, hoverinfo:"skip", showlegend:false});
  traces.push({type:"cone",
    x:[p[0]+0.16*n[0]], y:[p[1]+0.16*n[1]], z:[p[2]+0.16*n[2]],
    u:[-0.14*n[0]], v:[-0.14*n[1]], w:[-0.14*n[2]],
    sizemode:"absolute", sizeref:0.09, anchor:"tip",
    colorscale:[[0,"#243447"],[1,"#243447"]], showscale:false,
    hoverinfo:"skip", name:"approach"});

  // tumble axis through target CoM (E1 context, dashed by segments)
  const seg = dashedSegments(pl.com_S, pl.axis_S, 1.65, 26);
  traces.push({type:"scatter3d", mode:"lines", x:seg.x, y:seg.y, z:seg.z,
    line:{color:"#7d93b2", width:3}, hoverinfo:"skip", showlegend:false});
  traces.push({type:"scatter3d", mode:"text",
    x:[pl.com_S[0]+1.7*pl.axis_S[0]], y:[pl.com_S[1]+1.7*pl.axis_S[1]],
    z:[pl.com_S[2]+1.7*pl.axis_S[2]],
    text:["tumble axis (E1 context)"], textfont:{size:10, color:"#7d93b2"},
    hoverinfo:"skip", showlegend:false});

  // capture point (evaluator scenario constant)
  const cp = DATA.meta.capture_point_S;
  traces.push({type:"scatter3d", mode:"markers+text",
    x:[cp[0]], y:[cp[1]], z:[cp[2]], text:["capture point S"],
    textposition:"bottom center", textfont:{size:9, color:"#7d93b2"},
    marker:{size:5, symbol:"cross", color:"#7d93b2"},
    hovertemplate:"capture_point_S [0.95, 0, −0.10] m<extra></extra>",
    showlegend:false});

  // B601 end-effector position (FK of snapshot selected_q; only when a q exists)
  if (row.ee_S) {
    traces.push({type:"scatter3d", mode:"markers+text",
      x:[row.ee_S[0]], y:[row.ee_S[1]], z:[row.ee_S[2]],
      text:["B601 EE (FK)"], textposition:"top right",
      textfont:{size:10, color:C.geometry_verified},
      marker:{size:7, symbol:"diamond", color:C.geometry_verified,
              line:{color:"#1c4a2e", width:1}},
      hovertemplate:"B601 末端 FK(selected_q)<br>[%{x:.3f}, %{y:.3f}, %{z:.3f}] m"+
                    "<extra></extra>", showlegend:false});
  }

  // servicer body frame S triad at origin (context)
  for (const [i,[ax,col]] of axes.entries()) {
    const d = [0,0,0]; d[i] = 0.25;
    traces.push({type:"scatter3d", mode:"lines+text",
      x:[0,d[0]], y:[0,d[1]], z:[0,d[2]], line:{color:col, width:3},
      text:["", ax+"_S"], textfont:{size:9, color:col},
      hoverinfo:"skip", showlegend:false});
  }
  return traces;
}

const LAYOUT = {
  margin:{l:0, r:0, t:6, b:0},
  paper_bgcolor:"#ffffff",
  uirevision:"keep",
  scene:{
    aspectmode:"data",
    xaxis:{title:"X_S [m]", showspikes:false},
    yaxis:{title:"Y_S [m]", showspikes:false},
    zaxis:{title:"Z_S [m]", showspikes:false},
    camera:{eye:{x:1.55, y:1.15, z:0.75}},
  },
  showlegend:false,
};

// ------------------------------------------------ panel
function chip(cls) {
  return '<span class="chip" style="background:'+C[cls]+'"></span>';
}
function render() {
  const g = DATA.groups[groupKey()];
  const row = rollRow();
  const cs = DATA.cases[caseId()];

  // roll slider notes
  const rollVal = document.getElementById("roll");
  rollVal.disabled = (state.mode === "approach_5d");
  document.getElementById("rollVal").textContent =
    (state.mode === "approach_5d") ? "（无约束）"
      : "candidate " + state.roll + "°";
  document.getElementById("rollNote").innerHTML =
    (state.mode === "approach_5d")
      ? "approach_5d：roll 无约束（单条 UNCONSTRAINED 记录，realized "
        + fmt(row.realized_roll,1) + "°）；滑条停用。"
      : "roll 为绕外法线 +z_G 的候选角（E1.5 冻结约定）；realized = "
        + fmt(row.realized_roll,1) + "°（快照记录值）。";

  // badges: geometry line + dynamics line, ALWAYS both
  const bg = document.getElementById("badgeGeom");
  if (row.feasible) {
    bg.style.background = C.geometry_verified;
    bg.innerHTML = "① 几何已验证 — IK/碰撞/条件数/关节裕度硬筛通过（该 roll 候选）";
  } else {
    bg.style.background = C.geometry_fail;
    bg.innerHTML = "① 几何未通过硬筛 — IK_FAIL：该相位/朝向 B601 不可达（几何事实）";
  }
  const bd = document.getElementById("badgeDyn");
  bd.style.background = C[cs.recount_class];
  const dynText = {
    PHYSICAL_LIMIT_EXCEEDED:
      "② 动力学已计算：数值超限 — post-capture rate "+fmt(cs.rate_dps,3)+
      " deg/s > 2.0（暂行阈值，margin "+fmt(cs.rate_margin,2)+"）",
    FLEX_SOLVER_UNKNOWN:
      "② 动力学不可判定 — ANCF 求解失败（UNKNOWN ≠ 不安全）",
    MISSING_FRESH_EVIDENCE:
      "② 动力学尚未验证 — 本轮无新鲜证据（证据缺失 ≠ 物理不安全）",
  };
  bd.innerHTML = dynText[cs.recount_class] ||
    "② 动力学尚未验证 — 无新鲜证据";

  // key-value panel
  const kv = [
    ["几何组", groupKey()],
    ["组选择状态", g.selection_status +
      (g.selection_status==="SELECTED" ? "（selected roll "+g.selected_roll+"°）" : "")],
    ["roll 候选状态", row.feasible ? (row.roll_status+" · 硬筛通过") : "IK_FAIL（不可达）"],
    ["cond(J)", fmt(row.cond,2)],
    ["collision margin", row.coll_margin_m===null ? "—（无记录）"
       : fmt(row.coll_margin_m,4)+" m"],
    ["joint margin", row.joint_margin_rad===null ? "—（无记录）"
       : fmt(row.joint_margin_rad,3)+" rad"],
    ["M_PCS (E1.5)", cs.mpcs===null ? "—（无，未形成完整证据）" : fmt(cs.mpcs,3)],
    ["当前工况", caseId()],
    ["e15_state（原始）", cs.e15_state_raw + " → 重算类：" + CLS_ZH[cs.recount_class]],
    ["scenario_hash（case）", "<span class='mono'>"+cs.hash+"</span>"],
    ["scenario_hash（roll 候选）", "<span class='mono'>"+row.hash+"</span>"],
    ["B601 末端", row.ee_S ? ("FK 有效 ["+row.ee_S.map(v=>v.toFixed(3)).join(", ")+"] m")
       : "无（该候选无可行 q，IK_FAIL）"],
  ];
  document.getElementById("kv").innerHTML =
    kv.map(([k,v]) => "<tr><td>"+k+"</td><td>"+v+"</td></tr>").join("");

  // speed mini-table (all three speeds of this geometry group)
  let rows = "<tr><th>v</th><th>工况</th><th>分类</th><th>hash</th></tr>";
  for (const v of [5,10,20]) {
    const c = DATA.cases[caseId(v)];
    rows += "<tr class='"+(v===state.v?"cur":"")+"'>"+
      "<td>"+v+" mm/s</td><td class='mono'>"+caseId(v)+"</td>"+
      "<td>"+chip(c.recount_class)+c.recount_class+"</td>"+
      "<td class='mono'>"+c.hash.slice(0,8)+"…</td></tr>";
  }
  document.getElementById("spd").innerHTML = rows;

  Plotly.react("plot", buildTraces(), LAYOUT, {displaylogo:false, responsive:true});
}

// ------------------------------------------------ controls
function seg(id, opts, key, fmtLabel) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  for (const o of opts) {
    const b = document.createElement("button");
    b.textContent = fmtLabel(o);
    b.dataset.v = o;
    if (String(state[key]) === String(o)) b.classList.add("on");
    b.onclick = () => {
      state[key] = (typeof o === "number") ? Number(o) : o;
      for (const x of el.children) x.classList.remove("on");
      b.classList.add("on");
      render();
    };
    el.appendChild(b);
  }
}
seg("segP", ["P1","P2","P3"], "pid", o=>o);
seg("segT", [0,30,60,90], "tc", o=>"t_c="+o+" s");
seg("segM", ["pose_6d","approach_5d"], "mode",
    o=>o==="pose_6d"?"6D 位姿":"5D 接近");
seg("segV", [5,10,20], "v", o=>o+" mm/s");
document.getElementById("roll").oninput = e => {
  state.roll = Number(e.target.value); render();
};

// legend card
document.getElementById("legend").innerHTML =
  "<h2 style='margin:0 0 6px;font-size:13px;color:#243447'>四类科学原因（重算 3/3/66/0）</h2>" +
  Object.keys(CLS_ZH).map(k =>
    chip(k)+"<b>"+k+"</b>"+(k==="VERIFIED_SAFE"?"（空集，仅图例声明）":"")+
    "<br><span style='color:#666'>"+CLS_ZH[k]+"</span>").join("<br>");

render();
</script>
</body>
</html>
"""
    html = (html
            .replace("__PLOTLYJS__", plotlyjs)
            .replace("__DATA__", data_json)
            .replace("__COLORS__", colors_json)
            .replace("__CLS_ZH__", cls_zh_json)
            .replace("__COMMIT__", meta["git_commit"])
            .replace("__SRC_COMMIT__", meta["e15_source_commit"][:12])
            .replace("__SNAPDIR__", meta["snapshot_dir"])
            .replace("__SNAP_ROWS__", snap_rows))

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    size_mb = os.path.getsize(OUT_HTML) / 1e6

    # -------- self-containment scan: no external fetch targets allowed ----
    ext = []
    for pat in (r'<script[^>]+src\s*=\s*["\']([^"\']+)',
                r'<link[^>]+href\s*=\s*["\'](https?://[^"\']+)',
                r'<img[^>]+src\s*=\s*["\'](https?://[^"\']+)',
                r'@import\s+url\(["\']?(https?://[^"\')]+)',
                r'url\(["\']?(https?://[^"\')]+)'):
        ext += re.findall(pat, html)
    report = {
        "path": OUT_HTML, "size_mb": round(size_mb, 2),
        "external_refs": ext, "self_contained": not ext,
        "payload_kb": round(len(data_json) / 1024),
    }
    return report


if __name__ == "__main__":
    rep = build_html()
    for k, v in rep.items():
        print(f"{k}: {v}")
    assert rep["self_contained"], "external references found!"
