#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_layout_svg.py — F4R1 工作包 C1 阶段 2D 布局图渲染脚本
================================================================
generated_at : 2026-08-27  (固定字面量, 保证逐字节确定性重跑)
status       : DESIGN_RESEARCH_CANDIDATE
data sources (只读, 与本脚本同目录):
  - EQUIPMENT_LIST_V1.yaml      (40 行设备: pos_mm / envelope_mm / bay / mass_g / status)
  - MASS_BUDGET_V1.csv          (质量预算行与两口径总计)
  - CG_INERTIA_CHECK_V1.json    (三场景 CG / CDS 包络 / CDS 变体质量核算)

输出 (同目录):
  - LAYOUT_SIDE_VIEW_V1.svg   侧视图: x-z 平面 (见下"视图平面选择")
  - LAYOUT_FRONT_VIEW_V1.svg  前视图: y-z 平面 (从 +x 任务端看入)
  - LAYOUT_BAY_MASS_V1.svg    三舱质量分配条形图 (DESIGN_POINT vs CDS_VARIANT)

依赖: 仅 Python 标准库. YAML 由本文件内置的定向行解析器解析
(不依赖 pyyaml; 解析器只覆盖 EQUIPMENT_LIST_V1 这一已知 schema:
顶层标量 / bay_bounds_mm 映射 / bus_x_span_mm 列表 / equipment 平铺字典列表).

----------------------------------------------------------------------------
坐标映射与视图平面选择 (S frame: 原点=12U几何中心, x=纵轴 +x 朝任务/臂, 单位 mm)
----------------------------------------------------------------------------
* 侧视图 = x-z 平面 (从 -y 侧向 +y 看入): 屏幕右 = +x, 屏幕上 = +z.
  选择理由: 三舱分界面均为 x=常数平面、臂基座站位 x=208.0 为 x 轴事实,
  x-y / x-z 两平面表达能力等价; 但帆板与 B601 的 C01 CG 在 y 向达 ±346.6 /
  -175.7 mm (超出 226.3 外包络), x-y 平面会把总线压缩到小比例; x-z 平面内
  全部 40 行投影都在外包络附近, 比例可读. 已知代价: 左右帆板在 x-z 投影
  重合, B601 的 y 向偏置不可见 —— 均登记于 README 局限节.
* 前视图 = y-z 平面 (从 +x 任务端向 -x 看入): 右手系 e_x × e_y = e_z,
  x 指向观察者时屏幕右 = +y, 屏幕上 = +z.
* SVG 像素映射: px = (mm - min_mm) * PX_PER_MM + margin; y 向取反 (z 向上).

