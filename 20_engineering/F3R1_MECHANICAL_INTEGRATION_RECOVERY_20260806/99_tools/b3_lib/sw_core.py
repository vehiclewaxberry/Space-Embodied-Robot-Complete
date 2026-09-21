"""B3 共享 SolidWorks COM 层。

连接/文档辅助改编自本地技能 solidworks-automation/scripts/sw_connect.py（保持语义，
增加 fail-closed 与日志）。单位约定：本层所有公开函数接受 **毫米/度**，内部转 米/弧度
（SolidWorks API 单位）。任何 COM 失败抛 B3FailClosed，调用方不得吞异常继续。
"""
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pythoncom
import win32com.client
from win32com.client import VARIANT

V2_ROOT = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_0")
LOG_DIR = V2_ROOT / "evidence" / "build_logs"


class B3FailClosed(RuntimeError):
    """构建失败即停：保存现场日志，不猜测修复。"""


def _mm(v):
    return float(v) / 1000.0


def _deg(v):
    return float(v) * math.pi / 180.0


class BuildLog:
    def __init__(self, stage: str):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.stage = stage
        self.path = LOG_DIR / f"{stage}.jsonl"
        self.t0 = time.time()

    def event(self, kind: str, **kw):
        rec = {"t_utc": datetime.now(timezone.utc).isoformat(), "stage": self.stage,
               "kind": kind, **kw}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{self.stage}] {kind}: " + json.dumps(kw, ensure_ascii=False)[:200])

    def fail(self, msg: str, **kw):
        self.event("FAIL_CLOSED", message=msg, **kw)
        raise B3FailClosed(f"{self.stage}: {msg}")


def get_com_member(obj, attr_name, *args):
    member = getattr(obj, attr_name)
    return member(*args) if callable(member) else member


_SLDWORKS_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
_tlb_module = None


def _sw_module():
    """加载 makepy 生成的 sldworks 类型库模块（须先手动 makepy sldworks.tlb）。"""
    global _tlb_module
    if _tlb_module is None:
        from win32com.client import gencache
        _tlb_module = gencache.EnsureModule(*_SLDWORKS_TLB)
        if _tlb_module is None:
            raise B3FailClosed("sldworks 类型库 makepy 模块缺失："
                               "python -m win32com.client.makepy <SW>/sldworks.tlb")
    return _tlb_module


def cast(obj, iface):
    """按接口名强转到早绑定类（绕过 CastTo 对 EnsureDispatch 的依赖）。

    SolidWorks 的 COM 对象不支持 GetTypeInfo 自动 makepy，因此用
    QueryInterface(接口 IID) + 生成类直接包装。失败原样返回。
    """
    if obj is None:
        return None
    try:
        klass = getattr(_sw_module(), iface)
        ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
        return klass(ole)
    except Exception:
        return obj


def byref_i4():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def empty_dispatch():
    return VARIANT(pythoncom.VT_DISPATCH, None)


def connect(log: BuildLog, wait_seconds=25, visible=False):
    """visible=False 无头模式（默认）：低内存机器上省图形缓冲，显著减少
    SolidWorks '系统内存极低' 模态框；视图导出等需要渲染的步骤显式传 True。"""
    mode = "existing"
    try:
        sw = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception:
        mode = "launched"
        sw = win32com.client.Dispatch("SldWorks.Application")
        time.sleep(wait_seconds)
    sw = cast(sw, "ISldWorks")
    if type(sw).__name__ == "CDispatch":
        log.fail("ISldWorks CastTo 失败——makepy 早绑定模块缺失，先运行 "
                 "python -m win32com.client.makepy <SOLIDWORKS>/sldworks.tlb")
    sw.Visible = bool(visible)
    try:
        sw.UserControl = True   # 防止最后一个 COM 客户端断开时 SolidWorks 自动退出
    except Exception:
        pass
    log.event("SW_CONNECT", mode=mode)
    rev = get_com_member(sw, "RevisionNumber")
    log.event("SW_VERSION", revision=rev, year=int(rev.split(".")[0]) - 8 + 2000)
    return sw


