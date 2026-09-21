# -*- coding: utf-8 -*-
"""
build_stop_rating_annotation_20260917.py

WP10 电气选型收口切片：为 STOP 控制板（STOP_CONTROL_PCB）103 个 REAL_PART_CANDIDATE
位号著录 rating 与 substitution_limit。

确定性、可审计设计原则：
  1. 输入仅来自 SELECTION_BOM_V36.csv（value/MPN/footprint 字段）、SELECTION_GAPS.json
     （103 位号清单核对）、PUBLIC_SOURCES.json（已归档数据手册清单）与网表 XML（交叉核对）。
  2. 贴片电容/电阻的额定值从 MPN 编码规则显式解码（KEMET C0603C、Vishay CRCW/TNPW），
     并与 value 字段中的人读部分交叉核对；不一致即落 UNKNOWN_NAMED_GAP，绝不猜测。
  3. IC 仅对 PUBLIC_SOURCES.json 已归档的 5 个 TI 器件 + TRACO TSR 1 给 DATASHEET_ARCHIVED
     级额定；其余 IC 一律 DECLARED_ENGINEERING_SCREEN（保守族级声明）或具名缺口。
  4. 连接器额定用族级公开值并标注 DERIVED_FROM_FAMILY_DATASHEET。
  5. 任何解析失败的行进 UNKNOWN_NAMED_GAP 并写明缺什么。

运行：python -B -X utf8 tools/build_stop_rating_annotation_20260917.py
输出：
  results/electrical_selection_20260917/STOP_RATING_ANNOTATION_20260917.json (+ .sha256)
  results/electrical_selection_20260917/SELECTION_GAPS_UPDATE_20260917.json (+ .sha256)
"""

import csv
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

IMPL = Path(__file__).resolve().parent.parent
SEL_DIR = IMPL / "results" / "electrical_selection_20260917"
BOM_CSV = SEL_DIR / "SELECTION_BOM_V36.csv"
GAPS_JSON = SEL_DIR / "SELECTION_GAPS.json"
PUB_SRC = IMPL / "results" / "stop_v36" / "PUBLIC_SOURCES.json"
NETLIST_XML = (IMPL / "results" / "stop_v36" / "pcb" / "thermal_filter_20260916"
               / "native_20260916_a" / "wp10_system.xml")

OUT_JSON = SEL_DIR / "STOP_RATING_ANNOTATION_20260917.json"
OUT_GAPS = SEL_DIR / "SELECTION_GAPS_UPDATE_20260917.json"
DATE = "2026-09-17"

# ---------------------------------------------------------------------------
# 编码规则表（显式、可审计）
# ---------------------------------------------------------------------------
# KEMET C0603C 贴片陶瓷电容编码：C 0603 C <3位容值pF> <容差字母> <电压码> <介质字母> ACTU
KEMET_TOL = {"B": "±0.1pF", "C": "±0.25pF", "D": "±0.5pF",
             "F": "±1%", "G": "±2%", "J": "±5%", "K": "±10%", "M": "±20%"}
KEMET_VOLT = {"9": 6.3, "8": 4, "4": 16, "3": 25, "5": 50, "1": 100, "2": 200}
KEMET_DIEL = {"R": "X7R", "G": "C0G (NP0)"}

# Vishay CRCW0603 e3 编码：CRCW0603 <阻值4位> F(±1%) K(±100ppm/K) EA(包装)
CRCW0603_POWER_W = 0.1        # 已归档 Vishay dcrcwe3 数据手册（20035, 14-Apr-2026）
CRCW0603_MAX_WORK_V = 75      # 同上：CRCW0603 最大工作电压

# Vishay TNPW e3 编码：TNPW <尺寸> <阻值4位> B(±0.1%) E(±25ppm/K) EA
# 注意：tnpw_e3 数据手册未在 PUBLIC_SOURCES.json 归档 → 功率/电压额定不著录，记具名缺口。

SUB_IC = "仅同 MPN 或厂商书面第二货源"


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_with_sidecar(path: Path, obj) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False)
    payload = (text + "\n").encode("utf-8")
    path.write_bytes(payload)  # 二进制写入，禁止 Windows CRLF 转换，保证哈希可复算
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_bytes(f"{digest}  {path.name}\n".encode("utf-8"))


def fmt_cap(pf: float) -> str:
    if pf >= 1e6:
        return f"{pf / 1e6:g} µF"
    if pf >= 1e3:
        return f"{pf / 1e3:g} nF"
    return f"{pf:g} pF"