----------------------------------------------------------------------------
比例 / 颜色 / 线型常量区
----------------------------------------------------------------------------
"""

import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

# ----------------------------- 常量区 -----------------------------
GENERATED_AT = "2026-08-27"
STATUS = "DESIGN_RESEARCH_CANDIDATE"

PX_PER_MM_SIDE = 1.6     # 侧视图比例: 1 mm = 1.6 px (x 向跨度含 B601 展开包络 ~870 mm)
PX_PER_MM_FRONT = 1.8    # 前视图比例: 1 mm = 1.8 px (y 向含帆板展开 CG ±346.6 mm)
MARGIN_PX = 96.0         # 图面四周留白 (放标签/标尺/题注)

FONT = "Microsoft YaHei, SimHei, Arial, sans-serif"

# 设备状态 -> 线型/填充 (图例在每张图右上角说明)
STATUS_STYLE = {
    "FROZEN_REF": {"stroke": "#444444", "dash": "7 3",   "fill": "#e8e8e8", "fill_op": 0.55},
    "CANDIDATE":  {"stroke": "#1a6fb5", "dash": "",      "fill": "#cfe4f7", "fill_op": 0.85},
    "ASSUMED":    {"stroke": "#b06000", "dash": "2.5 2", "fill": "#fdeacc", "fill_op": 0.85},
}
BAY_BAND = {  # 侧视图舱段背景带 (灰度, 避免与状态色冲突)
    "rear_service":  "#f6f1e7",
    "mid_avionics":  "#eef2f7",
    "front_mission": "#eef7ee",
}
BAY_COLOR = {  # 质量条形图舱段配色
    "front_mission":   "#7fb069",
    "mid_avionics":    "#4f81bd",
    "rear_service":    "#e8a33d",
    "side_deployables":"#9b7ec4",
    "distributed":     "#999999",
}
BAY_ORDER = ["front_mission", "mid_avionics", "rear_service", "side_deployables", "distributed"]
CG_A_COLOR = "#111111"     # 场景 A 主口径 CG
CG_B_COLOR = "#777777"     # 场景 B 上限 CG
CG_CDS_COLOR = "#c0392b"   # CDS 变体 CG (fail)
CDS_BOX_COLOR = "#c0392b"
ARM_BASE_COLOR = "#8B0000"

LABEL_FONT = 7.5
TINY_FONT = 6.5

SRC_YAML = "EQUIPMENT_LIST_V1.yaml"
SRC_CSV = "MASS_BUDGET_V1.csv"
SRC_JSON = "CG_INERTIA_CHECK_V1.json"

HERE = Path(__file__).resolve().parent


# ----------------------------- 数据解析 -----------------------------
def _parse_vec(text):
    """'[a, b, c]' -> [float, ...]; 失败返回 None."""
    m = re.match(r"^\s*\[(.*)\]\s*$", text)
    if not m:
        return None
    try:
        return [float(t.strip()) for t in m.group(1).split(",") if t.strip() != ""]
    except ValueError:
        return None


def parse_equipment_yaml(path):
    """EQUIPMENT_LIST_V1 schema 定向解析 (无 pyyaml 依赖, 见文件头注释)."""
    data = {"bay_bounds_mm": {}, "bus_x_span_mm": None, "equipment": []}
    cur = None
    section = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("#") or raw.strip() == "" or raw.strip() == "---":
            continue
        if re.match(r"^bay_bounds_mm:\s*$", raw):
            section = "bay_bounds"; continue
        if re.match(r"^equipment:\s*$", raw):
            section = "equipment"; continue
        m = re.match(r"^bus_x_span_mm:\s*(\[.*\])\s*$", raw)
        if m:
            data["bus_x_span_mm"] = _parse_vec(m.group(1)); section = None; continue
        m = re.match(r"^bus_length_note:\s*\"?(.*?)\"?\s*$", raw)
        if m:
            data["bus_length_note"] = m.group(1); section = None; continue
        if raw and not raw.startswith(" ") and not raw.startswith("\t"):
            section = None  # 其他顶层键 (title/units/...) 不需要
        if section == "bay_bounds":
            m = re.match(r"^\s+(\w+):\s*(\[.*\])\s*$", raw)
            if m:
                data["bay_bounds_mm"][m.group(1)] = _parse_vec(m.group(2))
            continue
        if section == "equipment":
            m = re.match(r"^\s{2}-\s+id:\s*(\S+)\s*$", raw)
            if m:
                cur = {"id": m.group(1)}
                data["equipment"].append(cur)
                continue
            m = re.match(r"^\s{4}(\w+):\s*(.*)$", raw)
            if m and cur is not None:
                cur[m.group(1)] = m.group(2).strip()
    # 字段规整: 数字字段转 float / vec, 失败记 None (由调用方登记跳过)
    for row in data["equipment"]:
        for k in ("mass_g",):
            try:
                row[k] = float(row.get(k, "nan"))
            except ValueError:
                row[k] = None
        for k in ("envelope_mm", "pos_mm"):
            v = row.get(k)
            row[k] = _parse_vec(v) if isinstance(v, str) else None
        row.setdefault("bay", None)
        row.setdefault("status", "UNKNOWN")
    return data


def parse_mass_csv(path):
    rows = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["line_id"]] = {
                "mass_kg": float(r["mass_kg"]),
                "status": r["status"],
                "item": r["item"],
                "category": r["category"],
            }
    return rows


def load_cg(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_12(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


# ----------------------------- 数值格式规则 -----------------------------
# 所有工程数字直接由源文件读出后按下列确定性规则格式化, 禁止手填.
def fmt_g(m):    # 质量(克)标签规则: %.6g
    return "%.6g" % m

def fmt_kg(m):   # 质量(千克)标签规则: %.6g
    return "%.6g" % m

def fmt_mm(v):   # 坐标/尺寸标签规则: %.6g
    return "%.6g" % v

def fmt_pct(x):  # 百分比标签规则: %.1f%%
    return "%.1f%%" % (100.0 * x)


def fmt_pos(v):  # data-* 属性中的坐标: 原样 str(float), 与 yaml 全精度一致
    return ",".join(str(x) for x in v)


# ----------------------------- SVG 基元 -----------------------------
class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, stroke, sw=1.0, fill="none", fill_op=1.0, dash="", extra=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
                 f'stroke="{stroke}" stroke-width="{sw}" fill="{fill}" fill-opacity="{fill_op}"{d}{extra}/>')

    def line(self, x1, y1, x2, y2, stroke, sw=1.0, dash="", marker_end=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        me = f' marker-end="url(#{marker_end})"' if marker_end else ""
        self.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}{me}/>')

    def text(self, x, y, s, size=10.0, anchor="start", fill="#111111", weight="normal", rotate=None):
        rot = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate is not None else ""
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-family="{FONT}" font-size="{size}" '
                 f'text-anchor="{anchor}" fill="{fill}" font-weight="{weight}"{rot}>{escape(s)}</text>')

    def circle(self, cx, cy, r, stroke, sw=1.0, fill="none"):
        self.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" stroke="{stroke}" '
                 f'stroke-width="{sw}" fill="{fill}"/>')

    def render(self, title, header_comment):
        defs = (
            '<defs>'
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="#111111"/></marker>'
            '<pattern id="marginHatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
            '<rect width="6" height="6" fill="#f3e2c7"/><line x1="0" y1="0" x2="0" y2="6" stroke="#c08a3e" stroke-width="1.4"/></pattern>'
            '<pattern id="distHatch" width="7" height="7" patternTransform="rotate(-45)" patternUnits="userSpaceOnUse">'
            '<rect width="7" height="7" fill="#f4f4f4"/><line x1="0" y1="0" x2="0" y2="7" stroke="#bbbbbb" stroke-width="1"/></pattern>'
            '</defs>'
        )
        body = "\n  ".join(self.parts)
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<!-- {escape(header_comment)} -->\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w:.0f}" height="{self.h:.0f}" '
            f'viewBox="0 0 {self.w:.0f} {self.h:.0f}">\n'
            f'  <title>{escape(title)}</title>\n  {defs}\n'
            f'  <rect x="0" y="0" width="{self.w:.0f}" height="{self.h:.0f}" fill="#ffffff"/>\n'
            f'  {body}\n</svg>\n'
        )


def est_text_w(s, size):
    """确定性文本宽度估计 (CJK≈1.0em, 其他≈0.56em), 仅用于标签防重叠."""
    return sum(1.0 if ord(c) > 127 else 0.56 for c in s) * size


def place_labels(labels):
    """确定性标签纵向防重叠: 按输入顺序, 与已放置框重叠则每次上移 9px (至多 24 次)."""
    placed = []
    for lab in labels:
        x, y = lab["x"], lab["y"]
        w = est_text_w(lab["s"], lab["size"]) / (2 if lab.get("anchor") == "middle" else 1)
        for _ in range(24):
            box = (x - w, y - lab["size"], x + w, y + 1.5)
            if not any(not (box[2] < p[0] or box[0] > p[2] or box[3] < p[1] or box[1] > p[3]) for p in placed):
                break
            y -= 9.0
        placed.append((x - w, y - lab["size"], x + w, y + 1.5))
        lab["y"] = y
    return labels


def header_comment():
    return (f"generated_by=render_layout_svg.py; generated_at={GENERATED_AT}; status={STATUS}; "
            f"sources={SRC_YAML}+{SRC_CSV}+{SRC_JSON}; unit=mm; frame=S")


# ----------------------------- 公共数据准备 -----------------------------
def extract_arm_base_x(eq_rows):
    """臂基座 x=208.0 冻结值从 FRZ-B601 的 notes/mounting_face 文本中正则提取
    (该值在源文件中无结构化字段, 仅以 frame 事实文本存在; 提取失败即报错, 禁止手填)."""
    for row in eq_rows:
        if row["id"] == "FRZ-B601":
            for field in (row.get("notes", ""), row.get("mounting_face", "")):
                m = re.search(r"x\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*mm", field)
                if m:
                    return float(m.group(1))
                m = re.search(r"arm_base_x([0-9]+(?:\.[0-9]+)?)", field)
                if m:
                    return float(m.group(1))
    raise RuntimeError("arm base x not found in FRZ-B601 notes/mounting_face —— 源文件缺 frame 事实, 停止")


def prepare(eq, csv_rows, cg):
    """返回 (rows_draw, rows_skip_distributed, rows_skip_bad, meta)."""
    draw, dist, bad = [], [], []
    for row in eq["equipment"]:
        if row["pos_mm"] is None or row["envelope_mm"] is None or row["mass_g"] is None:
            bad.append((row["id"], "pos_mm/envelope_mm/mass_g 缺失或不可解析"))
            continue
        if len(row["pos_mm"]) != 3 or len(row["envelope_mm"]) != 3:
            bad.append((row["id"], "pos_mm/envelope_mm 维度 != 3"))
            continue
        if row["bay"] not in BAY_ORDER:
            bad.append((row["id"], f"bay 值未登记: {row['bay']}"))
            continue
        if row["bay"] == "distributed":
            dist.append(row)  # 分布式行: 几何视图中作背景阴影层 + 角注, 不单画色块
            continue
        draw.append(row)
    arm_x = extract_arm_base_x(eq["equipment"])
    bus = next(r for r in eq["equipment"] if r["id"] == "FRZ-BUS")
    half_cross = bus["envelope_mm"][1] / 2.0  # 226.3/2; [1]==[2] 由源文件保证
    meta = {
        "arm_x": arm_x, "half_cross": half_cross,
        "bus_span": eq["bus_x_span_mm"], "bay_bounds": eq["bay_bounds_mm"],
        "cds_env": cg["scenarios"]["SCENARIO_A_CARVE_OUT_READING_A"]["cds_envelope_mm"],
        "cds_limit_kg": cg["cds_variant_mass_check"]["limit_kg"],
        "cds_margin_ok": cg["cds_variant_mass_check"]["pass"],
    }
    return draw, dist, bad, meta


def eq_group_attrs(row):
    """每行设备在 SVG 中携带 data-* 属性 (全精度源值), 供机器审计数字与源文件一致."""
    return (f' data-id="{escape(row["id"])}" data-bay="{escape(str(row["bay"]))}" '
            f'data-status="{escape(str(row["status"]))}" data-mass_g="{row["mass_g"]}" '
            f'data-pos_mm="{fmt_pos(row["pos_mm"])}" data-envelope_mm="{fmt_pos(row["envelope_mm"])}"')


def draw_eq_block(svg, row, ux, uy, label_pos="top"):
    """按状态线型画设备包络色块 + 标签; 返回标签字典(供防重叠).
    label_pos: "top"=块上方居中; "br"=块内右下角(用于 FRZ-BUS 这类近全船大块)."""
    st = STATUS_STYLE.get(row["status"], STATUS_STYLE["ASSUMED"])
    ex, ey, ez = row["envelope_mm"]
    px, py, pz = row["pos_mm"]
    x0, y0 = ux(px - ex / 2.0), uy(pz + ez / 2.0)
    w, h = ex * SCALE[0], ez * SCALE[1]
    svg.add(f'<g class="eq"{eq_group_attrs(row)}>')
    svg.rect(x0, y0, w, h, st["stroke"], sw=1.1, fill=st["fill"], fill_op=st["fill_op"], dash=st["dash"])
    svg.add('</g>')
    if label_pos == "br":
        return {"x": x0 + w - 6, "y": y0 + h - 7, "s": f'{row["id"]} {fmt_g(row["mass_g"])}g',
                "size": LABEL_FONT, "anchor": "end"}
    return {"x": x0 + w / 2.0, "y": y0 - 2.5, "s": f'{row["id"]} {fmt_g(row["mass_g"])}g',
            "size": LABEL_FONT, "anchor": "middle"}


# SCALE 全局: draw_eq_block 复用 (side: [PX_PER_MM_SIDE]*2, front: [PX_PER_MM_FRONT]*2)
SCALE = [1.0, 1.0]


def draw_scale_bar(svg, x_px, y_px, mm_len, px_per_mm):
    """比例尺: mm_len 为布局参考长度 (非工程数据)."""
    seg = mm_len * px_per_mm
    svg.line(x_px, y_px, x_px + seg, y_px, "#111111", sw=1.6)
    svg.line(x_px, y_px - 4, x_px, y_px + 4, "#111111", sw=1.6)
    svg.line(x_px + seg, y_px - 4, x_px + seg, y_px + 4, "#111111", sw=1.6)
    svg.line(x_px + seg / 2, y_px - 3, x_px + seg / 2, y_px + 3, "#111111", sw=1.0)
    svg.text(x_px, y_px + 14, "0", size=8, anchor="middle")
    svg.text(x_px + seg, y_px + 14, f"{mm_len} mm", size=8, anchor="middle")


def draw_title_block(svg, lines):
    y = 26.0
    for i, ln in enumerate(lines):
        svg.text(MARGIN_PX * 0.45, y, ln, size=13.0 if i == 0 else 8.5,
                 weight="bold" if i == 0 else "normal",
                 fill="#111111" if i == 0 else "#444444")
        y += 16.0 if i == 0 else 12.0


def draw_legend(svg, x, y, entries, title="图例 legend"):
    h = 14.0 * (len(entries) + 1) + 8
    w = max(est_text_w(t, 8) for _, t in entries + [("", title)]) + 34
    svg.rect(x, y, w, h, "#888888", sw=0.8, fill="#ffffff", fill_op=0.92)
    svg.text(x + 8, y + 13, title, size=8.5, weight="bold")
    yy = y + 26.0
    for kind, label in entries:
        if kind in STATUS_STYLE:
            st = STATUS_STYLE[kind]
            svg.rect(x + 8, yy - 7, 20, 9, st["stroke"], sw=1.0, fill=st["fill"],
                     fill_op=st["fill_op"], dash=st["dash"])
        elif kind == "cds_box":
            svg.rect(x + 8, yy - 7, 20, 9, CDS_BOX_COLOR, sw=1.2, dash="5 2.5")
        elif kind == "arm_line":
            svg.line(x + 8, yy - 2, x + 28, yy - 2, ARM_BASE_COLOR, sw=1.8, dash="8 3")
        elif kind == "cg_a":
            svg.circle(x + 18, yy - 2, 4, CG_A_COLOR, sw=1.4); svg.line(x + 12, yy - 2, x + 24, yy - 2, CG_A_COLOR, sw=1.0); svg.line(x + 18, yy - 8, x + 18, yy + 4, CG_A_COLOR, sw=1.0)
        elif kind == "cg_b":
            svg.circle(x + 18, yy - 2, 3.4, CG_B_COLOR, sw=1.2); svg.line(x + 13, yy - 2, x + 23, yy - 2, CG_B_COLOR, sw=0.9); svg.line(x + 18, yy - 7, x + 18, yy + 3, CG_B_COLOR, sw=0.9)
        elif kind == "cg_cds":
            svg.line(x + 13, yy - 7, x + 23, yy + 3, CG_CDS_COLOR, sw=1.6); svg.line(x + 13, yy + 3, x + 23, yy - 7, CG_CDS_COLOR, sw=1.6)
        elif kind == "dist_hatch":
            svg.rect(x + 8, yy - 7, 20, 9, "#aaaaaa", sw=0.8, fill="url(#distHatch)")
        elif kind == "bay_band":
            svg.rect(x + 8, yy - 7, 20, 9, "#cccccc", sw=0.6, fill="#eef2f7", fill_op=0.9)
        svg.text(x + 34, yy + 1, label, size=8)
        yy += 14.0
    return w, h


# ----------------------------- 侧视图 (x-z) -----------------------------
def build_side_view(eq, csv_rows, cg, draw, dist, meta):
    global SCALE
    SCALE = [PX_PER_MM_SIDE, PX_PER_MM_SIDE]
    sc = PX_PER_MM_SIDE
    hb = meta["bay_bounds"]; span = meta["bus_span"]
    env = meta["cds_env"]

    # 视图范围: 由实际绘制对象的数据范围推出 + 12 mm 边距 (布局常数)
    xs = [span[0], span[1], meta["arm_x"], -env["x"], env["x"]]
    zs = [-meta["half_cross"], meta["half_cross"], -env["z"], env["z"]]
    for r in draw:
        xs += [r["pos_mm"][0] - r["envelope_mm"][0] / 2, r["pos_mm"][0] + r["envelope_mm"][0] / 2]
        zs += [r["pos_mm"][2] - r["envelope_mm"][2] / 2, r["pos_mm"][2] + r["envelope_mm"][2] / 2]
    x_min, x_max = min(xs) - 12.0, max(xs) + 12.0
    z_min, z_max = min(zs) - 12.0, max(zs) + 12.0
    W = (x_max - x_min) * sc + 2 * MARGIN_PX
    H = (z_max - z_min) * sc + 2 * MARGIN_PX + 96.0  # 顶部题注带
    top = 96.0

    def ux(x): return MARGIN_PX + (x - x_min) * sc
    def uz(z): return top + MARGIN_PX + (z_max - z) * sc

    svg = Svg(W, H)
    # 舱段背景带 + 分界
    for bay in ("rear_service", "mid_avionics", "front_mission"):
        b = hb[bay]
        svg.rect(ux(b[0]), uz(z_max), (b[1] - b[0]) * sc, (z_max - z_min) * sc,
                 "#dddddd", sw=0.4, fill=BAY_BAND[bay], fill_op=0.7)
        svg.text((ux(b[0]) + ux(b[1])) / 2, uz(z_max) + 11, f"{bay}", size=9, anchor="middle", weight="bold")
        svg.text((ux(b[0]) + ux(b[1])) / 2, uz(z_max) + 21,
                 f"x ∈ [{fmt_mm(b[0])}, {fmt_mm(b[1])}] mm", size=7, anchor="middle", fill="#555555")
    for xb in (hb["mid_avionics"][0], hb["mid_avionics"][1]):
        svg.line(ux(xb), uz(z_min), ux(xb), uz(z_max), "#888888", sw=1.0, dash="10 4")

    # FRZ-BUS 包络 proxy 块 (12U 外廓由总线 span × 横截面绘出; 题注置于图面底部边距)
    svg.rect(ux(span[0]), uz(meta["half_cross"]), (span[1] - span[0]) * sc,
             2 * meta["half_cross"] * sc, "#333333", sw=1.6)

    # 分布式行: 背景阴影层 (块=全船包络, 角注列出 id+质量)
    svg.rect(ux(span[0]), uz(meta["half_cross"]), (span[1] - span[0]) * sc,
             2 * meta["half_cross"] * sc, "#aaaaaa", sw=0.8, fill="url(#distHatch)")
    svg.add(f'<g class="eq-distributed" data-rows="{len(dist)}">')
    for r in dist:
        svg.add(f'<g class="eq"{eq_group_attrs(r)}></g>')
    svg.add('</g>')
    svg.text(ux(x_min) + 8, uz(z_min) + 40, "distributed (背景阴影, 不单画): "
             + "; ".join(f'{r["id"]} {fmt_g(r["mass_g"])}g' for r in dist), size=TINY_FONT, fill="#666666")
    # 366.0 mm CDS 现行标准值从 yaml bus_length_note 文本正则提取 (无结构化字段); 340.5 由 span 推导
    _m366 = re.search(r"CDS 12U 现行标准\s*([0-9.]+)\s*mm", eq.get("bus_length_note") or "")
    _conflict = f", CDS 现行标准 {_m366.group(1)} 冲突登记 OI-6" if _m366 else ""
    svg.text(ux(x_min) + 8, uz(z_min) + 53,
             f'12U 外廓 bus outline: x ∈ [{fmt_mm(span[0])}, {fmt_mm(span[1])}], '
             f'z ∈ [±{fmt_mm(meta["half_cross"])}] mm ({fmt_mm(span[1] - span[0])} mm 冻结基线{_conflict})', size=7.5, fill="#333333")

    # 设备块 (文件顺序; FRZ-BUS 近全船大块, 标签置于块内右下角)
    labels = []
    for r in draw:
        lab = draw_eq_block(svg, r, ux, uz, label_pos=("br" if r["id"] == "FRZ-BUS" else "top"))
        labels.append(lab)

    # 臂基座 x=208.0 冻结标记线
    svg.line(ux(meta["arm_x"]), uz(z_min), ux(meta["arm_x"]), uz(z_max), ARM_BASE_COLOR, sw=1.8, dash="8 3")
    svg.text(ux(meta["arm_x"]) + 3, uz(z_min) + 2, f'臂基座 arm base x={fmt_mm(meta["arm_x"])} mm FROZEN',
             size=8, fill=ARM_BASE_COLOR, weight="bold")

    # CDS CG 包络框 (x-z 投影: x±70, z±45; 题注竖排于框左缘外侧避开设备标签)
    svg.rect(ux(-env["x"]), uz(env["z"]), 2 * env["x"] * sc, 2 * env["z"] * sc,
             CDS_BOX_COLOR, sw=1.2, dash="5 2.5")
    svg.text(ux(-env["x"]) - 6, uz(0),
             f'CDS CG 包络 x±{fmt_mm(env["x"])} / z±{fmt_mm(env["z"])} mm', size=7.5,
             anchor="middle", fill=CDS_BOX_COLOR, rotate=-90)

    # CG 标记 (三场景, 值来自 CG_INERTIA_CHECK_V1.json; pass/fail 取 cg_pass 字段)
    sc_a = cg["scenarios"]["SCENARIO_A_CARVE_OUT_READING_A"]
    sc_b = cg["scenarios"]["SCENARIO_B_ADDITIVE_READING_B"]
    sc_c = cg["scenarios"]["SCENARIO_CDS_VARIANT_24KG"]
    for scn, color, r_, tag in ((sc_a, CG_A_COLOR, 5.0, "CG-A"), (sc_b, CG_B_COLOR, 4.2, "CG-B")):
        gx, gz = scn["cg_S_mm"][0], scn["cg_S_mm"][2]
        svg.circle(ux(gx), uz(gz), r_, color, sw=1.5)
        svg.line(ux(gx) - r_ - 3, uz(gz), ux(gx) + r_ + 3, uz(gz), color, sw=1.1)
        svg.line(ux(gx), uz(gz) - r_ - 3, ux(gx), uz(gz) + r_ + 3, color, sw=1.1)
        labels.append({"x": ux(gx), "y": uz(gz) + r_ + 12, "s":
                       f'{tag} x={fmt_mm(gx)} z={fmt_mm(gz)} m={fmt_kg(scn["total_mass_kg"])}kg', "size": TINY_FONT,
                       "anchor": "middle"})
    gx, gz = sc_c["cg_S_mm"][0], sc_c["cg_S_mm"][2]
    svg.line(ux(gx) - 5, uz(gz) - 5, ux(gx) + 5, uz(gz) + 5, CG_CDS_COLOR, sw=1.8)
    svg.line(ux(gx) - 5, uz(gz) + 5, ux(gx) + 5, uz(gz) - 5, CG_CDS_COLOR, sw=1.8)
    labels.append({"x": ux(gx), "y": uz(gz) + 16, "s":
                   f'CG-CDS 变体 x={fmt_mm(gx)} z={fmt_mm(gz)} ({"pass" if sc_c["cg_pass"] else "fail"}, OI-1)', "size": TINY_FONT,
                   "anchor": "middle"})

    # 设备标签 (防重叠后绘制)
    for lab in place_labels(labels):
        svg.text(lab["x"], lab["y"], lab["s"], size=lab["size"], anchor=lab.get("anchor", "start"))

    # 坐标轴注 + 方向标 + 比例尺
    svg.text(ux(0) - 3, uz(0) - 6, "O", size=8, anchor="end", fill="#555555")
    svg.line(ux(x_min) + 8, uz(z_min) + 22, ux(x_min) + 8 + 40 * sc / 2, uz(z_min) + 22, "#111111", sw=1.4, marker_end="arrow")
    svg.text(ux(x_min) + 8 + 40 * sc / 2 + 6, uz(z_min) + 25, "+x (任务/臂方向)", size=8.5)
    svg.line(ux(x_min) + 8, uz(z_min) + 22, ux(x_min) + 8, uz(z_min) + 22 - 40 * sc / 2, "#111111", sw=1.4, marker_end="arrow")
    svg.text(ux(x_min) + 12, uz(z_min) + 22 - 40 * sc / 2 - 4, "+z", size=8.5)
    draw_scale_bar(svg, ux(x_min) + 8, uz(z_min) - 26, 100, sc)

    # 图例 + 题注
    entries = [("FROZEN_REF", "FROZEN_REF 冻结引用 (虚线灰)"),
               ("CANDIDATE", "CANDIDATE 候选 (实线蓝)"),
               ("ASSUMED", "ASSUMED 工程估计 (点线橙)"),
               ("dist_hatch", "distributed 分布质量 (背景)"),
               ("bay_band", "舱段背景带 + x 范围"),
               ("arm_line", f'臂基座 x={fmt_mm(meta["arm_x"])} (冻结)'),
               ("cds_box", f'CDS CG 包络 (x±{fmt_mm(env["x"])}/z±{fmt_mm(env["z"])})'),
               ("cg_a", f'CG 场景A 主口径 ({"pass" if sc_a["cg_pass"] else "fail"})'),
               ("cg_b", f'CG 场景B 上限 ({"pass" if sc_b["cg_pass"] else "fail"})'),
               ("cg_cds", f'CG CDS 变体 ({"pass" if sc_c["cg_pass"] else "fail"}, OI-1)')]
    lw, lh = draw_legend(svg, W - MARGIN_PX - 250, top + 6, entries)

    draw_title_block(svg, [
        "F4R1 C1 布局侧视图 SIDE VIEW (x–z 平面, 从 −y 侧看入)",
        f"generated_at={GENERATED_AT} · status={STATUS} · unit=mm · S frame · 比例 1mm={PX_PER_MM_SIDE}px",
        f"sources: {SRC_YAML} + {SRC_CSV} + {SRC_JSON}",
        f"{len(eq['equipment'])} 行设备按 pos_mm/envelope_mm 投影为色块; 标签 = id + 质量(g); 数字均由脚本读自源文件",
    ])
    return svg.render("F4R1 C1 LAYOUT SIDE VIEW V1", header_comment())


# ----------------------------- 前视图 (y-z, 从 +x 看入) -----------------------------
def build_front_view(eq, csv_rows, cg, draw, dist, meta):
    global SCALE
    SCALE = [PX_PER_MM_FRONT, PX_PER_MM_FRONT]
    sc = PX_PER_MM_FRONT
    hb = meta["bay_bounds"]

    # 重映射: 前视图屏幕横轴 = y_mm, 纵轴 = z_mm; 设备包络取 [ey, ez]
    for r in draw:
        r["_env_yz"] = (r["envelope_mm"][1], r["envelope_mm"][2])

    solar = [r for r in eq["equipment"] if r["id"] in ("FRZ-SOLAR-L", "FRZ-SOLAR-R")]
    half = meta["half_cross"]

    ys = [-half, half]
    zs = [-half, half]
    for r in draw:
        ey, ez = r["_env_yz"]
        ys += [r["pos_mm"][1] - ey / 2, r["pos_mm"][1] + ey / 2]
        zs += [r["pos_mm"][2] - ez / 2, r["pos_mm"][2] + ez / 2]
    y_min, y_max = min(ys) - 14.0, max(ys) + 14.0
    z_min, z_max = min(zs) - 14.0, max(zs) + 14.0
    W = (y_max - y_min) * sc + 2 * MARGIN_PX
    H = (z_max - z_min) * sc + 2 * MARGIN_PX + 96.0
    top = 96.0

    def uy(y): return MARGIN_PX + (y - y_min) * sc
    def uz(z): return top + MARGIN_PX + (z_max - z) * sc

    svg = Svg(W, H)
    # 226.3×226.3 外廓 (题注置于正方形内左下角, 避开顶部设备标签)
    svg.rect(uy(-half), uz(half), 2 * half * sc, 2 * half * sc, "#333333", sw=1.8)
    svg.text(uy(-half) + 4, uz(-half) - 8,
             f'12U 横截面 {fmt_mm(2 * half)}×{fmt_mm(2 * half)} mm', size=7, fill="#333333")
    # 中心十字
    svg.line(uy(-half), uz(0), uy(half), uz(0), "#bbbbbb", sw=0.7, dash="3 3")
    svg.line(uy(0), uz(-half), uy(0), uz(half), "#bbbbbb", sw=0.7, dash="3 3")

    # 分布式行: 背景阴影 + data 属性 (角注置于正方形下方)
    svg.rect(uy(-half), uz(half), 2 * half * sc, 2 * half * sc, "#aaaaaa", sw=0.8, fill="url(#distHatch)")
    svg.add(f'<g class="eq-distributed" data-rows="{len(dist)}">')
    for r in dist:
        svg.add(f'<g class="eq"{eq_group_attrs(r)}></g>')
    svg.add('</g>')
    svg.text(MARGIN_PX, H - 12, "distributed (背景阴影): "
             + "; ".join(f'{r["id"]} {fmt_g(r["mass_g"])}g' for r in dist), size=TINY_FONT, fill="#666666")

    # 设备块 (y-z 投影; FRZ-BUS 近全廓大块, 标签置于块内右下角)
    labels = []
    for r in draw:
        st = STATUS_STYLE.get(r["status"], STATUS_STYLE["ASSUMED"])
        ey, ez = r["_env_yz"]
        py, pz = r["pos_mm"][1], r["pos_mm"][2]
        x0, y0 = uy(py - ey / 2.0), uz(pz + ez / 2.0)
        w, h = ey * sc, ez * sc
        svg.add(f'<g class="eq"{eq_group_attrs(r)}>')
        svg.rect(x0, y0, w, h, st["stroke"], sw=1.1, fill=st["fill"], fill_op=st["fill_op"], dash=st["dash"])
        svg.add('</g>')
        if r["id"] == "FRZ-BUS":
            labels.append({"x": x0 + w - 6, "y": y0 + h - 7,
                           "s": f'{r["id"]} {fmt_g(r["mass_g"])}g', "size": LABEL_FONT, "anchor": "end"})
        else:
            labels.append({"x": x0 + w / 2.0, "y": y0 - 2.5,
                           "s": f'{r["id"]} {fmt_g(r["mass_g"])}g', "size": LABEL_FONT, "anchor": "middle"})

    # 臂基座安装区注记 (M3R/BRIDGE/F-T 同心块区域)
    m3r = next(r for r in draw if r["id"] == "FRZ-M3R")
    svg.text(uy(m3r["pos_mm"][1] + m3r["_env_yz"][0] / 2) + 4, uz(m3r["pos_mm"][2]) + 2,
             f'臂基座安装区: M3R+BRIDGE+F/T (station x={fmt_mm(meta["arm_x"])} mm, 冻结)', size=7.5,
             fill=ARM_BASE_COLOR, weight="bold")

    # 帆板: 展开态包络(虚线条) + 根部标记(在 ±y 包络边) + CG 投影点
    for r in solar:
        side = 1.0 if r["pos_mm"][1] > 0 else -1.0
        root_y = side * half
        zr = r["pos_mm"][2]
        # 根部标记 (菱形)
        cxp, czp = uy(root_y), uz(zr)
        svg.add(f'<g class="eq-root"{eq_group_attrs(r)} data-marker="panel_root">')
        svg.add(f'<path d="M {cxp:.2f} {czp - 5:.2f} L {cxp + 5 * side:.2f} {czp:.2f} L {cxp:.2f} {czp + 5:.2f} '
                f'L {cxp - 5 * side:.2f} {czp:.2f} Z" fill="{ARM_BASE_COLOR}"/>')
        svg.add('</g>')
        labels.append({"x": cxp + 40 * side, "y": czp + (10 if side > 0 else -4),
                       "s": f'{r["id"]} 根部 root (F_{"L" if side > 0 else "R"}), 展开CG y={fmt_mm(r["pos_mm"][1])}',
                       "size": TINY_FONT, "anchor": "middle"})
        # 展开 CG 投影 ×
        gy = uy(r["pos_mm"][1]); gz = uz(r["pos_mm"][2])
        svg.line(gy - 5, gz - 5, gy + 5, gz + 5, "#444444", sw=1.4)
        svg.line(gy - 5, gz + 5, gy + 5, gz - 5, "#444444", sw=1.4)
        svg.line(cxp, czp, gy, gz, "#888888", sw=0.8, dash="4 3")

    for lab in place_labels(labels):
        svg.text(lab["x"], lab["y"], lab["s"], size=lab["size"], anchor=lab.get("anchor", "start"))

    # 方向标: ⊙ +x 指向观察者
    cx0, cy0 = uy(y_min) + 26, uz(z_min) + 30
    svg.circle(cx0, cy0, 9, "#111111", sw=1.5)
    svg.circle(cx0, cy0, 2, "#111111", sw=1.0, fill="#111111")
    svg.text(cx0 + 14, cy0 + 3, "+x 指向观察者 (从 +x 任务端看入)", size=8.5)
    svg.line(cx0, cy0 - 26, cx0, cy0 - 60, "#111111", sw=1.4, marker_end="arrow")
    svg.text(cx0 + 6, cy0 - 52, "+z", size=8.5)
    svg.line(cx0, cy0 - 26, cx0 + 34, cy0 - 26, "#111111", sw=1.4, marker_end="arrow")
    svg.text(cx0 + 38, cy0 - 23, "+y", size=8.5)
    draw_scale_bar(svg, uy(y_min) + 8, uz(z_min) - 26, 100, sc)

    entries = [("FROZEN_REF", "FROZEN_REF 冻结引用"),
               ("CANDIDATE", "CANDIDATE 候选"),
               ("ASSUMED", "ASSUMED 工程估计"),
               ("dist_hatch", "distributed 分布质量"),
               ("arm_line", "帆板根部标记 (菱形)"),
               ("cg_cds", "帆板展开 CG 投影 ×")]
    draw_legend(svg, W - MARGIN_PX - 235, top + 6, entries)

    draw_title_block(svg, [
        "F4R1 C1 布局前视图 FRONT VIEW (y–z 平面, 从 +x 任务端向 −x 看入)",
        f"generated_at={GENERATED_AT} · status={STATUS} · unit=mm · S frame · 比例 1mm={PX_PER_MM_FRONT}px",
        f"sources: {SRC_YAML} + {SRC_CSV} + {SRC_JSON}",
        "设备按 (y,z) 投影; B601/帆板为 C01 在轨展开态包络与 CG 投影, 收拢态未表达 (见 README 局限)",
    ])
    return svg.render("F4R1 C1 LAYOUT FRONT VIEW V1", header_comment())


# ----------------------------- 三舱质量条形图 -----------------------------
def build_bay_mass(eq, csv_rows, cg, meta):
    rows = eq["equipment"]
    tot_dp = csv_rows["TOTAL-DESIGN-POINT"]["mass_kg"]
    tot_cds = csv_rows["TOTAL-CDS-VARIANT"]["mass_kg"]
    margin = csv_rows["MARGIN-CDS-15PCT"]["mass_kg"]
    tot_cds_m = csv_rows["TOTAL-CDS-VARIANT-MARGINED"]["mass_kg"]
    sub_eq = csv_rows["SUBTOTAL-EQUIPMENT-NEW"]["mass_kg"]
    sub_sec = csv_rows["SUBTOTAL-SECONDARY-NEW"]["mass_kg"]
    limit = cg["cds_variant_mass_check"]["limit_kg"]

    def kg(row): return row["mass_g"] / 1000.0

    # 口径 1 (DESIGN_POINT, 读法 A): 仅 FRZ-* 行, 设备分摊于 FRZ-BUS 块内不作加法
    dp_rows = [r for r in rows if r["id"].startswith("FRZ-")]
    dp_sum = math.fsum(kg(r) for r in dp_rows)
    if abs(dp_sum - tot_dp) > 1e-9:
        raise RuntimeError(f"DESIGN_POINT 聚合失配: {dp_sum} vs {tot_dp}")
    # 口径 2 (CDS_VARIANT): 全部行替换 FRZ-BUS → ST-STRUCT-REAL (= 除 FRZ-BUS 外全部)
    cds_rows = [r for r in rows if r["id"] != "FRZ-BUS"]
    cds_sum = math.fsum(kg(r) for r in cds_rows)
    if abs(cds_sum - tot_cds) > 1e-9:
        raise RuntimeError(f"CDS_VARIANT 聚合失配: {cds_sum} vs {tot_cds}")

    def by_bay(sel):
        agg = {b: 0.0 for b in BAY_ORDER}
        for r in sel:
            agg[r["bay"]] += kg(r)
        return agg

    dp_bay, cds_bay = by_bay(dp_rows), by_bay(cds_rows)

    # 图面布局 (题注全部置于条下方字幕行, 图例置于绘图区右侧净空区)
    left, plot_w = 170.0, 740.0
    x_max = max(tot_dp, limit * 1.12)
    sk = plot_w / x_max
    bar_h, gap = 46.0, 128.0
    y1 = 190.0
    y2 = y1 + bar_h + gap
    axis_y = y2 + bar_h + 66
    H = axis_y + 92.0
    W = left + plot_w + 320.0

    def ux(m): return left + m * sk

    svg = Svg(W, H)
    # x 轴与刻度 (每 5 kg 一tick, 布局常数)
    svg.line(left, axis_y, left + plot_w, axis_y, "#111111", sw=1.2)
    t = 0.0
    while t <= x_max:
        svg.line(ux(t), axis_y, ux(t), axis_y + 5, "#111111", sw=1.0)
        svg.text(ux(t), axis_y + 16, f"{t:.0f}", size=8, anchor="middle")
        t += 5.0
    svg.text(left + plot_w / 2, axis_y + 34, "质量 mass [kg]", size=9, anchor="middle")

    # CDS 24 kg 参考线
    svg.line(ux(limit), y1 - 26, ux(limit), axis_y, CDS_BOX_COLOR, sw=1.5, dash="7 3")
    svg.text(ux(limit), y1 - 32, f'CDS 12U 上限 {limit:.2f} kg (limit_kg)', size=8.5,
             anchor="middle", fill=CDS_BOX_COLOR, weight="bold")

    def draw_bar(y0, bay_agg, total, name, captions):
        svg.text(left - 8, y0 + bar_h / 2 + 3, name, size=9.5, anchor="end", weight="bold")
        x = left
        small = []
        for bay in BAY_ORDER:
            m = bay_agg[bay]
            if m <= 0:
                continue
            w = m * sk
            svg.rect(x, y0, w, bar_h, "#333333", sw=0.8, fill=BAY_COLOR[bay], fill_op=0.88)
            if w >= 96:
                svg.text(x + w / 2, y0 + bar_h / 2 - 4, bay, size=8, anchor="middle", fill="#ffffff")
                svg.text(x + w / 2, y0 + bar_h / 2 + 9, f"{fmt_kg(m)} kg · {fmt_pct(m / total)}",
                         size=7.5, anchor="middle", fill="#ffffff")
            else:
                small.append((bay, m, x + w / 2))
            x += w
        for k, (bay, m, cx) in enumerate(small):
            ly = y0 - 6 - (k % 3) * 11
            svg.line(cx, y0, cx, ly + 3, "#666666", sw=0.7)
            svg.text(cx, ly, f"{bay} {fmt_kg(m)} kg · {fmt_pct(m / total)}", size=7, anchor="middle")
        for j, cap in enumerate(captions):
            svg.text(left, y0 + bar_h + 14 + j * 11, cap, size=7, fill="#555555")
        return x

    # 口径 1 (DESIGN_POINT, 读法 A)
    draw_bar(y1, dp_bay, tot_dp, "DESIGN_POINT (主口径, 登记)", [
        f"Σ {fmt_kg(tot_dp)} kg (= SUBTOTAL-FROZEN-C01, 读法 A: 新设备 {fmt_kg(sub_eq)} kg + 二级 {fmt_kg(sub_sec)} kg 分摊于 FRZ-BUS 块内, 不作加法)",
        "FRZ-* 6 行按声明 bay 聚合; FRZ-BUS 为全船包络 proxy 块 (yaml 声明 bay=mid_avionics)",
    ])

    # 口径 2 (CDS_VARIANT): 干重 + 15% 余量段 (余量比例 = margin/干重, 由数据推导)
    margin_pct = fmt_pct(margin / tot_cds)
    draw_bar(y2, cds_bay, tot_cds, "CDS_VARIANT ≤24 kg", [
        f"干重 Σ {fmt_kg(tot_cds)} kg; 含余量 Σ {fmt_kg(tot_cds_m)} kg ≤ {limit:.2f} kg → {'PASS' if meta['cds_margin_ok'] else 'FAIL'} (B1 R2/VMMO {margin_pct})",
        f"{csv_rows['ST-STRUCT-REAL']['mass_kg']:.6g} kg ST-STRUCT-REAL 替换 {csv_rows['FRZ-BUS']['mass_kg']:.6g} kg FRZ-BUS proxy; 臂/M3R/桥/帆板/设备全保留; CDS 变体 CG 判定 fail (x/y 超包络, 登记 OI-1)",
    ])
    x_dry_end = ux(tot_cds)
    svg.rect(x_dry_end, y2, margin * sk, bar_h, "#8a6d3b", sw=0.8, fill="url(#marginHatch)")
    svg.text(x_dry_end + margin * sk + 4, y2 - 5, f"+{margin_pct} 余量 {fmt_kg(margin)} kg", size=7.5, anchor="start")

    # 图例 (绘图区右侧净空)
    lx = left + plot_w + 40
    ly = y1
    svg.text(lx, ly - 10, "舱段 bay", size=8.5, weight="bold")
    for bay in BAY_ORDER:
        svg.rect(lx, ly, 14, 10, "#333333", sw=0.6, fill=BAY_COLOR[bay], fill_op=0.88)
        svg.text(lx + 20, ly + 9, bay, size=8)
        ly += 16
    svg.rect(lx, ly, 14, 10, "#8a6d3b", sw=0.6, fill="url(#marginHatch)")
    svg.text(lx + 20, ly + 9, f"{margin_pct} 系统余量 (B1 R2/VMMO)", size=8)
    ly += 18
    svg.line(lx, ly + 5, lx + 14, ly + 5, CDS_BOX_COLOR, sw=1.5, dash="7 3")
    svg.text(lx + 20, ly + 9, f"CDS 12U 上限 {limit:.2f} kg", size=8)

    # 底部表注
    svg.text(left, axis_y + 54, "占比 pct = 段质量 / 该口径干重总质量; 全部数字由脚本聚合自 MASS_BUDGET_V1.csv + EQUIPMENT_LIST_V1.yaml",
             size=7.5, fill="#555555")
    res = cg["scenarios"]["SCENARIO_CDS_VARIANT_24KG"]["iteration"]["residual_margins_mm"]
    svg.text(left, axis_y + 66, f"质量合规 ≠ 质心合规: CDS 变体质心超出 CDS 包络 (x {fmt_mm(res['x'])} mm / y {fmt_mm(res['y'])} mm), 见 CG_INERTIA_CHECK_V1.json 与侧视图 CG 标记",
             size=7.5, fill=CDS_BOX_COLOR)

    draw_title_block(svg, [
        "F4R1 C1 三舱质量分配 BAY MASS (两口径并排)",
        f"generated_at={GENERATED_AT} · status={STATUS} · 聚合自 {SRC_CSV} (bay 归属来自 {SRC_YAML})",
        f"DESIGN_POINT {fmt_kg(tot_dp)} kg (读法 A 登记) vs CDS_VARIANT 干重 {fmt_kg(tot_cds)} kg / 含余量 {fmt_kg(tot_cds_m)} kg",
    ])
    return svg.render("F4R1 C1 LAYOUT BAY MASS V1", header_comment())


# ----------------------------- main -----------------------------
def main():
    eq = parse_equipment_yaml(HERE / SRC_YAML)
    csv_rows = parse_mass_csv(HERE / SRC_CSV)
    cg = load_cg(HERE / SRC_JSON)

    draw, dist, bad, meta = prepare(eq, csv_rows, cg)

    # 行级质量交叉核对 (yaml g vs csv kg), 不一致只登记不中断 (机器核算 json 已 PASS)
    xcheck = []
    for r in eq["equipment"]:
        if r["id"] in csv_rows and r["mass_g"] is not None:
            if abs(r["mass_g"] / 1000.0 - csv_rows[r["id"]]["mass_kg"]) > 1e-9:
                xcheck.append(r["id"])

    outs = {
        "LAYOUT_SIDE_VIEW_V1.svg": build_side_view(eq, csv_rows, cg, draw, dist, meta),
        "LAYOUT_FRONT_VIEW_V1.svg": build_front_view(eq, csv_rows, cg, draw, dist, meta),
        "LAYOUT_BAY_MASS_V1.svg": build_bay_mass(eq, csv_rows, cg, meta),
    }
    for name, text in outs.items():
        (HERE / name).write_bytes(text.encode("utf-8"))

    report = {
        "generated_at": GENERATED_AT, "status": STATUS,
        "inputs_sha256_12": {n: sha256_12(HERE / n) for n in (SRC_YAML, SRC_CSV, SRC_JSON)},
        "equipment_rows_total": len(eq["equipment"]),
        "rows_drawn_geometric": len(draw),
        "rows_distributed_background": [r["id"] for r in dist],
        "rows_skipped_invalid": bad,
        "arm_base_x_extracted_mm": meta["arm_x"],
        "yaml_csv_mass_mismatch": xcheck,
        "outputs": sorted(outs),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if bad:
        print("WARNING: 有设备行被跳过 (应登记进 README 局限节):", bad, file=sys.stderr)


if __name__ == "__main__":
    main()
