# -*- coding: utf-8 -*-
"""
build_system_rating_annotation_20260917.py

WP10 电气选型收口二期：为 STOP 板之外剩余 121 个 REAL_PART_CANDIDATE 位号
（MAIN_INPUT_OR_AUX_PCB 76 行 / BRAKE_READY_OR_AUX_PCB 37 行 / SYSTEM_OR_HARNESS 8 行）
著录 rating 与 substitution_limit。

确定性、可审计设计原则（沿用 STOP 先例 build_stop_rating_annotation_20260917.py）：
  1. 输入仅来自 SELECTION_BOM_V36.csv、SELECTION_GAPS.json（fail-closed 断言 121 ⊆ rating 缺口）、
     PUBLIC_SOURCES.json、aux_v35/SELECTED_PARTS.json（+哈希绑定）与网表 XML（交叉核对）。
  2. 大电流/高压器件的 rating 只来自 MPN 解码或已归档源（implementation/sources/ 与
     aux_v35/sources/ 下 PDF，脚本内逐一 sha256 登记）；电流额定不猜测。
  3. 解析失败/无 MPN/无归档源 → UNKNOWN_NAMED_GAP 并写明缺什么，禁止零填充。
  4. STOP 板 4 行 UNKNOWN（U101 TPS3431、U311-U313 TLV6700）不在本范围、保持 UNKNOWN。
     注意差异：BRAKE 板 U302 同为 TLV6700DDCR，但 implementation/sources/tlv6700.pdf
     已归档（STOP 著录时仅核 PUBLIC_SOURCES.json 范围），故本行按 DATASHEET_ARCHIVED 著录；
     差异在 crosscheck_vs_stop_precedent 中显式登记，不回改 STOP 产物。

运行：python -B -X utf8 tools/build_system_rating_annotation_20260917.py
输出：
  results/electrical_selection_20260917/SYSTEM_RATING_ANNOTATION_20260917.json (+ .sha256)
  results/electrical_selection_20260917/SELECTION_GAPS_UPDATE2_20260917.json (+ .sha256)
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
GAPS_UPDATE1 = SEL_DIR / "SELECTION_GAPS_UPDATE_20260917.json"
PUB_SRC = IMPL / "results" / "stop_v36" / "PUBLIC_SOURCES.json"
NETLIST_XML = (IMPL / "results" / "stop_v36" / "pcb" / "thermal_filter_20260916"
               / "native_20260916_a" / "wp10_system.xml")
AUX_SEL = IMPL / "results" / "aux_v35" / "SELECTED_PARTS.json"
AUX_CALC = IMPL / "results" / "aux_v35" / "CALCULATIONS.json"
ST_RECORD = IMPL / "results" / "aux_v35" / "sources" / "ST_PUBLIC_SOURCE_RECORD.json"

OUT_JSON = SEL_DIR / "SYSTEM_RATING_ANNOTATION_20260917.json"
OUT_GAPS = SEL_DIR / "SELECTION_GAPS_UPDATE2_20260917.json"
DATE = "2026-09-17"

BOARDS = ("MAIN_INPUT_OR_AUX_PCB", "BRAKE_READY_OR_AUX_PCB", "SYSTEM_OR_HARNESS")

# ---------------------------------------------------------------------------
# 已归档源登记表：本脚本引用的每一个 PDF 都必须存在且可 sha256 复算。
# 哈希值在运行时计算并写入产物顶层 archived_sources，供独立复核。
# ---------------------------------------------------------------------------
ARCHIVED_FILES = {
    "eaton_1025hc_2025.pdf": "sources/eaton_1025hc_2025.pdf",
    "eaton_mda_2025.pdf": "sources/eaton_mda_2025.pdf",
    "74651195R.pdf": "sources/terminal_v29/74651195R.pdf",
    "wslp2726.pdf": "sources/wslp2726.pdf",
    "tnpw_e3_20260410_v24.pdf": "sources/tnpw_e3_20260410_v24.pdf",
    "lm5069_rev_g.pdf": "sources/lm5069_rev_g.pdf",
    "wima_mkp2_v24.pdf": "sources/wima_mkp2_v24.pdf",
    "wima_mks2_v25.pdf": "sources/wima_mks2_v25.pdf",
    "lxg_2026.pdf": "sources/lxg_2026.pdf",
    "cincon_chb500w.pdf": "sources/cincon_chb500w.pdf",
    "lm7480_q1.pdf": "sources/lm7480_q1.pdf",
    "lt3013.pdf": "sources/lt3013.pdf",
    "startup_tps3808.pdf": "sources/startup_tps3808.pdf",
    "csd19536ktt.pdf": "sources/csd19536ktt.pdf",
    "lps300.pdf": "sources/lps300.pdf",
    "ntcle100.pdf": "sources/ntcle100.pdf",
    "tlv6700.pdf": "sources/tlv6700.pdf",
    "tps3760_rev_a.pdf": "results/aux_v35/sources/tps3760_rev_a.pdf",
}

# aux_v35/SELECTED_PARTS.json 中登记、本脚本复核的哈希绑定（复核失败即拒绝引用）
AUX_HASH_BINDINGS = {
    "tnpw_e3_20260410_v24.pdf": "6f0508c568cb355aaf2accdd33fe3a780d3ea5ef207c4c9a71839a8acadc33a5",
    "wima_mks2_v25.pdf": "2a64392db00b639b6d0fca1d9e1a3aa38c1a5138ca6796a713914a9918d05fe9",
    "lt3013.pdf": "285ab2e67f086b183737c2b96080acf482c423d7170b8017768f2ae16d614103",
    "tps3760_rev_a.pdf": "eb7d626587f369ade98d55b60823ed28e4b4d955b41181c4443763cf0eef5e7d",
}

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


def parse_resistance_code(code: str):
    """解析 '47K5' / '2M20' / '100R' / '1K80' 式阻值码 → 欧姆。"""
    m = re.fullmatch(r"(\d+)([RKM])(\d{0,2})", code)
    if not m:
        return None
    a, letter, b = m.groups()
    mult = {"R": 1.0, "K": 1e3, "M": 1e6}[letter]
    mant = float(a + "." + b) if b else float(a)
    return mant * mult


def fmt_res(ohm: float) -> str:
    if ohm >= 1e6:
        return f"{ohm / 1e6:g} MΩ"
    if ohm >= 1e3:
        return f"{ohm / 1e3:g} kΩ"
    return f"{ohm:g} Ω"


def unknown(ref, what: str):
    return (None, "UNKNOWN_NAMED_GAP",
            "未定——rating 未著录前禁止替代",
            [what], f"解析失败/证据不足：{what}")


def value_human_part(value: str) -> str:
    if " / " in value:
        return value.split(" / ", 1)[1].strip()
    return value.strip()


# ---------------------------------------------------------------------------
# TNPW e3：阻值自 MPN 解码；功率/电压额定为分尺寸族级值
# 0603 行通用模式 P70=0.11W@125°C 膜温、100V 来自 aux_v35/SELECTED_PARTS.json
# （其 source_file=tnpw_e3_20260410_v24.pdf，哈希绑定已复核）；
# 0805/1210 行通用模式值 SELECTED_PARTS 未覆盖 → 著录数据手册技术规格表
# P70(2) 功率模式值并注明，通用模式值列 named gap。
# ---------------------------------------------------------------------------
TNPW_SIZE = {
    "0603": {"p70_note": "P70=0.11 W（通用模式，膜温 ≤125 °C，SELECTED_PARTS.json 记录，"
                         "源 tnpw_e3_20260410_v24.pdf 哈希复核一致；功率模式 P70(2)=0.21 W 见数据手册表）",
             "p70_W": 0.11, "umax_V": 100, "gap": None},
    "0805": {"p70_note": "P70(2)=0.26 W（tnpw_e3 数据手册技术规格表功率模式值；通用模式值未提取）",
             "p70_W": 0.26, "umax_V": 150,
             "gap": "TNPW0805 通用模式 P70（膜温 ≤125 °C）未提取：SELECTED_PARTS.json 仅覆盖 0603 行"},
    "1210": {"p70_note": "P70(2)=0.52 W（tnpw_e3 数据手册技术规格表功率模式值；通用模式值未提取）",
             "p70_W": 0.52, "umax_V": 200,
             "gap": "TNPW1210 通用模式 P70（膜温 ≤125 °C）未提取：SELECTED_PARTS.json 仅覆盖 0603 行"},
}


def decode_tnpw(ref, mpn, value, in_aux_selected: bool):
    m = re.fullmatch(r"TNPW(0603|0805|1210)(\d+[RKM]\d{0,2})([BF])EEA", mpn)
    if not m:
        return unknown(ref, f"MPN '{mpn}' 不匹配 Vishay TNPW e3 编码规则（0603/0805/1210）")
    size, code, tol_c = m.groups()
    ohm = parse_resistance_code(code)
    if ohm is None:
        return unknown(ref, f"阻值码 '{code}' 无法解析")
    info = TNPW_SIZE[size]
    rating = {
        "resistance": fmt_res(ohm),
        "resistance_ohm": ohm,
        "tolerance": "±0.1%" if tol_c == "B" else "±1%",
        "tempco_ppm": "±25 ppm/K",
        "rated_power_W": info["p70_W"],
        "rated_voltage_V": info["umax_V"],
        "case": f"{size} ({'1608' if size == '0603' else '2012' if size == '0805' else '3225'} metric)",
    }
    # 与 value 人读部分交叉核对（部分行 value 为 '38.3k' 等人读值）
    human = value_human_part(value)
    if human != mpn:
        m2 = re.match(r"([\d.]+)\s*(k|K|M|R)?", human)
        if not m2:
            return unknown(ref, f"value 人读部分 '{human}' 无法解析，无法交叉核对")
        hv = float(m2.group(1)) * {"": 1.0, "R": 1.0, "k": 1e3, "K": 1e3, "M": 1e6}[(m2.group(2) or "")]
        if abs(hv - ohm) > 1e-9 * max(ohm, 1.0):
            return unknown(ref, f"value 阻值 '{human}' 与 MPN 解码 {fmt_res(ohm)} 不一致")
    gaps = [info["gap"]] if info["gap"] else []
    tol_txt = "0.1%" if tol_c == "B" else "1%"
    sub = (f"仅 TNPW e3 同尺寸同阻值（{fmt_res(ohm)}）±{tol_txt} ±25ppm/K 薄膜可替代；"
           "禁普通厚膜（1%/100ppm）降等——分压比精度与温漂敏感")
    notes = ("Vishay TNPW e3 编码解码（B=±0.1%/F=±1%，E=±25ppm/K），value 交叉核对一致；"
             f"功率/电压额定：{info['p70_note']}；最大工作电压 {info['umax_V']}V 自 tnpw_e3 技术规格表")
    if in_aux_selected:
        notes += "；本行在 aux_v35/SELECTED_PARTS.json 有逐字段选型记录（哈希绑定复核一致）"
    return (rating, "DERIVED_FROM_PARTCODE", sub, gaps, notes)


# ---------------------------------------------------------------------------
# KEMET C0603C / C1210C 解码（沿用 STOP 先例码表）
# ---------------------------------------------------------------------------
KEMET_TOL = {"B": "±0.1pF", "C": "±0.25pF", "D": "±0.5pF",
             "F": "±1%", "G": "±2%", "J": "±5%", "K": "±10%", "M": "±20%"}
KEMET_VOLT = {"9": 6.3, "8": 4, "4": 16, "3": 25, "5": 50, "1": 100, "2": 200}
KEMET_DIEL = {"R": "X7R", "G": "C0G (NP0)"}


def decode_kemet(ref, mpn, value, size):
    m = re.fullmatch(r"C" + size + r"C(\d{3})([A-Z])(\d)([A-Z])ACTU", mpn)
    if not m:
        return unknown(ref, f"MPN '{mpn}' 不匹配 KEMET C{size}C 编码规则")
    digits, tol_c, volt_c, diel_c = m.groups()
    if tol_c not in KEMET_TOL or volt_c not in KEMET_VOLT or diel_c not in KEMET_DIEL:
        return unknown(ref, f"MPN '{mpn}' 含未登记编码字母（容差/电压/介质码表外）")
    pf = int(digits[:2]) * (10 ** int(digits[2]))
    rating = {
        "capacitance_pF": pf,
        "capacitance": f"{pf / 1e3:g} nF" if pf >= 1e3 else f"{pf:g} pF",
        "dielectric": KEMET_DIEL[diel_c],
        "tolerance": KEMET_TOL[tol_c],
        "rated_voltage_V": KEMET_VOLT[volt_c],
        "case": f"{size} ({'1608' if size == '0603' else '3225'} metric)",
    }
    human = value_human_part(value)
    if human != mpn:
        # 支持 '100nF 100V C0G' 与 '1nF_5pct_50V_C0G' 两种人读格式
        norm = human.replace("_", " ")
        m2 = re.search(r"([\d.]+)\s*(nF|uF|µF|pF)", norm)
        if not m2:
            return unknown(ref, f"value 人读部分 '{human}' 无法解析，无法交叉核对")
        hv = float(m2.group(1)) * {"pF": 1.0, "nF": 1e3, "uF": 1e6, "µF": 1e6}[m2.group(2)]
        if abs(hv - pf) >= 0.5:
            return unknown(ref, f"value 容值 '{human}' 与 MPN 解码不一致")
        mv = re.search(r"([\d.]+)\s*V", norm)
        if mv and abs(float(mv.group(1)) - KEMET_VOLT[volt_c]) > 1e-9:
            return unknown(ref, f"value 电压 '{human}' 与 MPN 解码 {KEMET_VOLT[volt_c]}V 不一致")
    sub = (f"同容值 C0G/NP0、{size}、额定电压 ≥{KEMET_VOLT[volt_c]:g}V、"
           f"容差不劣于 {KEMET_TOL[tol_c]} 可替代；禁二类介质（X7R/X5R/Y5V）降等")
    return (rating, "DERIVED_FROM_PARTCODE", sub, [],
            f"KEMET C{size}C 编码规则解码；value 人读部分交叉核对一致；"
            "KEMET 规格书 URL 在 BOM source 列（未归档本地）")


# ---------------------------------------------------------------------------
# Micro-Fit 3.0 连接器（沿用 STOP 先例族级声明）
# ---------------------------------------------------------------------------
def decode_microfit(ref, mpn):
    if mpn != "430450200":
        return unknown(ref, f"连接器 MPN '{mpn}' 未登记")
    return ({"family": "Molex Micro-Fit 3.0",
             "rated_current_A_per_contact": 5,
             "rated_voltage_V": 250},
            "DERIVED_FROM_FAMILY_DATASHEET",
            "仅 Molex Micro-Fit 3.0 同位数同安装方向（43045 系列）或厂商书面第二货源；"
            "替代件须 ≥5A/250V per contact",
            [],
            "Micro-Fit 3.0 族级公开额定 5A/250V per contact（族级常识，标注来源等级；"
            "Molex 产品页 URL 在 BOM source 列，族规格书未归档本地）")


# ---------------------------------------------------------------------------
# 逐位号著录表：DATASHEET_ARCHIVED 级（归档 PDF 已在 ARCHIVED_FILES 登记）
# ---------------------------------------------------------------------------
def arch(ref, rating, sub, notes, gaps=None):
    return (rating, "DATASHEET_ARCHIVED", sub, gaps or [], notes)


def decode_f201(ref, mpn):
    if mpn != "1025HC30-RTR":
        return unknown(ref, f"F201 MPN '{mpn}' 未登记")
    return arch(ref,
        {"family": "Eaton 1025HC 快断高电流贴片陶瓷管保险丝",
         "rated_current_A": 30,
         "voltage_rating": "250 VAC / 72 VDC",
         "interrupting_rating": "100 A @ 250 VAC / 500 A @ 72 VDC",
         "cold_resistance_mohm_typ": 1.7,
         "melting_I2t_A2s_typ": 112,
         "opening_time": "100% 额定: ≥4 h；200% 额定: ≤60 s",
         "size": "20–30 A 壳（10.0 × 3.15 × 1.70 mm）"},
        "仅 1025HC 同电流档（≥30A、250VAC/72VDC、快断、同壳尺寸）或厂商书面第二货源；"
        "I²t 与冷阻须复核书面批准；禁慢断（time-delay）替代",
        "Eaton 1025HC 数据手册 Technical Data 10572（2025-06 版，已归档 "
        "sources/eaton_1025hc_2025.pdf）1025HC30-R 行逐字段转录；"
        "BOM value 与 MPN 一致")


def decode_f202(ref, mpn):
    if mpn != "MDA-V-6-R":
        return unknown(ref, f"F202 MPN '{mpn}' 未登记")
    return arch(ref,
        {"family": "Eaton MDA 1/4\"×1-1/4\" 延时陶瓷管保险丝（-V 轴向引线）",
         "rated_current_A": 6,
         "voltage_rating": "250 VAC / 125 VDC",
         "interrupting_rating": "200 A @ 250 VAC；10000 A @ 125 VAC；10000 A @ 125 VDC",
         "cold_resistance_mohm_typ": 18,
         "melting_I2t_A2s_typ": 98.1,
         "opening_time": "100%: 4 h；135%: ≤60 min；200%: ≤120 s（延时型）"},
        "仅 MDA 同电流档（≥6A、250VAC/125VDC、延时型）或厂商书面第二货源；"
        "禁快断替代（上电浪涌耐受语义不同）",
        "Eaton MDA 数据手册 Technical Data 2002（2025-11 版，已归档 "
        "sources/eaton_mda_2025.pdf）MDA-6-R 行逐字段转录；-V = 轴向引线版本")


def decode_wurth_terminal(ref, mpn):
    if mpn != "74651195R":
        return unknown(ref, f"端子 MPN '{mpn}' 未登记")
    return arch(ref,
        {"family": "Würth WP-THRSH REDCUBE M5 外螺纹 THR 端子",
         "rated_current_A_at_20C": 85,
         "rated_voltage_V": None,
         "material": "黄铜镀锡",
         "thread": "M5",
         "tightening_torque_Nm": 2.2,
         "operating_temp_C": "-55 – +150"},
        "仅同 MPN 或厂商书面第二货源；替代端子须 ≥85 A @20 °C、M5、同 THR 封装，"
        "载流路径（PCB/接线耳/线缆截面）复核书面批准",
        "Würth 74651195R 数据手册 rev 002.001（2022-02-21，已归档 "
        "sources/terminal_v29/74651195R.pdf）：Rated Current I_R @20 °C = 85 A max "
        "（数据手册注明工作电流取决于 PCB、接线耳与线缆截面）",
        ["rated_voltage_V 未著录：数据手册未给额定电压（THR 端子，电压等级由系统设计决定）"])


def decode_wslp(ref, mpn):
    m = re.fullmatch(r"WSLP2726(2L000|L5000)FEA", mpn)
    if not m:
        return unknown(ref, f"MPN '{mpn}' 不匹配 WSLP2726 编码（已登记 2L000/L5000）")
    code = m.group(1)
    if code == "2L000":
        ohm, pwr, pwr_note = 0.002, 5.0, "5 W（1.3m–5mΩ 档，P70）"
    else:
        ohm, pwr, pwr_note = 0.0005, 12.0, "12 W（0.2m–0.5mΩ 档，基于 100 °C 端子温度，表注 2）"
    return arch(ref,
        {"family": "Vishay WSLP2726 Power Metal Strip 检流电阻",
         "resistance_ohm": ohm,
         "resistance": f"{ohm * 1e3:g} mΩ",
         "tolerance": "±1%（F 码）",
         "rated_power_W": pwr,
         "power_basis": pwr_note,
         "tempco_ppm": "±75 ppm/°C（元件级 TCR 0.5m–5mΩ 档，0–150 °C；元素级 <20 ppm/°C）",
         "operating_temp_C": "-65 – +170",
         "case": "2726"},
        "仅 WSLP2726 同阻值同容差（±1%）或厂商书面第二货源；大电流检流路径禁普通片阻替代，"
        "功率/TCR 不得降等",
        "Vishay WSLP2726 数据手册 doc 30179（已归档 sources/wslp2726.pdf）："
        f"阻值/容差自全球订货码解码（{code}= {ohm * 1e3:g} mΩ，F=±1%），"
        f"功率档位 {pwr_note} 自标准电气规格表；aux_v35/CALCULATIONS.json 中 "
        "shunts=0.0025 Ω（2 mΩ+0.5 mΩ 串联）与两值之和一致")


def decode_lm5069(ref, mpn):
    if mpn != "LM5069MM-1":
        return unknown(ref, f"U201 MPN '{mpn}' 未登记")
    return arch(ref,
        {"function": "正高压热插拔/浪涌电流控制器（带功率限制）",
         "supply_range_V": "9 – 80",
         "key_ratings": {"variant": "-1 = 故障后锁断（latch-off）",
                          "gate_drive": "内部高边电荷泵驱动外部 N 沟 MOSFET",
                          "features": "可调限流/功率限制/UVLO/OVLO/故障定时器"}},
        "仅同 MPN（LM5069MM-1 锁断版本）或厂商书面第二货源；"
        "禁 -2 自重启版本互换（故障恢复语义不同）",
        "TI LM5069 数据手册 SNVS452G（2020-01 修订，已归档 sources/lm5069_rev_g.pdf）："
        "9–80 V 工作范围、-1/-2 变体语义取自第 1 页 Features/Description",
        ["绝对最大额定表（7.1 节）未逐字段提取：已归档 PDF 可复核，著录从简"])


def decode_wima_mkp2(ref, mpn):
    table = {
        "MKP2C041001N00JSSD": {"cap": "1.0 µF", "vr": 63, "vac": 40},
        "MKP2D031001F00JSSD": {"cap": "0.1 µF", "vr": 100, "vac": 63},
    }
    if mpn not in table:
        return unknown(ref, f"WIMA MKP2 MPN '{mpn}' 未登记（已登记 C041001N00/D031001F00）")
    t = table[mpn]
    return arch(ref,
        {"family": "WIMA MKP 2 金属化聚丙烯（PP）薄膜电容 PCM 5 mm",
         "capacitance": t["cap"],
         "rated_voltage_VDC": t["vr"],
         "rated_voltage_VAC": t["vac"],
         "tolerance": "±5%（J 码）",
         "pitch_mm": 5,
         "operating_temp_C": "-55 – +100",
         "dielectric": "PP（脉冲级，自愈）"},
        "仅同 MPN 或 WIMA MKP2 同容值同额定电压 ±5% PCM5；"
        "禁聚酯（MKS）/二类介质降等——脉冲与损耗语义不同",
        "WIMA MKP 2 数据手册 rev 62.30（已归档 sources/wima_mkp2_v24.pdf）："
        f"{t['cap']} / {t['vr']} VDC 行逐字段转录（{mpn[:14]} 为该电压档表内订货码）；"
        "J=±5%、S=bulk、SD=6-2 mm 引线自数据手册 part number completion 节")


def decode_wima_mks2(ref, mpn):
    table = {
        "MKS2D041501M00JSSD": {"cap": "1.5 µF"},
        "MKS2D044701O00JSSD": {"cap": "4.7 µF"},
    }
    if mpn not in table:
        return unknown(ref, f"WIMA MKS2 MPN '{mpn}' 未登记（已登记 D041501M00/D044701O00）")
    t = table[mpn]
    return arch(ref,
        {"family": "WIMA MKS 2 金属化聚酯（PET）薄膜电容 PCM 5 mm",
         "capacitance": t["cap"],
         "rated_voltage_VDC": 100,
         "tolerance": "±5%（J 码）",
         "pitch_mm": 5,
         "operating_temp_C": "-55 – +100",
         "dielectric": "metallized polyester"},
        "仅同 MPN 或 WIMA MKS2 同容值同额定电压（100 VDC）±5% PCM5；"
        "禁二类陶瓷/电解降等；>85 °C DC 降额按 OEM 曲线",
        "aux_v35/SELECTED_PARTS.json 逐字段选型记录（rated_DC_V=100、5%、MKS2 族，"
        "源 sources/wima_mks2_v25.pdf rev 03.26，哈希绑定复核一致）；"
        "归档 PDF sources/wima_mks2_v25.pdf 可独立复核")


def decode_lxg(ref, mpn):
    if mpn != "ELXG101VSN222MR50S":
        return unknown(ref, f"C203 MPN '{mpn}' 未登记")
    return arch(ref,
        {"family": "United Chemi-Con LXG 105 °C 长寿命卡入式铝电解",
         "capacitance": "2200 µF",
         "tolerance": "±20%（M 码）",
         "rated_voltage_VDC": 100,
         "case_mm": "φ30 × 50",
         "ripple_current_Arms_105C_120Hz": 2.40,
         "endurance": "5000 h @ 105 °C（叠加额定纹波）",
         "leakage": "I = 0.02CV 或 3 mA 取小（20 °C，5 min）",
         "terminal": "VS 卡入式"},
        "仅同 MPN 或 LXG 同容值同电压档（2200 µF/100 V、φ30×50）；"
        "纹波 ≥2.40 Arms、寿命 ≥5000 h @105 °C 不得降等",
        "UCC LXG 目录 lxg_2026.pdf（已归档 sources/lxg_2026.pdf）："
        "ELXG101VSN222MR50S 标准额定行逐字段转录（100 V / 2200 µF / 30×50 / 2.40 Arms）")


def decode_smbj(ref, mpn):
    table = {"SMBJ30A-13-F": ("单向", "30A"), "SMBJ30CA-13-F": ("双向", "30CA")}
    if mpn not in table:
        return unknown(ref, f"TVS MPN '{mpn}' 未登记")
    direction, code = table[mpn]
    return ({"family": f"SMBJ 600W 贴片 TVS（{direction}）",
             "standoff_voltage_Vrwm_V": 30,
             "direction": direction,
             "case": "SMB (DO-214AA)",
             "peak_pulse_power_W": None,
             "clamping_voltage_V": None},
            "DERIVED_FROM_PARTCODE",
            "同 standoff ≥30 V、同向性、SMB 壳 600 W 级 TVS；"
            "替代须 Vbr/Vc@Ipp 复核书面批准（基线缺失）",
            "SMBJ 命名解码：30 = Vrwm 30 V，A = 单向 / CA = 双向（Diodes Inc. -13-F 卷带后缀）；"
            "SMBJ 族数据手册 URL 在 BOM source 列，未归档本地",
            ["峰值脉冲功率 PPPM（族级 600W）/Vbr/Vc@Ipp 未著录："
             "SMBJ5.0(C)A–SMBJ170(C)A 族数据手册未归档（PUBLIC_SOURCES.json 与 sources/ 均无此源）"])


def decode_stps3h100(ref, mpn):
    if mpn != "STPS3H100U":
        return unknown(ref, f"肖特基 MPN '{mpn}' 未登记")
    return ({"family": "ST STPS3H100 功率肖特基整流",
             "If_av_A": 3,
             "Vrrm_V": 100,
             "case": "SMB (STPS3H100U)",
             "Vf_V": None,
             "reverse_leakage": None},
            "DERIVED_FROM_PARTCODE",
            "同 MPN 或 ≥3 A / ≥100 V 肖特基 SMB；Vf 与高温泄漏复核书面批准",
            "ST 命名解码：3 = If(AV) 3 A，H100 = Vrrm 100 V（与 STPS30H100 同族规则一致）；"
            "aux_v35/sources/ST_PUBLIC_SOURCE_RECORD.json 记录 DS6597 Rev3 泄漏 1 mA max "
            "@125 °C/VR=100 V（agent 转述、原 PDF 未归档）——仅作保守设计场景，不作额定著录",
            ["Vf/热阻/全温泄漏未著录：stps3h100.pdf 未归档（仅 agent 转述记录，"
             "offline_original_PDF_available=false）"])


def decode_stps30h100(ref, mpn):
    if mpn != "STPS30H100CT":
        return unknown(ref, f"肖特基 MPN '{mpn}' 未登记")
    return ({"family": "ST STPS30H100 功率肖特基整流（共阴对管）",
             "If_av_A": 30,
             "Vrrm_V": 100,
             "case": "TO-220AB (CT 共阴)"},
            "DERIVED_FROM_PARTCODE",
            "同 MPN 或 ≥30 A / ≥100 V 共阴肖特基 TO-220AB；Vf 与热阻复核书面批准",
            "ST 命名解码：30 = If(AV) 30 A，H100 = Vrrm 100 V，CT = TO-220AB 共阴对管；"
            "数据手册未归档",
            ["Vf/热阻/泄漏未著录：stps30h100 数据手册未归档（sources/ 与 PUBLIC_SOURCES 均无此源）"])


def decode_csd19536(ref, mpn):
    if mpn != "CSD19536KTT":
        return unknown(ref, f"MOSFET MPN '{mpn}' 未登记")
    return arch(ref,
        {"type": "N 沟道 NexFET 功率 MOSFET",
         "Vds_V": 100,
         "Vgs_abs_V": "±20",
         "Rds_on_mohm_typ": {"Vgs6V": 2.2, "Vgs10V": 2.0},
         "Id_A": {"package_limited": 200, "silicon_limited_25C": 272},
         "Qg_nC_typ": 118,
         "junction_temp_C": "-55 – +175",
         "case": "D2PAK (TO-263)"},
        "仅同 MPN 或厂商书面第二货源；替代须 Vds ≥100 V、Rds_on ≤2.2 mΩ @6 V、"
        "D2PAK 封装、Qg/热阻复核书面批准",
        "TI CSD19536KTT 数据手册 SLPS540C（2025-05 修订，已归档 sources/csd19536ktt.pdf）："
        "Product Summary 与 Absolute Maximum Ratings 表逐字段转录")


def decode_2n7002(ref, mpn):
    if mpn != "2N7002K-7":
        return unknown(ref, f"MOSFET MPN '{mpn}' 未登记")
    return ({"type": "N 沟道小信号 MOSFET",
             "Vds_V": 60,
             "case": "SOT-23",
             "key_ratings": {"Vds_V": 60}},
            "DERIVED_FROM_PARTCODE",
            "优先同 MPN；替代须 Vds ≥60 V N 沟 SOT-23，Rds_on/Id 复核书面批准（基线缺失）",
            "Vds=60 V 为 2N7002 族级额定（MPN 解码 + 族级常识，标注来源等级，同 STOP 板 "
            "IRL630 先例处理）；ds30896.pdf URL 在 BOM source 列，未归档本地",
            ["Rds_on/Id/Vgs(th) 未著录：2N7002K 数据手册未归档"])


def decode_q201(ref, mpn):
    if mpn != "IXTH75N10L2":
        return unknown(ref, f"Q201 MPN '{mpn}' 未登记")
    return ({"type": "N 沟道功率 MOSFET（L2 = 线性模式族）",
             "Vds_V": 100,
             "Id_A": 75,
             "case": "TO-247 (IXTH)",
             "key_ratings": {"Vds_V": 100, "Id_A": 75}},
            "DERIVED_FROM_PARTCODE",
            "优先同 MPN（IXTH75N10L2）；替代须 Vds ≥100 V、Id ≥75 A、TO-247，"
            "且线性区 SOA/热阻复核书面批准（热插拔/线性应用场景，基线缺失）",
            "IXYS/Littelfuse 命名解码：75 = Id 75 A、N10 = Vds 100 V、L2 = 线性模式后缀"
            "（族级常识，标注来源等级，同 STOP 板 IRL630 先例处理）；"
            "BOM source 列 Littelfuse PDF URL 未归档本地；"
            "aux_v35/CALCULATIONS.json 预算使用 Q201_25C=0.021 Ω 为场景假设值（非额定著录）",
            ["Rds_on/线性区 SOA/Vgs(th)/Qg 未著录：IXT-75N10 数据手册未归档"])


def decode_chb500w(ref, mpn):
    if mpn != "CHB500W-24S24N":
        return unknown(ref, f"U203 MPN '{mpn}' 未登记")
    return arch(ref,
        {"family": "CINCON CHB500W 500 W 半砖隔离 DC-DC",
         "input_range_V": "9.5 – 40（24S24 行；24Vin 族 9–40）",
         "output": "24 VDC / 21.0 A max（500 W 级）",
         "efficiency_pct": {"full_load": 91.5, "typ": 91},
         "isolation": "3000 Vdc / 1875 Vac 1 min（I/O）",
         "remote_onoff_logic": "N = 负逻辑",
         "abs_max_input": "-0.3 – 40 V 连续；50 V / 100 ms 浪涌",
         "protections": "OTP/OCP（110–140% hiccup）/OVP（120–140%）/UVLO",
         "case_temp_C": "-40 – +105（max case 110）"},
        "仅同 MPN（CHB500W-24S24N）或厂商书面第二货源；输入范围/24 V 输出/隔离等级/"
        "遥控逻辑极性不得变更",
        "CINCON CHB500W 数据手册（已归档 sources/cincon_chb500w.pdf）："
        "CHB500W-24S24 型号表行与绝对最大额定表逐字段转录；"
        "aux_v35/CALCULATIONS.json 中 eta=0.85/0.9 为场景假设（低于手册 91.5%，保守侧）")


def decode_lm7480(ref, mpn):
    if mpn != "LM74800QDRRRQ1":
        return unknown(ref, f"U204 MPN '{mpn}' 未登记")
    return arch(ref,
        {"function": "理想二极管控制器（带负载突降保护）",
         "supply_range_V": "3 – 65",
         "reverse_protection_V": -65,
         "qualification": "AEC-Q100 Grade 1（-40 – +125 °C）",
         "case": "12-Pin WSON"},
        "仅同 MPN（LM74800QDRRRQ1 车规）或厂商书面第二货源",
        "TI LM7480-Q1 数据手册 SNOSD95C（2020-12 修订，已归档 sources/lm7480_q1.pdf）："
        "3–65 V 输入、-65 V 反接保护取自第 1 页 Features/Description")


def decode_lt3013(ref, mpn, extra_note=""):
    if mpn != "LT3013EDE#PBF":
        return unknown(ref, f"LT3013 MPN '{mpn}' 未登记")
    return arch(ref,
        {"function": "高压微功耗 LDO（带 PWRGD）",
         "supply_range_V": "4 – 80",
         "output_current_mA": 250,
         "dropout_V": 0.4,
         "output_adjust_range_V": "1.24 – 60",
         "iq_uA": 65,
         "case": "DFN-12 (3×4, EP)"},
        "仅同 MPN 或厂商书面第二货源；禁低压 LDO 替代（80 V 输入耐压为选型关键）",
        "Analog Devices LT3013 数据手册 RevE（已归档 sources/lt3013.pdf，"
        "sha256 与 aux_v35/CALCULATIONS.json source_bindings 登记值一致）；"
        "4–80 V/250 mA/400 mV 取自第 1 页 Features" + extra_note)


def decode_tps3808g01(ref, mpn):
    if mpn != "TPS3808G01DBVR":
        return unknown(ref, f"U206 MPN '{mpn}' 未登记")
    return arch(ref,
        {"supply_range_V": "1.8 – 6.5", "abs_max_V": 7,
         "key_ratings": {"threshold_V": 0.405, "monitored_rail": "可调（SENSE 分压）",
                          "reset_output": "开漏低有效",
                          "iq_typ_uA": 2.4, "threshold_accuracy_pct_typ": 0.5}},
        SUB_IC,
        "TI TPS3808 数据手册 SBVS050N（PUBLIC_SOURCES.json 已归档条目，本地 "
        "sources/startup_tps3808.pdf 可复核）；G01 为可调阈值 0.405 V 基准版本"
        "（著录与 STOP 板 U102 先例一致）")


def decode_tps3760(ref, mpn):
    if mpn != "TPS3760A015DYYR":
        return unknown(ref, f"U208 MPN '{mpn}' 未登记")
    return arch(ref,
        {"function": "高压窗口监控器（可编程检测/复位延时）",
         "supply_range_V": "2.7 – 65",
         "sense_reset_graded_V": 65,
         "iq_typ_uA": 1,
         "case": "SOT-14 (DYY)"},
        "仅同 MPN（A015 变体）或厂商书面第二货源；变体阈值档不得互换",
        "TI TPS3760 数据手册 SBVS420A（已归档 results/aux_v35/sources/tps3760_rev_a.pdf，"
        "sha256 与 aux_v35/CALCULATIONS.json source_bindings 登记值一致）："
        "2.7–65 V 供电、SENSE/RESET 65 V 取自第 1 页 Features",
        ["A015 变体的具体阈值/迟滞档未解码：数据手册订货码表未提取，"
         "aux_v35/CALCULATIONS.json 以分压网络场景值（UV 16.5–17.1 V）运行"])


def decode_tlv6700(ref, mpn):
    if mpn != "TLV6700DDCR":
        return unknown(ref, f"TLV6700 MPN '{mpn}' 未登记")
    return arch(ref,
        {"function": "微功耗 18 V 窗口比较器（400 mV 基准）",
         "supply_range_V": "1.8 – 18",
         "key_ratings": {"reference_V": 0.4,
                          "threshold_accuracy": "±0.5% max @25 °C；±1.0% max 全温",
                          "iq_typ_uA": 5.5,
                          "output": "双开漏，额定 18 V",
                          "hysteresis_mV_typ": 5.5},
         "case": "SOT-23-6 (DDC)"},
        SUB_IC,
        "TI TLV6700 数据手册 SNVSAV2B（2019-11 修订，已归档 sources/tlv6700.pdf）："
        "1.8–18 V、400 mV 基准、开漏 18 V 取自第 1 页；"
        "注意：STOP 板同 MPN 行（U311/U312/U313）在 STOP 著录时仅核 PUBLIC_SOURCES.json "
        "范围判 UNKNOWN，本行按 implementation/sources/ 已归档源补级，差异已在顶层登记")


def decode_lps300(ref, mpn):
    if mpn != "LPS0300H1R00JB":
        return unknown(ref, f"制动电阻 MPN '{mpn}' 未登记")
    return arch(ref,
        {"family": "Vishay Sfernice LPS 300 厚膜功率电阻（散热器安装）",
         "resistance_ohm": 1.0,
         "tolerance": "±5%（J 码）",
         "rated_power_W": 300,
         "power_basis": "300 W @ +85 °C 底板温度（需散热器）",
         "limiting_voltage_V": 5000,
         "tempco_ppm": "±500 ppm/°C（R ≤ 1 Ω 档）",
         "dielectric_strength": "H 码 = 7 kV RMS 1 min",
         "inductance_uH_max": 0.1,
         "operating_temp_C": "-55 – +120",
         "mounting": "M4 螺钉 2 N·m（电气与散热器各 2 N·m）"},
        "仅同 MPN 或厂商书面第二货源；制动泄放路径禁低功率/绕线（高感）替代，"
        "阻值/功率/无感特性不得降等",
        "Vishay LPS 300 数据手册 doc 50052 Rev 13-Apr-2021（已归档 sources/lps300.pdf）："
        "全球订货码解码 LPS0300H1R00JB = LPS 300 / H(7 kV) / 1R00 / J(±5%) / B(15 只盒装)；"
        "300 W@85 °C、5000 V 限制电压、±500 ppm/°C 自标准电气规格表；"
        "sources/BRAKE_MECHANICAL_SOURCE_MANIFEST.json 登记 OEM 3D 模型绑定（doc 50061）")


def decode_ntcle100(ref, mpn):
    if mpn != "NTCLE100E3103GB0":
        return unknown(ref, f"NTC MPN '{mpn}' 未登记")
    return arch(ref,
        {"family": "Vishay NTCLE100E3 径向引线 NTC 热敏电阻",
         "R25_ohm": 10000,
         "R25_tolerance": "±2%（G 码）",
         "B25_85_K": 3977,
         "B_tolerance_pct": 0.75,
         "max_power_mW_at_55C": 500,
         "operating_temp_C": "-40 – +125（短时 ≤150）"},
        "仅同 MPN 或同 R25（10 kΩ）/同 B25/85（3977 K）/同容差 NTC；"
        "禁 B 值不同替代（测温曲线改变，属功能安全相关）",
        "Vishay NTCLE100E3 数据手册（已归档 sources/ntcle100.pdf）："
        "电气数据与订货信息表 103*B0 行——10 000 Ω / 3977 K / B 容差 0.75%；"
        "G=±2% 自 IEC 容差字母")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    # fail-closed：所有登记的归档源必须存在
    archived_sources = []
    for name, rel in sorted(ARCHIVED_FILES.items()):
        p = IMPL / rel
        if not p.exists():
            raise SystemExit(f"FAIL: 登记的归档源缺失: {rel}")
        digest = sha256_of(p)
        binding = AUX_HASH_BINDINGS.get(name)
        if binding is not None and digest != binding:
            raise SystemExit(f"FAIL: 哈希绑定复核失败 {name}: 期望 {binding} 实得 {digest}")
        archived_sources.append({"file": rel, "sha256": digest,
                                 "aux_hash_binding_verified": binding is not None})

    bom_sha = sha256_of(BOM_CSV)
    gaps_sha = sha256_of(GAPS_JSON)
    update1_sha = sha256_of(GAPS_UPDATE1)

    gaps_doc = json.loads(GAPS_JSON.read_text(encoding="utf-8"))
    update1_doc = json.loads(GAPS_UPDATE1.read_text(encoding="utf-8"))
    aux_sel_doc = json.loads(AUX_SEL.read_text(encoding="utf-8"))
    pub_doc = json.loads(PUB_SRC.read_text(encoding="utf-8"))
    archived_parts_pub = {s["part"] for s in pub_doc["sources"]}

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

    # 读 BOM，取三板 REAL_PART_CANDIDATE 行
    with BOM_CSV.open("r", encoding="utf-8", newline="") as fh:
        rows_all = list(csv.DictReader(fh))
    rows = [r for r in rows_all
            if r["board"] in BOARDS and r["class_"] == "REAL_PART_CANDIDATE"]
    refs = [r["ref"] for r in rows]
    assert len(refs) == len(set(refs)), "位号重复"
    if len(rows) != 121:
        raise SystemExit(f"FAIL: 范围行数 {len(rows)} != 121")

    # fail-closed 断言：121 位号必须全部 ⊆ SELECTION_GAPS rating 缺口集合
    rating_gap_refs = set(gaps_doc["gaps"]["rating"]["refs"])
    not_in_gaps = [r for r in refs if r not in rating_gap_refs]
    if not_in_gaps:
        raise SystemExit(f"FAIL: 以下位号不在 SELECTION_GAPS rating 缺口清单内: {not_in_gaps}")
    # 同时断言与 STOP 板著录无交集（STOP 产物 103 行不可覆盖）
    stop_ann = SEL_DIR / "STOP_RATING_ANNOTATION_20260917.json"
    stop_doc = json.loads(stop_ann.read_text(encoding="utf-8"))
    stop_refs = {row["ref"] for row in stop_doc["rows"]}
    overlap = [r for r in refs if r in stop_refs]
    if overlap:
        raise SystemExit(f"FAIL: 与 STOP 著录行交集非空: {overlap}")

    aux_refs = set(aux_sel_doc.keys())

    out_rows = []
    netlist_mismatches = []
    for r in rows:
        ref, mpn, value, fp = r["ref"], r["MPN"].strip(), r["value"], r["footprint"]
        prefix = re.match(r"[A-Z]+", ref).group(0)

        if not mpn and value.strip() == "LT3013EDE#PBF":
            # BOM MPN 列为空但 value 字段为完整已归档 MPN（U301）——按 value 著录并记具名缺口
            res = decode_lt3013(ref, value.strip())
            result = (res[0], res[1], res[2],
                      ["BOM MPN 列与 footprint 列为空：MPN 取自 value 字段（'LT3013EDE#PBF'），"
                       "著录前须回填 BOM 结构化字段"] + res[3],
                      res[4] + "；注意：本行 MPN 自 value 字段取得（BOM MPN 列空）")
        elif not mpn and value.strip() in ("MAX5048CAUT+T", "MAX16053AUT+T"):
            result = unknown(ref, f"{value.strip()} 数据手册未归档（PUBLIC_SOURCES.json 与 "
                                  "implementation/sources/ 均无此源；BOM MPN 列空、value 含 MPN、"
                                  "仅有 URL）：供电范围、绝对最大额定、关键额定全部缺失，"
                                  "须归档数据手册并回填 BOM MPN 列后补录")
        elif not mpn:
            result = unknown(ref, f"无 MPN（value='{value}'，footprint='{fp or '空'}'）："
                                  "缺厂商订货码与数据手册，无法著录 rating")
        elif mpn == "1025HC30-RTR":
            result = decode_f201(ref, mpn)
        elif mpn == "MDA-V-6-R":
            result = decode_f202(ref, mpn)
        elif mpn == "74651195R":
            result = decode_wurth_terminal(ref, mpn)
        elif mpn == "IXTH75N10L2":
            result = decode_q201(ref, mpn)
        elif mpn.startswith("WSLP2726"):
            result = decode_wslp(ref, mpn)
        elif mpn.startswith("TNPW"):
            result = decode_tnpw(ref, mpn, value, ref in aux_refs)
        elif mpn == "LM5069MM-1":
            result = decode_lm5069(ref, mpn)
        elif mpn.startswith("MKP2"):
            result = decode_wima_mkp2(ref, mpn)
        elif mpn.startswith("MKS2"):
            result = decode_wima_mks2(ref, mpn)
        elif mpn == "ELXG101VSN222MR50S":
            result = decode_lxg(ref, mpn)
        elif mpn.startswith("SMBJ"):
            result = decode_smbj(ref, mpn)
        elif mpn == "STPS3H100U":
            result = decode_stps3h100(ref, mpn)
        elif mpn == "STPS30H100CT":
            result = decode_stps30h100(ref, mpn)
        elif mpn == "CSD19536KTT":
            result = decode_csd19536(ref, mpn)
        elif mpn == "2N7002K-7":
            result = decode_2n7002(ref, mpn)
        elif mpn == "CHB500W-24S24N":
            result = decode_chb500w(ref, mpn)
        elif mpn == "LM74800QDRRRQ1":
            result = decode_lm7480(ref, mpn)
        elif mpn == "LT3013EDE#PBF":
            extra = ""
            if not fp:
                extra = ("；注意：BOM 本行 footprint 为空（网表交叉核对见 netlist_crosscheck），"
                         "不影响 rating 著录")
            result = decode_lt3013(ref, mpn, extra)
        elif mpn == "TPS3808G01DBVR":
            result = decode_tps3808g01(ref, mpn)
        elif mpn == "TPS3760A015DYYR":
            result = decode_tps3760(ref, mpn)
        elif mpn == "TLV6700DDCR":
            result = decode_tlv6700(ref, mpn)
        elif mpn == "LPS0300H1R00JB":
            result = decode_lps300(ref, mpn)
        elif mpn == "NTCLE100E3103GB0":
            result = decode_ntcle100(ref, mpn)
        elif mpn.startswith("C1210C"):
            result = decode_kemet(ref, mpn, value, "1210")
            if result[1] != "UNKNOWN_NAMED_GAP" and ref in aux_refs:
                result = (result[0], result[1], result[2], result[3],
                          result[4] + "；aux_v35/SELECTED_PARTS.json 有该 MPN 选型记录"
                          "（100 V/5%/C0G，TCR 30 ppm/K），与解码一致")
        elif mpn.startswith("C0603C"):
            result = decode_kemet(ref, mpn, value, "0603")
        elif mpn == "430450200":
            result = decode_microfit(ref, mpn)
        elif mpn in ("TPS26600PWPR", "MAX5048CAUT+T", "MAX16053AUT+T"):
            result = unknown(ref, f"{mpn} 数据手册未归档（PUBLIC_SOURCES.json 与 "
                                  "implementation/sources/ 均无此源；BOM 仅有 URL）："
                                  "供电范围、绝对最大额定、关键额定全部缺失，须归档数据手册后补录")
        else:
            result = unknown(ref, f"MPN '{mpn}' 未在任何登记解码器/归档源表中")

        rating, sclass, sub, named_gaps, notes = result

        # 网表交叉核对
        nl = netlist.get(ref)
        nl_note = "网表无此位号"
        if nl is not None:
            diffs = []
            if nl["footprint"] and fp and nl["footprint"] != fp:
                diffs.append(f"footprint: BOM='{fp}' vs 网表='{nl['footprint']}'")
            if nl["MPN"] and mpn and nl["MPN"] != mpn:
                diffs.append(f"MPN: BOM='{mpn}' vs 网表='{nl['MPN']}'")
            if diffs:
                netlist_mismatches.append({"ref": ref, "diffs": diffs})
                nl_note = "不一致: " + "; ".join(diffs)
            else:
                nl_note = "footprint/MPN 与网表一致（或网表字段为空不比对）"

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
    board_counts = {}
    for row in out_rows:
        board_counts[row["board"]] = board_counts.get(row["board"], 0) + 1

    annotation = {
        "schema": "WP10_V36_SYSTEM_RATING_ANNOTATION",
        "date": DATE,
        "scope_boards": list(BOARDS),
        "source_bom": "results/electrical_selection_20260917/SELECTION_BOM_V36.csv",
        "source_bom_sha256": bom_sha,
        "source_gaps": "results/electrical_selection_20260917/SELECTION_GAPS.json",
        "source_gaps_sha256": gaps_sha,
        "public_sources": "results/stop_v36/PUBLIC_SOURCES.json",
        "public_source_parts": sorted(archived_parts_pub),
        "aux_evidence": {
            "selected_parts": "results/aux_v35/SELECTED_PARTS.json",
            "selected_parts_sha256": sha256_of(AUX_SEL),
            "calculations": "results/aux_v35/CALCULATIONS.json",
            "calculations_sha256": sha256_of(AUX_CALC),
            "st_source_record": "results/aux_v35/sources/ST_PUBLIC_SOURCE_RECORD.json",
            "st_source_record_sha256": sha256_of(ST_RECORD),
        },
        "archived_sources": archived_sources,
        "netlist_crosscheck_source": "results/stop_v36/pcb/thermal_filter_20260916/"
                                     "native_20260916_a/wp10_system.xml",
        "netlist_footprint_mpn_mismatches": netlist_mismatches,
        "crosscheck_vs_stop_precedent": [
            "STOP 板著录（STOP_RATING_ANNOTATION_20260917.json，103 行）未改动；本范围 121 行与其无交集（脚本断言）。",
            "TNPW 功率/电压额定：STOP 著录时 tnpw_e3 按 PUBLIC_SOURCES.json 判未归档、记具名缺口；"
            "本范围改用 implementation/sources/tnpw_e3_20260410_v24.pdf（与 aux_v35/SELECTED_PARTS.json "
            "哈希绑定复核一致）著录分尺寸额定。STOP 板 TNPW 行的具名缺口不回改，留待统一收口。",
            "TLV6700DDCR：STOP 板 U311/U312/U313 保持 UNKNOWN（仅核 PUBLIC_SOURCES.json）；"
            "本范围 BRAKE 板 U302 按 implementation/sources/tlv6700.pdf（SNVSAV2B）著录为 "
            "DATASHEET_ARCHIVED。两处范围不同导致的口径差异在此登记，STOP 产物不回改。",
            "STPS3H100U：aux_v35/sources/ST_PUBLIC_SOURCE_RECORD.json 为 agent 转述"
            "（offline_original_PDF_available=false），仅作场景证据引用，不升级为 DATASHEET_ARCHIVED。",
        ],
        "coverage": {
            "total": len(out_rows),
            "composition_note": "三板全部 REAL_PART_CANDIDATE 行，按板构成: " +
                                ", ".join(f"{k}={v}" for k, v in sorted(board_counts.items())),
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

    # --- SELECTION_GAPS 二次更新（不覆盖原文件与 UPDATE_20260917） ---
    resolved_refs = sorted(row["ref"] for row in out_rows
                           if row["rating_source_class"] != "UNKNOWN_NAMED_GAP")
    # 口径：UPDATE1 的 125 行剩余 = 121 本范围 + 4 STOP UNKNOWN；
    # 本期解决 = 本范围非 UNKNOWN 行；剩余 = UPDATE1 剩余减去本期解决
    update1_remaining = update1_doc["changes"]["rating"]["remaining_refs"]
    resolved_set = set(resolved_refs)
    remaining_rating = [r for r in update1_remaining if r not in resolved_set]
    update1_remaining_sub = update1_doc["changes"]["substitution_limit"]["remaining_refs"]
    remaining_sub = [r for r in update1_remaining_sub if r not in resolved_set]

    gaps_update = {
        "schema": "WP10_V36_SELECTION_GAPS_UPDATE",
        "date": DATE,
        "supersedes_in_part": ["results/electrical_selection_20260917/SELECTION_GAPS.json",
                               "results/electrical_selection_20260917/SELECTION_GAPS_UPDATE_20260917.json"],
        "source_gaps_sha256": gaps_sha,
        "previous_update": "results/electrical_selection_20260917/SELECTION_GAPS_UPDATE_20260917.json",
        "previous_update_sha256": update1_sha,
        "rating_annotations": [
            {"file": "results/electrical_selection_20260917/STOP_RATING_ANNOTATION_20260917.json",
             "sha256": sha256_of(stop_ann), "scope": "STOP_CONTROL_PCB 103 行"},
            {"file": "results/electrical_selection_20260917/SYSTEM_RATING_ANNOTATION_20260917.json",
             "sha256": ann_sha, "scope": "MAIN_INPUT/BRAKE/HARNESS 121 行"},
        ],
        "scope": "三板 121 行 rating/substitution_limit 著录后剩余缺口；"
                 "原 SELECTION_GAPS.json 与 SELECTION_GAPS_UPDATE_20260917.json 均未改动",
        "changes": {
            "rating": {"before": gaps_doc["gaps"]["rating"]["count"],
                       "resolved_stop_board": update1_doc["changes"]["rating"]["resolved_stop_board"],
                       "resolved_system_boards": len(resolved_refs),
                       "still_unknown_stop_board": 4,
                       "still_unknown_system_boards": len(unknown_rows),
                       "after": len(remaining_rating),
                       "remaining_refs": remaining_rating},
            "substitution_limit": {"before": gaps_doc["gaps"]["substitution_limit"]["count"],
                                   "resolved_stop_board": update1_doc["changes"]["substitution_limit"]["resolved_stop_board"],
                                   "resolved_system_boards": len(resolved_refs),
                                   "still_unknown_stop_board": 4,
                                   "still_unknown_system_boards": len(unknown_rows),
                                   "after": len(remaining_sub),
                                   "remaining_refs": remaining_sub},
        },
        "unchanged_gap_categories": {
            k: v["count"] for k, v in gaps_doc["gaps"].items()
            if k not in ("rating", "substitution_limit")},
        "remaining_unknown_breakdown": {
            "stop_board_unchanged": update1_doc["unknown_named_gap_rows"],
            "system_boards_new": [
                {"ref": row["ref"], "board": row["board"], "MPN": row["MPN"],
                 "named_gaps": row["named_gaps"]}
                for row in unknown_rows],
        },
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
    print(f"三板 REAL_PART_CANDIDATE 行数: {len(out_rows)}")
    print("source_class 分布:")
    for k, v in sorted(dist.items()):
        print(f"  {k}: {v}")
    print(f"named_gaps 非空行数（含 UNKNOWN）: {len(named_gap_rows)}")
    print(f"网表 footprint/MPN 交叉核对不一致: {len(netlist_mismatches)}")
    if unknown_rows:
        print("UNKNOWN_NAMED_GAP 清单:")
        for row in unknown_rows:
            print(f"  {row['ref']} [{row['board']}] ({row['MPN'] or '无MPN'}): {row['named_gaps'][0][:80]}")
    print(f"rating 缺口: {update1_doc['changes']['rating']['after']} -> {len(remaining_rating)}"
          f"（本期解决 {len(resolved_refs)}；剩余 = 4 STOP UNKNOWN + {len(unknown_rows)} 本期 UNKNOWN）")
    print(f"产物: {OUT_JSON}")
    print(f"产物: {OUT_GAPS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
