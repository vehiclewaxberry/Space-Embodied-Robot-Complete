# BOM 来源绑定：未应用的最小修订建议

这是 `REVIEW_AND_PLAN` 的文本建议，**没有修改 WP03 文件，没有执行 BOM、CAD 或动力学生成器，也没有运行下面的拟议补丁**。此前独立复现修正暂停时两次补丁均未写入成功，不能记为已修复。

被审源：`20_engineering/service_robot_wp03_spacecraft_body_r1/export_parts_and_bom.py`，SHA-256 `1321dc954dd363af578ae1c9811c5152df1362772404cc9fe2523f1a1a142f27`。现行脚本第 2 行顶层导入 `spacecraft_model`，所以 `--bom-only` 仍加载 CAD；第 12–19 行按现存交接映射后仅核对合计，同总质量的旧来源没有被拒绝。

实际 V1 数据提供了检查所需的字段：

- `DYNAMICS_HANDOFF.json.schema = WP03_DYNAMICS_HANDOFF_V1`；`input_sha256` 有 11 个已记录输入；`source_files_unchanged`；`receipt_model_source_checks`。
- 服务态收据 `source_sha256` 和四项 `dependency_sha256`；`state`、`view`、`q_deg`、`finger_mm`、`T_S_arm_base`、`instances`。
- 交接服务态 `T_S_arm_base_mm`、`mass_owner_values`、`mass_owner_values_by_role`；`groups.ONBOARD_CANDIDATE` 中 `mass_atoms`、`unknown_mass_instances`、`instance_count`、`known_mass_kg`。

最小依赖绑定片段如下。应在获准的派生副本中再形成可应用 diff，加入测试后交独立审阅；此处不表示实现完成。

```python
from pathlib import Path
import hashlib

HERE = Path(__file__).resolve().parent  # replace top-level CAD import

def require_sha(path, expected):
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'Stale or missing input: {path}')

def require_handoff_binding(receipt, handoff, receipt_path):
    if handoff.get('schema') != 'WP03_DYNAMICS_HANDOFF_V1':
        raise ValueError('Unsupported handoff schema')
    if handoff.get('source_files_unchanged') is not True:
        raise ValueError('Handoff inputs were not recorded unchanged')
    if receipt.get('state') != 'service' or receipt.get('view') != 'complete':
        raise ValueError('BOM requires the complete service receipt')
    require_sha(HERE / 'spacecraft_model.py', receipt['source_sha256'])
    for name in ('design_parameters.json', 'root_structure.py',
                 'wing_kinematics.py', 'kinematics.py'):
        require_sha(HERE / name, receipt['dependency_sha256'][name])
    inputs = {Path(p).resolve(): h for p, h in handoff['input_sha256'].items()}
    required = {
        *(HERE / 'results' / f'{s}_instances.json'
          for s in ('parking', 'released', 'service')),
        *(HERE / n for n in ('dynamics_handoff.py', 'spacecraft_model.py',
                            'design_parameters.json', 'kinematics.py', 'wing_kinematics.py')),
        HERE.parent / 'service_robot_wp01_20260905/kinematics.py',
        HERE.parent / 'cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf',
    }
    if not {p.resolve() for p in required} <= inputs.keys():
        raise ValueError('Missing required provenance hashes')
    for path, expected in inputs.items():
        require_sha(path, expected)
    checks = [c for c in handoff['receipt_model_source_checks']
              if Path(c['receipt']).resolve() == receipt_path.resolve()]
    if (len(checks) != 1 or checks[0]['matches_current_model_source'] is not True
            or checks[0]['recorded_model_sha256'] != receipt['source_sha256']):
        raise ValueError('Handoff/receipt model mismatch')
```

拟议调用顺序：无 `--bom-only` 时才局部 `from spacecraft_model import build`。已有完整收据且交接存在时，在打开任意 CSV 前执行来源检查，再验证恰好一个 service 状态、q/指位/根变换一致；按 instance ID、mass_owner、product_role、source_revision 核对 `mass_atoms` 与 `unknown_mass_instances` 的互斥完整覆盖和唯一性，然后逐项核对质量映射，最后核对合计。不能只用“合计相同”或文件存在代替绑定。

首次没有交接时仍可输出几何 BOM：原始 `mass_kg` 保留，所有 `allocated_dynamics_mass_kg` 为 null（CSV 空白），增加 `allocated_mass_status=NOT_ALLOCATED_NO_HANDOFF`。有交接但未知的项保持 null，并标 `UNKNOWN_IN_HANDOFF`；已分配项标 `HANDOFF_ALLOCATED`。只对明确非 null 的数值求和，不用 `or 0` 遮盖未知。现行服务态的 361 个实例、194 项已分配和 167 项未知属于被审账本的内容，不能把数量硬编码为未来判据。

README 的日常复现顺序应当让三态完整收据先生成，随后 `dynamics_handoff.py`，最后再 `export_parts_and_bom.py --bom-only`。需要局部零件导出时，可在现行交接就绪后运行无参数导出器；最终 BOM 刷新仍在交接之后。旧交接被拒绝时报告具体文件，保持原有 BOM 不变。

README 同时应准确说明：JSON 的 `wing_source` 是来源说明；当前翼坐标来自 `wing_kinematics.py` 中 `ROOT_Y=121.15`、`ROOT_Z=-108.15`、300×200×2.5 mm 叶片与 3 mm 偏置，CAD 叶片尺寸和 0.18 kg 预算另在 `spacecraft_model.py` 显式给出。局部 JSON 的旧太阳翼字段、旧支承字段、局部梁板尺寸/密度/臂根说明及 `retention.hinge_y_mm`、`saddle_carrier_recess_mm` 并未直接驱动相应 CAD；根框还读取 WP02 的 P/R。保持器 CAD 角度使用 `states.*`，路径角度使用 `retention.*`，需要一致性校验。

待授权修订的验收负控：同合计旧 service 收据、旧模型哈希、旧参数/运动学/URDF 哈希、缺少必需输入哈希、重复/错误 mass_owner、已知项被遗漏、非 complete 视图，都应在写 CSV 前被拒绝；首次缺交接可输出明确未分配 BOM。测试使用临时夹具或派生副本，随后才对当前文件执行 `--bom-only` 并确认 CAD 模块未加载。上述 BOM 测试本轮未执行。