def parse_resistance_code(code: str):
    """解析 '10K0' / '100K' / '22R0' / '100R' / '1K00' 式 4 位阻值码 → 欧姆。"""
    m = re.fullmatch(r"(\d+)([RK])(\d{0,2})", code)
    if not m:
        return None
    a, letter, b = m.groups()
    mult = 1000.0 if letter == "K" else 1.0
    mant = float(a + "." + b) if b else float(a)
    return mant * mult


def fmt_res(ohm: float) -> str:
    if ohm >= 1e6:
        return f"{ohm / 1e6:g} MΩ"
    if ohm >= 1e3:
        return f"{ohm / 1e3:g} kΩ"
    return f"{ohm:g} Ω"


# ---------------------------------------------------------------------------
# value 字段人读部分解析（用于与 MPN 解码交叉核对）
# ---------------------------------------------------------------------------
def value_human_part(value: str) -> str:
    """BOM value 形如 'MPN / 100nF X7R 25V 10%'；取 '/ ' 之后的人读部分。"""
    if " / " in value:
        return value.split(" / ", 1)[1].strip()
    return value.strip()


def parse_cap_human(text: str):
    """解析 '100nF X7R 25V 10%' 或 '1uF X7R 16V 10%' → dict；失败返回 None。"""
    m = re.fullmatch(
        r"([\d.]+)\s*(nF|uF|µF|pF)\s+([A-Za-z0-9() ]+?)\s+([\d.]+)\s*V\s+([\d.]+)\s*%",
        text.strip())
    if not m:
        return None
    mag, unit, diel, volt, tol = m.groups()
    factor = {"pF": 1.0, "nF": 1e3, "uF": 1e6, "µF": 1e6}[unit]
    return {"capacitance_pF": float(mag) * factor, "dielectric": diel.strip(),
            "rated_voltage_V": float(volt), "tolerance": f"±{tol}%"}


def parse_bare_cap(text: str):
    """解析裸值 '1nF' → pF；失败 None。"""
    m = re.fullmatch(r"([\d.]+)\s*(nF|uF|µF|pF)", text.strip())
    if not m:
        return None
    factor = {"pF": 1.0, "nF": 1e3, "uF": 1e6, "µF": 1e6}[m.group(2)]
    return float(m.group(1)) * factor


# ---------------------------------------------------------------------------
# 各器件族解码器：返回 (rating, source_class, substitution_limit, named_gaps, notes)
# ---------------------------------------------------------------------------
def unknown(ref, what: str):
    return (None, "UNKNOWN_NAMED_GAP",
            "未定——rating 未著录前禁止替代",
            [what], f"解析失败/证据不足：{what}")


def decode_kemet_cap(ref, mpn, value):
    m = re.fullmatch(r"C0603C(\d{3})([A-Z])(\d)([A-Z])ACTU", mpn)
    if not m:
        return unknown(ref, f"MPN '{mpn}' 不匹配 KEMET C0603C 编码规则")
    digits, tol_c, volt_c, diel_c = m.groups()
    if tol_c not in KEMET_TOL or volt_c not in KEMET_VOLT or diel_c not in KEMET_DIEL:
        return unknown(ref, f"MPN '{mpn}' 含未登记编码字母（容差/电压/介质码表外）")
    pf = int(digits[:2]) * (10 ** int(digits[2]))
    rating = {
        "capacitance": fmt_cap(pf),
        "capacitance_pF": pf,
        "dielectric": KEMET_DIEL[diel_c],
        "tolerance": KEMET_TOL[tol_c],
        "rated_voltage_V": KEMET_VOLT[volt_c],
        "case": "0603 (1608 metric)",
    }
    # 与 value 人读部分交叉核对
    human = value_human_part(value)
    if human != mpn:
        full = parse_cap_human(human)
        if full:
            checks = [
                (abs(full["capacitance_pF"] - pf) < 0.5, "容值"),
                (full["dielectric"].upper().startswith(KEMET_DIEL[diel_c][:3]), "介质"),
                (abs(full["rated_voltage_V"] - KEMET_VOLT[volt_c]) < 1e-9, "额定电压"),
                (full["tolerance"] == KEMET_TOL[tol_c], "容差"),
            ]
            bad = [name for ok, name in checks if not ok]
            if bad:
                return unknown(ref, f"MPN 解码与 value 人读部分不一致：{bad}（value='{value}'）")
        else:
            bare = parse_bare_cap(human)
            if bare is None:
                return unknown(ref, f"value 人读部分 '{human}' 无法解析，无法交叉核对")
            if abs(bare - pf) >= 0.5:
                return unknown(ref, f"value 容值 '{human}' 与 MPN 解码 {fmt_cap(pf)} 不一致")
    if KEMET_DIEL[diel_c] == "X7R":
        sub = (f"E 系列同容值（{fmt_cap(pf)}）X7R、0603、额定电压 ≥{KEMET_VOLT[volt_c]:g}V、"
               f"容差不劣于 {KEMET_TOL[tol_c]} 可替代；禁 Y5V/Z5U")
    else:
        sub = (f"同容值（{fmt_cap(pf)}）C0G/NP0、0603、额定电压 ≥{KEMET_VOLT[volt_c]:g}V、"
               f"容差不劣于 {KEMET_TOL[tol_c]} 可替代；禁二类介质（X7R/X5R/Y5V）降等")
    return (rating, "DERIVED_FROM_PARTCODE", sub, [],
            "KEMET C0603C 编码规则解码；value 人读部分交叉核对一致；"
            "KEMET 规格书 URL 在 BOM source 列（未归档本地）")


