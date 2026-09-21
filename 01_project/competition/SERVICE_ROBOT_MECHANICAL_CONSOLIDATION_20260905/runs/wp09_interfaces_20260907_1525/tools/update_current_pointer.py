"""Prepend the verified delivery to the existing navigation, preserving history."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1];B=R.parents[1]
seal=json.loads((R/'results/FINAL_INTEGRITY.json').read_text());assert seal['status']=='PASS_DELIVERY_FILES_BINDINGS_AND_FROZEN_INPUTS'
status=json.loads((R/'results/DELIVERY_STATUS.json').read_text());assert len(status['native_states'])==3
p=B/'CURRENT_candidate.md';old=p.read_bytes().decode('utf-8');prefix='# 当前机械工程入口：WP09 共享舱、推进与DM接口整合'
assert not old.startswith(prefix),'Pointer already updated; history not duplicated'
new=prefix+'\n\n2026-09-07：从 [本轮交付说明](runs/wp09_interfaces_20260907_1525/README.md) 查看3套SolidWorks固定姿态总装，每套701组件/1082几何实体；619组件继承，82实例新增/替换，共享21个新原生零件。服务态全部实体实读，停放/释放态新82实体实读、旧1000实体依冻结WP08证据哈希绑定；全部姿态组件身份/文件哈希/变换已核验。\n\nB601已确认DM，工程样机采用外置RSP-500-24；BPX 8S/P60用于低功率支路。共享舱布局、非承压推进托架与两条静态线束路线已纳入总装。整机机械、电气、制造和飞行放行仍开放；真实端接、设备固定、DM出货机械修订与拆盖/工具验证见[关闭项与开放项](runs/wp09_interfaces_20260907_1525/docs/CLOSURE_DELTA_AND_OPEN_ITEMS_ZH.md)。完整电气回路仍为0。\n\n机器状态见[DELIVERY_STATUS](runs/wp09_interfaces_20260907_1525/results/DELIVERY_STATUS.json)，文件完整性见[FINAL_INTEGRITY](runs/wp09_interfaces_20260907_1525/results/FINAL_INTEGRITY.json)。以下为历史入口，表述属于当时记录。\n\n---\n\n'+old
p.write_bytes(new.encode('utf-8'))
print(json.dumps(dict(path=str(p),old_sha256=hashlib.sha256(old.encode('utf-8')).hexdigest(),new_sha256=hashlib.sha256(new.encode('utf-8')).hexdigest(),history_retained=True),ensure_ascii=False))
