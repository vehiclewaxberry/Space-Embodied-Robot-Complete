"""Update the one existing entry point only after verified native delivery."""
from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
C=Path(__file__).resolve().parents[1]
base=C.parents[2]
target=base/'CURRENT_candidate.md'
status=json.loads((C/'results/DELIVERY_STATUS.json').read_text(encoding='utf-8'))
assert status['mechanical']['fixed_pose_native_delivery_passed'] is True
assert status['whole_mechatronic_detailed_design_complete'] is False
assert (C/'README.md').is_file() and (C/'REVIEW.html').is_file()
old=target.read_bytes()
backup=C/'results/CURRENT_ENTRY_BEFORE.md'
if backup.exists():
    raise RuntimeError('Entry update already attempted; inspect current hashes before any retry.')
backup.write_bytes(old)
rel=C.relative_to(base).as_posix()
prefix=f'''# 当前工程入口：WP09R 原生装配、电气与推进设计增量

2026-09-08：从 [本轮交付说明]({rel}/README.md) 与 [可视化查看页]({rel}/REVIEW.html) 进入。三态原生 SolidWorks 各 873 叶零件、10 固定容器，19 个唯一子装配；新增太阳面层、修订叠层机构与 R01 标准件。实际保存、冷重开及搬迁见 [原生交付回执]({rel}/results/NATIVE_DELTA_DELIVERY.json)。原 705 组件便携包保留。

实际停止电路已并入系统两页原理图：94 元件/96 网/72 条外部主表连接、191 项连接核验；[主接线表]({rel}/ecad/MASTER_FROM_TO.csv) 与 [分层 BOM]({rel}/ecad/MASTER_BOM.csv) 为当前子版，父版同名文件保留历史身份。真实官方 MotorBridge DLL 完成18项边界ABI检查，DM公开电机型号与ID已绑定，原生串口/MIT编码未执行。推进源侧针位与安装螺纹已修正，模块受控ICD仍未绑定。

完整机电系统详细设计仍未完成：辅助供源与停止PCB、星上高功率支路、回生、推进受控接口、完整线束及热/强度/整机动作仍有开放设计责任。现行 [机器状态]({rel}/results/DELIVERY_STATUS.json) 保留未满足条件与原24项未执行物理检查。原85文件电气/DM参考包、47网一致/29项Python历史验证均保留原身份，不与本轮18项原生ABI检查混记。

下方历次入口原样保留，其中“当前/本轮”均属于记录时刻。

---

'''.encode('utf-8')
new=prefix+old
target.write_bytes(new)
assert target.read_bytes()[len(prefix):]==old
record={'utc':datetime.now(timezone.utc).isoformat(),'status':'UPDATED_EXISTING_SINGLE_ENTRY_WITH_BYTE_PRESERVED_HISTORY','target':str(target),'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(new).hexdigest(),'prefix_bytes':len(prefix),'prior_bytes_preserved_exactly':True,'new_parallel_CURRENT_created':False}
(C/'results/CURRENT_UPDATE.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