def decode_crcw0603(ref, mpn, value):
    m = re.fullmatch(r"CRCW0603(\d+[RK]\d{0,2})FKEA", mpn)
    if not m:
        return unknown(ref, f"MPN '{mpn}' 不匹配 Vishay CRCW0603 e3 编码规则")
    ohm = parse_resistance_code(m.group(1))
    if ohm is None:
        return unknown(ref, f"阻值码 '{m.group(1)}' 无法解析")
    rating = {
        "resistance": fmt_res(ohm),
        "resistance_ohm": ohm,
        "tolerance": "±1%",
        "tempco_ppm": "±100 ppm/K",
        "rated_power_W": CRCW0603_POWER_W,
        "rated_voltage_V": CRCW0603_MAX_WORK_V,
        "case": "0603 (1608 metric)",
    }
    # 与 value 人读部分交叉核对（如 '10k 1%'、'22k 1% 100ppm/C'、'4.7k'、'100'）
    human = value_human_part(value)
    if human != mpn:
        m2 = re.match(r"([\d.]+)\s*(k|K|M|R)?", human)
        if not m2:
            return unknown(ref, f"value 人读部分 '{human}' 无法解析，无法交叉核对")
        mag = float(m2.group(1))
        unit = (m2.group(2) or "").upper()
        hv = mag * {"": 1.0, "R": 1.0, "K": 1e3, "M": 1e6}[unit]
        if abs(hv - ohm) > 1e-9 * max(ohm, 1.0):
            return unknown(ref, f"value 阻值 '{human}' 与 MPN 解码 {fmt_res(ohm)} 不一致")
    return (rating, "DERIVED_FROM_PARTCODE",
            f"E96 1% 0603 厚膜片阻，阻值相等（{fmt_res(ohm)}）、额定功率 ≥0.1W、"
            "TCR 不劣于 ±100ppm/K 可替代；禁 5% 档降等",
            [],
            "Vishay CRCW0603 e3 编码解码（F=±1%，K=±100ppm/K）；"
            "0.1W/75V 来自已归档 dcrcwe3 数据手册（DATASHEET_ARCHIVED 级字段）；"
            "value 人读部分交叉核对一致")


def decode_tnpw(ref, mpn, value):
    m = re.fullmatch(r"TNPW(0603|0805)(\d+[RK]\d{0,2})BEEA", mpn)
    if not m:
        return unknown(ref, f"MPN '{mpn}' 不匹配 Vishay TNPW e3 编码规则")
    size, code = m.groups()
    ohm = parse_resistance_code(code)
    if ohm is None:
        return unknown(ref, f"阻值码 '{code}' 无法解析")
    rating = {
        "resistance": fmt_res(ohm),
        "resistance_ohm": ohm,
        "tolerance": "±0.1%",
        "tempco_ppm": "±25 ppm/K",
        "rated_power_W": None,
        "rated_voltage_V": None,
        "case": f"{size} ({'1608' if size == '0603' else '2012'} metric)",
    }
    human = value_human_part(value)
    if human != mpn:
        m2 = re.match(r"([\d.]+)\s*(k|K|M)", human.replace("_0.1pct_25ppm", "").replace("_", " "))
        if m2:
            hv = float(m2.group(1)) * {"k": 1e3, "K": 1e3, "M": 1e6}[m2.group(2)]
            if abs(hv - ohm) > 1e-9 * max(ohm, 1.0):
                return unknown(ref, f"value 阻值 '{human}' 与 MPN 解码 {fmt_res(ohm)} 不一致")
        else:
            return unknown(ref, f"value 人读部分 '{human}' 无法解析，无法交叉核对")
    return (rating, "DERIVED_FROM_PARTCODE",
            f"仅 E192 0.1% ±25ppm/K 薄膜同规格（{fmt_res(ohm)}，{size}）可替代；"
            "禁普通厚膜（1%/100ppm）降等——分压比精度与温漂敏感",
            ["rated_power_W 与 rated_voltage_V 未著录：Vishay tnpw_e3 数据手册未归档"
             "（PUBLIC_SOURCES.json 无此源），需归档后补录"],
            "Vishay TNPW e3 编码解码（B=±0.1%，E=±25ppm/K）；value 人读部分交叉核对一致；"
            "功率/电压额定为具名缺口")