def find_template(sw, doc_type="part"):
    import glob
    type_map = {"part": (sw.GetUserPreferenceStringValue(24), "*.prtdot"),
                "assembly": (sw.GetUserPreferenceStringValue(25), "*.asmdot")}
    default_path, pattern = type_map[doc_type]
    if default_path:
        for root in str(default_path).split(";"):
            root = root.strip().strip('"')
            if root and os.path.isfile(root):
                return root
            if root and os.path.isdir(root):
                m = glob.glob(os.path.join(root, pattern))
                if m:
                    return m[0]
    for d in (r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates",
              r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\chinese-simplified",
              r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english"):
        m = glob.glob(os.path.join(d, pattern))
        if m:
            return m[0]
    raise B3FailClosed(f"找不到 {doc_type} 模板")


def new_document(sw, log: BuildLog, doc_type="part", template=None):
    template = template or find_template(sw, doc_type)
    model = sw.NewDocument(template, 0, 0, 0)
    if model is None:
        for _ in range(20):
            model = sw.ActiveDoc
            if model is not None:
                break
            time.sleep(0.25)
    if model is None:
        log.fail(f"NewDocument({doc_type}) 未返回文档", template=template)
    log.event("DOC_NEW", doc_type=doc_type, template=template)
    return cast(model, "IModelDoc2")


def _unpack(ret):
    """早绑定 byref 参数以返回元组形式给出：(retval, out1, out2, ...)。"""
    if isinstance(ret, tuple):
        return ret[0], list(ret[1:])
    return ret, []


def open_document(sw, log: BuildLog, file_path, read_only=False):
    ext = os.path.splitext(str(file_path))[1].lower()
    doc_type = {".sldprt": 1, ".sldasm": 2}.get(ext)
    if doc_type is None:
        log.fail("未知文档类型", path=str(file_path))
    options = 2 if read_only else 0
    try:
        ret = sw.OpenDoc6(str(file_path), doc_type, options, "", 0, 0)
        model, outs = _unpack(ret)
    except TypeError:
        errors, warnings = byref_i4(), byref_i4()
        model = sw.OpenDoc6(str(file_path), doc_type, options, "", errors, warnings)
        outs = [int(errors.value), int(warnings.value)]
    if model is None:
        log.fail("OpenDoc6 失败", path=str(file_path), outs=outs)
    log.event("DOC_OPEN", path=str(file_path), read_only=read_only)
    return cast(model, "IModelDoc2")


def save_as(model, log: BuildLog, file_path: Path, overwrite=False):
    file_path = Path(file_path)
    if file_path.exists() and not overwrite:
        log.fail("目标已存在且未授权覆盖（可重入规则）", path=str(file_path))
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        ret = model.Extension.SaveAs(str(file_path), 0, 1, None, 0, 0)
        ok, outs = _unpack(ret)
    except TypeError:
        errors, warnings = byref_i4(), byref_i4()
        ok = model.Extension.SaveAs(str(file_path), 0, 1, empty_dispatch(),
                                    errors, warnings)
        outs = [int(errors.value), int(warnings.value)]
    if not ok:
        log.fail("SaveAs 失败", path=str(file_path), outs=outs)
    log.event("DOC_SAVE", path=str(file_path))
    return True


def save(model, log: BuildLog):
    try:
        ret = model.Save3(1, 0, 0)
        ok, outs = _unpack(ret)
    except TypeError:
        errors, warnings = byref_i4(), byref_i4()
        ok = model.Save3(1, errors, warnings)
        outs = [int(errors.value), int(warnings.value)]
    if not ok:
        log.fail("Save3 失败", outs=outs)
    return True


def rebuild_or_fail(model, log: BuildLog, what=""):
    ok = model.ForceRebuild3(False)
    if not ok:
        log.fail(f"ForceRebuild3 失败 {what}")
    log.event("REBUILD_OK", what=what)


def close_document(sw, model, log: BuildLog):
    title = get_com_member(model, "GetTitle")
    sw.CloseDoc(title)
    log.event("DOC_CLOSE", title=title)


def activate_configuration(model, log: BuildLog, name: str):
    """切换配置并以 ActiveConfiguration.Name 实核（ShowConfiguration2 返回值不可信）。"""
    model.ShowConfiguration2(name)
    ac = get_com_member(get_com_member(model, "ConfigurationManager"),
                        "ActiveConfiguration")
    actual = get_com_member(ac, "Name")
    if actual != name:
        log.fail("配置激活失败", wanted=name, active=actual)
    log.event("CONFIG_ACTIVE", name=name)


def rename_last_feature(model, log: BuildLog, new_name: str):
    """把特征树最后一个特征改名（创建后立刻调用，保证确定性命名）。"""
    feats = cast(model, "IModelDoc2").FeatureManager.GetFeatures(True)
    if isinstance(feats, tuple) and feats:
        last = cast(feats[-1], "IFeature")
        last.Name = new_name
        log.event("FEATURE_RENAME", name=new_name)
        return last
    log.fail("GetFeatures 为空，无法命名", wanted=new_name)


def set_custom_properties(model, log: BuildLog, props: dict, config=""):
    """写入 15 项治理属性。全部按文本写入；已存在则覆盖（swCustomPropertyDeleteAndAdd=2）。"""
    mgr = model.Extension.CustomPropertyManager(config)
    for k, v in props.items():
        mgr.Add3(str(k), 30, str(v), 2)  # 30 = swCustomInfoText
    log.event("PROPS_SET", count=len(props), config=config or "(doc)")


def read_custom_properties(model, config=""):
    mgr = model.Extension.CustomPropertyManager(config)
    names = mgr.GetNames
    if callable(names):
        names = names()
    out = {}
    for n in names or []:
        val_out, resolved_out = "", ""
        try:
            ok, val_out, resolved_out = mgr.Get5(n, False, val_out, resolved_out)
            out[n] = resolved_out or val_out
        except Exception:
            try:
                out[n] = mgr.Get(n)
            except Exception:
                out[n] = None
    return out


def _equation_mgr(model, log: BuildLog):
    for attr in ("GetEquationMgr", "EquationMgr"):
        try:
            return get_com_member(model, attr)
        except Exception:
            continue
    log.fail("无法获取 EquationMgr（GetEquationMgr/EquationMgr 均不可用）")


def eq_text(eq, i):
    member = getattr(eq, "Equation", None)
    if member is not None:
        try:
            return member(i)
        except Exception:
            pass
    return getattr(eq, "GetEquation")(i)


def add_global_equations(model, log: BuildLog, params: dict):
    """把参数合同写入方程管理器为全局变量：\"NAME\" = value。

    已知偏差 D-EQ-01：本机 SolidWorks 为精简安装（VBA7.1 vbe7.dll 缺失），
    IEquationMgr.Add/Add2/Add3 恒返回 -1。方程不可用时不 fail-closed——参数唯一
    驱动源由哈希锁定的 b3_build_spec.yaml 承担，并以 PARAM_* 自定义属性冗余写入
    文档本体（机器可读）；偏差记入构建日志与后续 claim_limit_audit。
    """
    eq = _equation_mgr(model, log)
    count = get_com_member(eq, "GetCount")
    existing = {}
    for i in range(count):
        existing[eq_text(eq, i).split("=")[0].strip().strip('"')] = i
    failed = []
    for name, value in params.items():
        if name in existing:
            continue
        if eq.Add2(-1, f'"{name}" = {value}', True) < 0:
            failed.append(name)
    if failed:
        log.event("DEVIATION_D-EQ-01", detail="IEquationMgr.Add2 返回 -1（VBA 运行时缺失）",
                  fallback="PARAM_* 自定义属性 + b3_build_spec.yaml 为参数权威",
                  failed_count=len(failed))
        mgr = model.Extension.CustomPropertyManager("")
        for name, value in params.items():
            mgr.Add3(f"PARAM_{name}", 30, str(value), 2)
        log.event("PARAM_PROPS_SET", count=len(params))
    else:
        log.event("EQUATIONS_SET", count=len(params))


def select_by_id(model, name, sel_type, x=0.0, y=0.0, z=0.0, append=False, mark=0):
    ok = model.Extension.SelectByID2(name, sel_type, x, y, z, append, mark,
                                     None, 0)
    return bool(ok)


IDENT16 = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
           0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]


