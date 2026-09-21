# current_r2_digital_host_capture_data_v1

`CURRENT_R2_DIGITAL_HOST_CAPTURE_DATA_INCREMENT_V1` — 当前系统数字主机实例化（TRACK_A 合同层）
与 prebind 仿真/数据自举（TRACK_B），六层架构 H0–H5。

**最高合法主张（冻结）：** `CURRENT_SYSTEM_DIGITAL_HOST_CANDIDATE` + `PREBIND_SIMULATION_DATASET_V1` + `NO_FORMAL_RELEASE_CREDIT`。
禁用：COMPLETE_DIGITAL_TWIN / FULL_CAPTURE_VALIDATED / REAL_CONTACT_VERIFIED / CONTROL_RELEASED /
SIM13_NON_ABORT_AUTHORIZED / MECHANICAL_RELEASE_COMPLETE。

## 机器入口

- 增量 Gate：[`11_verification/DH_INCREMENT_GATE_V1.json`](11_verification/DH_INCREMENT_GATE_V1.json)（DH-G0..G8）
- DH-G0：[`11_verification/DH_G0_GATE.json`](11_verification/DH_G0_GATE.json)
- 权威快照：[`00_authority/CURRENT_V2_STATUS_SNAPSHOT.json`](00_authority/CURRENT_V2_STATUS_SNAPSHOT.json)（51 源哈希 + 19 项复核）
- 冲突台账：[`00_authority/CONFLICT_LEDGER.csv`](00_authority/CONFLICT_LEDGER.csv)

## 复现

```bash
python scripts/gen_authority.py        # 权威快照（fail-closed pin 校验）
python -m pytest tests/ -q --basetemp=.pytest-tmp -p no:cacheprovider
python scripts/run_increment.py        # S00/S01/S02/S03/S07 + episodes + gates
```

## 边界（读我再引用）

- CAD 执行分支 FROZEN：命名授权 MISSING + 内存 < 6 GiB；本增量不索取低内存 override。
- S02/S03 是 **prebind 刚体无接触诊断**（无重力、无柔性、无接触），不是任务放行，不重发任何父 Gate。
- S03 是控制阶梯 C1 候选诊断，**不得**称为时域控制 PASS。
- T_E_T 权威值 MISSING → C08/C09 保持 NOT_EVALUATED；D0 之外的数据级（D1/D2/D3）全部 PLANNED/BLOCKED。
- 帆板质量 0.348 kg 为占位（D-7，可差 5–10 倍）——组合 plant 未注入柔性体，正是因为该占位不可用于结论。