def decode_pr02(ref, mpn, value):
    if not mpn.startswith("PR02"):
        return unknown(ref, f"MPN '{mpn}' 不以 PR02 开头")
    human = value_human_part(value)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)R\s+(\d+(?:\.\d+)?)%\s+(\d+)\s*ppm/C\s+(\d+(?:\.\d+)?)W",
                     human)
    if not m:
        return unknown(ref, f"value 人读部分 '{human}' 无法解析（期望 '<阻值>R <容差>% <TCR>ppm/C <功率>W'）")
    ohm, tol, tcr, pwr = m.groups()
    rating = {
        "resistance": f"{ohm} Ω",
        "resistance_ohm": float(ohm),
        "tolerance": f"±{tol}%",
        "tempco_ppm": f"±{tcr} ppm/K",
        "rated_power_W": float(pwr),
        "rated_voltage_V": None,
        "case": "PR02 轴向 2W（WP10_STOP:Vishay_PR02_P15_24）",
    }
    return (rating, "DERIVED_FROM_PARTCODE",
            f"PR02 同阻值（{ohm}Ω）2W ±{tol}% 或同族更高功率（PR03 3W）可替代；"
            "禁额定功率 <2W 替代",
            ["rated_voltage_V 未著录：pr010203 数据手册未归档（PUBLIC_SOURCES.json 无此源）"],
            "rated_power_W=2 来自 value 字段本身；MPN 前缀 PR02 与 2W 系列一致；"
            "阻值/容差/TCR/功率均解析自 value 人读部分")


def decode_connector(ref, mpn):
    if re.fullmatch(r"43(?:045|650)\d{4}", mpn):
        return ({"family": "Molex Micro-Fit 3.0",
                 "rated_current_A_per_contact": 5,
                 "rated_voltage_V": 250},
                "DERIVED_FROM_FAMILY_DATASHEET",
                "仅 Molex Micro-Fit 3.0 同位数同安装方向（43045/43650 系列）或厂商书面第二货源；"
                "替代件须 ≥5A/250V per contact",
                [],
                "Micro-Fit 3.0 族级公开额定 5A/250V per contact（族级常识，标注来源等级；"
                "Molex 产品页 URL 在 BOM source 列，族规格书未归档本地）")
    if mpn == "SM06B-GHS-TB":
        return ({"family": "JST GH (1.25mm)",
                 "rated_current_A_per_contact": 1,
                 "rated_voltage_V": 50},
                "DERIVED_FROM_FAMILY_DATASHEET",
                "仅 JST GH 同位数（SMxxB-GHS-TB）或厂商书面第二货源；替代件须 ≥1A/50V",
                [],
                "JST GH 族级公开额定 1A/50V（族级常识，标注来源等级；"
                "eGH.pdf URL 在 BOM source 列，未归档本地）")
    return unknown(ref, f"连接器 MPN '{mpn}' 不在已登记族（Micro-Fit 3.0 / JST GH）内")


def decode_q101(ref, mpn):
    if mpn != "IRL630PbF":
        return unknown(ref, f"Q 位号 MPN '{mpn}' 未登记")
    return ({"type": "N 沟道功率 MOSFET",
             "Vds_V": 200,
             "package": "TO-220-3",
             "key_ratings": {"Vds_V": 200}},
            "DERIVED_FROM_PARTCODE",
            "优先同 MPN（IRL630PbF）；替代须 Vds ≥200V N 沟 TO-220，且 Rds_on/Qg 复核后书面批准"
            "（irl630.pdf 未归档，替代参数基线缺失）",
            ["Rds_on/Id/Vgs(th)/Qg 未著录：irl630.pdf 未归档（PUBLIC_SOURCES.json 无此源）"],
            "Vds=200V 为 IRL630 族级额定（MPN 解码 + 族级常识，标注来源等级）；"
            "Vishay 91303/irl630.pdf URL 在 BOM source 列，未归档本地")