def insert_components_identity(sw, log: BuildLog, asm_model, part_paths):
    """打开零件→插入装配→显式恒等位姿→固定。全局坐标零件的标准装配路径。

    已知坑（b3_03 证据）：AddComponent5 把包围盒中心放到插入点，必须
    随后显式设 Transform2=I。
    """
    asm = cast(asm_model, "IAssemblyDoc")
    asm_title = get_com_member(asm_model, "GetTitle")
    mu = cast(get_com_member(sw, "GetMathUtility"), "IMathUtility")
    xf = mu.CreateTransform(IDENT16)
    comps = []
    for prt in part_paths:
        open_document(sw, log, prt, read_only=True)
        try:
            ret = sw.ActivateDoc3(asm_title, False, 0, 0)
        except TypeError:
            ret = sw.ActivateDoc3(asm_title, False, 0, byref_i4())
        c = asm.AddComponent5(str(prt), 0, "", False, "", 0.0, 0.0, 0.0)
        if c is None:
            log.fail("AddComponent5 失败", part=Path(prt).name)
        c2 = cast(c, "IComponent2")
        try:
            c2.Transform2 = xf
        except Exception:
            c2.SetTransformAndSolve2(xf)
        comps.append(c2)
        log.event("COMPONENT_ADDED_IDENTITY", part=Path(prt).name)
        # 低内存机器：插入后立即关闭零件独立窗口（装配自持引用），压住打开文档数
        sw.CloseDoc(Path(prt).name)
    asm_model.ClearSelection2(True)
    for c2 in comps:
        c2.Select4(True, None, False)
    asm.FixComponent()
    asm_model.ClearSelection2(True)
    rebuild_or_fail(asm_model, log, "assembly_identity_insert")
    return comps


def create_offset_plane(model, log: BuildLog, base_plane_names, offset_mm: float,
                        new_name: str, flip=False):
    """从基准面偏移创建参考面。base_plane_names: 中英文候选名列表。"""
    model.ClearSelection2(True)
    picked = None
    for nm in base_plane_names:
        if select_by_id(model, nm, "PLANE"):
            picked = nm
            break
    if not picked:
        log.fail("找不到基准面", candidates=list(base_plane_names))
    # 8 = swRefPlaneReferenceConstraint_Distance; 256 = _OptionFlip（swconst 查证值）
    flag = 8 | (256 if flip else 0)
    feat = model.FeatureManager.InsertRefPlane(flag, _mm(abs(offset_mm)), 0, 0, 0, 0)
    if feat is None:
        log.fail("InsertRefPlane 失败", base=picked, offset_mm=offset_mm)
    feat.Name = new_name
    model.ClearSelection2(True)
    log.event("PLANE_CREATED", name=new_name, base=picked, offset_mm=offset_mm,
              flipped=flip)
    return feat