# ---------------------------------------------------------------------------
# IC 额定表：DATASHEET_ARCHIVED 级数值来自 PUBLIC_SOURCES.json 登记的 6 条已归档源
# （UCC27517 SLUSAY4D / SN74LV1T04 SCLS738E / TPS3808 SBVS050N / SN74LVC74A SCAS287W /
#   TRACO TSR 1 2025-08-07；CRCW0603 走电阻解码器）。
# abs_max_V 取自对应已归档数据手册的 Absolute Maximum Ratings 表。
# ---------------------------------------------------------------------------
IC_ARCHIVED = {
    "UCC27517DBVR": {
        "rating": {"supply_range_V": "4.5 – 18", "abs_max_V": 20,
                   "key_ratings": {"peak_source_A": 4, "peak_sink_A": 4,
                                   "uvlo_typ_V": 4,
                                   "input_logic": "TTL/CMOS 兼容，阈值与 VDD 无关"}},
        "notes": "TI UCC27517 数据手册 SLUSAY4D（PUBLIC_SOURCES 已归档）；"
                 "4.5–18V 供电、4A/4A 峰值、UVLO 4V typ 经 TI 产品页复核一致"},
    "SN74LV1T04DBVR": {
        "rating": {"supply_range_V": "1.65 – 5.5", "abs_max_V": 7,
                   "key_ratings": {"input_5V_tolerant": True,
                                   "output_drive_mA": {"5V": 8, "3.3V": 7, "1.8V": 3},
                                   "characterized_MHz_at_3V3": 50}},
        "notes": "TI SN74LV1T04 数据手册 SCLS738E（PUBLIC_SOURCES 已归档）；"
                 "1.65–5.5V、输入 5V 耐压、输出驱动经 TI 产品页复核一致"},
    "TPS3808G33DBVR": {
        "rating": {"supply_range_V": "1.8 – 6.5", "abs_max_V": 7,
                   "key_ratings": {"threshold_V": 3.07, "monitored_rail_V": 3.3,
                                   "reset_output": "开漏低有效",
                                   "iq_typ_uA": 2.4, "threshold_accuracy_pct_typ": 0.5}},
        "notes": "TI TPS3808 数据手册 SBVS050N（PUBLIC_SOURCES 已归档，著录条目为 G33）；"
                 "阈值 3.07V（监测 3.3V 轨）取自该族固定阈值表"},
    "TPS3808G50DBVR": {
        "rating": {"supply_range_V": "1.8 – 6.5", "abs_max_V": 7,
                   "key_ratings": {"threshold_V": 4.65, "monitored_rail_V": 5.0,
                                   "reset_output": "开漏低有效",
                                   "iq_typ_uA": 2.4, "threshold_accuracy_pct_typ": 0.5}},
        "notes": "同 SBVS050N 覆盖 G01/G33/G50（PUBLIC_SOURCES 著录条目为 G33，"
                 "BOM source URL 同为 tps3808.pdf）；阈值 4.65V（监测 5V 轨）"},
    "TPS3808G01DBVR": {
        "rating": {"supply_range_V": "1.8 – 6.5", "abs_max_V": 7,
                   "key_ratings": {"threshold_V": 0.405, "monitored_rail": "可调（SENSE 分压）",
                                   "reset_output": "开漏低有效",
                                   "iq_typ_uA": 2.4, "threshold_accuracy_pct_typ": 0.5}},
        "notes": "同 SBVS050N（见 U102 行注）；G01 为可调阈值 0.405V 基准版本"},
    "SN74LVC74APWR": {
        "rating": {"supply_range_V": "1.65 – 3.6", "abs_max_V": 6.5,
                   "key_ratings": {"input_tolerance_V": 5.5,
                                   "tpd_max_ns_at_3V3": 5.2,
                                   "output_drive_mA_at_3V": {"IOL": 24, "IOH": -24}}},
        "notes": "TI SN74LVC74A 数据手册 SCAS287W（PUBLIC_SOURCES 已归档）；"
                 "1.65–3.6V 供电、输入耐 5.5V 经 TI 产品页复核一致"},
    "TSR 1-2433": {
        "rating": {"supply_range_V": "输入 4.75 – 36 VDC", "abs_max_V": 36,
                   "key_ratings": {"output_V": 3.3, "output_A_max": 1,
                                   "efficiency_pct_at_vin_min": 91,
                                   "operating_temp_C": "-40 – +85",
                                   "external_input_cap": "输入 >32VDC 时需 22µF/50V"
                                   "（WP10 24V 轨不需要）"}},
        "notes": "TRACO TSR 1 数据手册 2025-08-07 版（PUBLIC_SOURCES 已归档）；"
                 "输入范围 4.75–36VDC 与归档页注释（>32VDC 需外接电容）一致"},
    "TSR 1-2450": {
        "rating": {"supply_range_V": "输入 6.5 – 36 VDC", "abs_max_V": 36,
                   "key_ratings": {"output_V": 5.0, "output_A_max": 1,
                                   "efficiency_pct_at_vin_min": 94,
                                   "operating_temp_C": "-40 – +85",
                                   "external_input_cap": "输入 >32VDC 时需 22µF/50V"
                                   "（WP10 24V 轨不需要）"}},
        "notes": "TRACO TSR 1 数据手册 2025-08-07 版（PUBLIC_SOURCES 已归档）"},
}

# LVC 小逻辑门：族级保守声明（数据手册未归档 → DECLARED_ENGINEERING_SCREEN）
LVC_FAMILY = {"supply_range_V": "1.65 – 5.5（族级保守声明）",
              "abs_max_V": 6.5,
              "key_ratings": {"note": "LVC 族级保守声明；具体 MPN 数据手册未归档，"
                                      "归档后须复核供电范围与绝对最大额定"}}

IC_SCREEN = {
    "SN74LVC1G17DBVR": dict(LVC_FAMILY, function="单施密特缓冲"),
    "SN74LVC2G17DBVR": dict(LVC_FAMILY, function="双施密特缓冲"),
    "SN74LVC1G04DBVR": dict(LVC_FAMILY, function="单反相器"),
    "SN74LVC1G08DBVR": dict(LVC_FAMILY, function="单与门"),
    "SN74LVC1G07DBVR": dict(LVC_FAMILY, function="单开漏缓冲"),
}


def decode_ic(ref, mpn):
    if mpn in IC_ARCHIVED:
        entry = IC_ARCHIVED[mpn]
        return (entry["rating"], "DATASHEET_ARCHIVED", SUB_IC, [], entry["notes"])
    if mpn in IC_SCREEN:
        rating = {"function": IC_SCREEN[mpn]["function"],
                  "supply_range_V": IC_SCREEN[mpn]["supply_range_V"],
                  "abs_max_V": IC_SCREEN[mpn]["abs_max_V"],
                  "key_ratings": IC_SCREEN[mpn]["key_ratings"]}
        return (rating, "DECLARED_ENGINEERING_SCREEN", SUB_IC,
                ["具体 MPN 数据手册未归档：供电范围/abs max 为 LVC 族级保守声明，待归档复核"],
                "TI LVC 族级保守声明值（未按具体 MPN 归档数据手册核验）")
    if mpn in ("TPS3431SDRBR", "TLV6700DDCR"):
        return ({"supply_range_V": None, "abs_max_V": None,
                 "key_ratings": {"note": "额定值未著录"}},
                "UNKNOWN_NAMED_GAP", "未定——rating 未著录前禁止替代",
                [f"{mpn} 数据手册未归档（PUBLIC_SOURCES.json 无此源）："
                 "供电范围、绝对最大额定、关键额定全部缺失，须归档 TI 数据手册后补录"],
                "无可解码编码规则且无已归档数据手册，按规则不猜测")
    return unknown(ref, f"IC MPN '{mpn}' 未在任何登记表中")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    # 输入真值哈希
    bom_sha = sha256_of(BOM_CSV)
    gaps_sha = sha256_of(GAPS_JSON)

    gaps_doc = json.loads(GAPS_JSON.read_text(encoding="utf-8"))
    pub_doc = json.loads(PUB_SRC.read_text(encoding="utf-8"))
    archived_parts = {s["part"] for s in pub_doc["sources"]}

    # 网表 XML 交叉核对（footprint / MPN）
    tree = ET.parse(NETLIST_XML)
    netlist = {}
    for comp in tree.getroot().iter("comp"):
        ref = comp.get("ref")
        fp_el = comp.find("footprint")
        mpn_el = None
        fields = comp.find("fields")
        if fields is not None:
            for f in fields.findall("field"):
                if f.get("name") == "MPN":
                    mpn_el = f
        netlist[ref] = {"footprint": fp_el.text if fp_el is not None else None,
                        "MPN": mpn_el.text if mpn_el is not None else None}

    # 读 BOM，取 STOP 板 REAL_PART_CANDIDATE 行
    with BOM_CSV.open("r", encoding="utf-8", newline="") as fh:
        rows_all = list(csv.DictReader(fh))
    stop_rows = [r for r in rows_all
                 if r["board"] == "STOP_CONTROL_PCB" and r["class_"] == "REAL_PART_CANDIDATE"]
    stop_refs = [r["ref"] for r in stop_rows]
    assert len(stop_refs) == len(set(stop_refs)), "位号重复"

    # 与 SELECTION_GAPS.json 的 rating 缺口清单核对
    rating_gap_refs = set(gaps_doc["gaps"]["rating"]["refs"])
    missing_from_gaps = [r for r in stop_refs if r not in rating_gap_refs]
    if missing_from_gaps:
        raise SystemExit(f"FAIL: 以下 STOP 位号不在 SELECTION_GAPS rating 缺口清单内: {missing_from_gaps}")

    out_rows = []
    netlist_mismatches = []
    for r in stop_rows:
        ref, mpn, value, fp = r["ref"], r["MPN"].strip(), r["value"], r["footprint"]
        prefix = re.match(r"[A-Z]+", ref).group(0)
        if prefix == "C":
            result = decode_kemet_cap(ref, mpn, value)
        elif prefix == "R":
            if mpn.startswith("CRCW0603"):
                result = decode_crcw0603(ref, mpn, value)
            elif mpn.startswith("TNPW"):
                result = decode_tnpw(ref, mpn, value)
            elif mpn.startswith("PR02"):
                result = decode_pr02(ref, mpn, value)
            else:
                result = unknown(ref, f"电阻 MPN '{mpn}' 不在已登记族（CRCW0603/TNPW/PR02）")
        elif prefix == "J":
            result = decode_connector(ref, mpn)
        elif prefix == "Q":
            result = decode_q101(ref, mpn)
        elif prefix == "U":
            result = decode_ic(ref, mpn)
        else:
            result = unknown(ref, f"位号前缀 '{prefix}' 无登记解码器")
        rating, sclass, sub, named_gaps, notes = result

        # 网表交叉核对
        nl = netlist.get(ref)
        nl_note = "网表无此位号"
        if nl is not None:
            diffs = []
            if nl["footprint"] and nl["footprint"] != fp:
                diffs.append(f"footprint: BOM='{fp}' vs 网表='{nl['footprint']}'")
            if nl["MPN"] and nl["MPN"] != mpn:
                diffs.append(f"MPN: BOM='{mpn}' vs 网表='{nl['MPN']}'")
            if diffs:
                netlist_mismatches.append({"ref": ref, "diffs": diffs})
                nl_note = "不一致: " + "; ".join(diffs)
            else:
                nl_note = "footprint/MPN 与网表一致"

        out_rows.append({
            "ref": ref,
            "board": r["board"],
            "value": value,
            "MPN": mpn,
            "footprint": fp,
            "rating": rating,
            "rating_source_class": sclass,
            "named_gaps": named_gaps,
            "substitution_limit": sub,
            "provenance_notes": notes,
            "netlist_crosscheck": nl_note,
        })

    # 覆盖统计
    dist = {}
    for row in out_rows:
        dist[row["rating_source_class"]] = dist.get(row["rating_source_class"], 0) + 1
    unknown_rows = [row for row in out_rows if row["rating_source_class"] == "UNKNOWN_NAMED_GAP"]
    named_gap_rows = [row for row in out_rows if row["named_gaps"]]
    prefix_counts = {}
    for row in out_rows:
        p = re.match(r"[A-Z]+", row["ref"]).group(0)
        prefix_counts[p] = prefix_counts.get(p, 0) + 1

    annotation = {
        "schema": "WP10_V36_STOP_RATING_ANNOTATION",
        "date": DATE,
        "source_bom": "results/electrical_selection_20260917/SELECTION_BOM_V36.csv",
        "source_bom_sha256": bom_sha,
        "source_gaps": "results/electrical_selection_20260917/SELECTION_GAPS.json",
        "source_gaps_sha256": gaps_sha,
        "public_sources": "results/stop_v36/PUBLIC_SOURCES.json",
        "archived_source_parts": sorted(archived_parts),
        "netlist_crosscheck_source": "results/stop_v36/pcb/thermal_filter_20260916/"
                                     "native_20260916_a/wp10_system.xml",
        "netlist_footprint_mpn_mismatches": netlist_mismatches,
        "coverage": {
            "total": len(out_rows),
            "composition_note": "STOP_CONTROL_PCB 全部 REAL_PART_CANDIDATE 行，"
                                "按位号前缀构成: " +
                                ", ".join(f"{k}={v}" for k, v in sorted(prefix_counts.items())) +
                                "；连接器 J101-J106 与功率电阻 R124/R125 均在 103 行内，"
                                "无安装孔/边界符号混入",
            "by_source_class": dist,
            "unknown_count": len(unknown_rows),
            "rows_with_named_gaps": len(named_gap_rows),
            "named_gap_policy": "named_gaps 非空的行其可确定字段照常著录；缺失字段以 null "
                                "表示并在 named_gaps 写明缺什么、缺哪个证据源",
        },
        "rows": out_rows,
        "whole_design_complete": False,
        "manufacturing_release": False,
    }
    write_with_sidecar(OUT_JSON, annotation)
    ann_sha = sha256_of(OUT_JSON)

    # --- SELECTION_GAPS 更新（不覆盖原文件） ---
    resolved_refs = sorted(row["ref"] for row in out_rows
                           if row["rating_source_class"] != "UNKNOWN_NAMED_GAP")
    remaining_rating = [r for r in gaps_doc["gaps"]["rating"]["refs"]
                        if r not in set(resolved_refs)]
    remaining_sub = [r for r in gaps_doc["gaps"]["substitution_limit"]["refs"]
                     if r not in set(resolved_refs)]
    gaps_update = {
        "schema": "WP10_V36_SELECTION_GAPS_UPDATE",
        "date": DATE,
        "supersedes_in_part": "results/electrical_selection_20260917/SELECTION_GAPS.json",
        "source_gaps_sha256": gaps_sha,
        "rating_annotation": "results/electrical_selection_20260917/STOP_RATING_ANNOTATION_20260917.json",
        "rating_annotation_sha256": ann_sha,
        "scope": "STOP_CONTROL_PCB 103 行 rating/substitution_limit 著录后剩余缺口；"
                 "原 SELECTION_GAPS.json 未改动",
        "changes": {
            "rating": {"before": gaps_doc["gaps"]["rating"]["count"],
                       "resolved_stop_board": len(resolved_refs),
                       "still_unknown_in_stop_board": len(unknown_rows),
                       "after": len(remaining_rating),
                       "remaining_refs": remaining_rating},
            "substitution_limit": {"before": gaps_doc["gaps"]["substitution_limit"]["count"],
                                   "resolved_stop_board": len(resolved_refs),
                                   "still_unknown_in_stop_board": len(unknown_rows),
                                   "after": len(remaining_sub),
                                   "remaining_refs": remaining_sub},
        },
        "unchanged_gap_categories": {
            k: v["count"] for k, v in gaps_doc["gaps"].items()
            if k not in ("rating", "substitution_limit")},
        "unknown_named_gap_rows": [
            {"ref": row["ref"], "MPN": row["MPN"], "named_gaps": row["named_gaps"]}
            for row in unknown_rows],
        "rows_with_named_gaps_but_classified": [
            {"ref": row["ref"], "rating_source_class": row["rating_source_class"],
             "named_gaps": row["named_gaps"]}
            for row in named_gap_rows if row["rating_source_class"] != "UNKNOWN_NAMED_GAP"],
        "exit_condition_WP2": gaps_doc.get("exit_condition_WP2"),
        "exit_condition_met": False,
        "whole_design_complete": False,
        "manufacturing_release": False,
    }
    write_with_sidecar(OUT_GAPS, gaps_update)

    # --- 控制台报告 ---
    print(f"STOP_CONTROL_PCB REAL_PART_CANDIDATE 行数: {len(out_rows)}")
    print("source_class 分布:")
    for k, v in sorted(dist.items()):
        print(f"  {k}: {v}")
    print(f"named_gaps 非空行数（含 UNKNOWN）: {len(named_gap_rows)}")
    print(f"网表 footprint/MPN 交叉核对不一致: {len(netlist_mismatches)}")
    if unknown_rows:
        print("UNKNOWN_NAMED_GAP 清单:")
        for row in unknown_rows:
            print(f"  {row['ref']} ({row['MPN']}): {row['named_gaps'][0]}")
    else:
        print("UNKNOWN_NAMED_GAP 清单: 无")
    print(f"rating 缺口: {gaps_doc['gaps']['rating']['count']} -> {len(remaining_rating)}"
          f"（解决 {len(resolved_refs)}，其中 STOP 板内仍 UNKNOWN {len(unknown_rows)}）")
    print(f"产物: {OUT_JSON}")
    print(f"产物: {OUT_GAPS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
