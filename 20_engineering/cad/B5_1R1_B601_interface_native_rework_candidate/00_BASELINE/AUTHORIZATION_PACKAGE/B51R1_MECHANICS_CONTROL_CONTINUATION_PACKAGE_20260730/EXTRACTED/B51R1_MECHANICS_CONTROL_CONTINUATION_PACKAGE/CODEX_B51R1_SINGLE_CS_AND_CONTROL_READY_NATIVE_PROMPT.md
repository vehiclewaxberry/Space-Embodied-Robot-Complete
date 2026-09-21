# Codex 续跑：单坐标系诊断、原生骨架、Carrier链与控制交接

## 0. 本次人工授权

`允许再次可见启动 SolidWorks 2024 一次，用于执行 B5.1R1 单坐标系 InsertCoordinateSystem 诊断；仅在一次性副本上测试，不修改已验证 Stage A。`

本次只授权一次性副本上的单坐标系诊断。诊断通过后，若现有 Phase 1 授权仍有效，才可依次创建：

1. 原生 Master Skeleton；
2. 10个原生Carrier；
3. Carrier-only 9关节链；
4. 控制交接寄存器草案。

不得修改：

- Stage A；
- V2.2；
- B5.0；
- B5.1；
- accepted URDF；
- vendor STEP。

## 1. 单坐标系诊断

### 1.1 一次性副本

新建：

`00_BASELINE/DIAGNOSTIC_ONLY/B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT`

不得复制或打开冻结原件进行写操作。

### 1.2 最小动作

在空白一次性零件中：

1. 建立三个正交参考平面；
2. 建立一个原点；
3. 仅调用一次 `InsertCoordinateSystem`；
4. 命名为 `CS_DIAGNOSTIC_ONLY`；
5. 保存；
6. 关闭文档；
7. 关闭SolidWorks；
8. 复算文件SHA-256；
9. 再次可见启动并冷重开；
10. 读取坐标系名称、变换和特征类型；
11. 再次保存并确认第二次哈希变化仅来自受控重保存。

禁止：

- 循环创建坐标系；
- 在同一文档同时测试其他API；
- 运行Mate；
- 导入STEP；
- 打开Stage A写入；
- 自动恢复冻结文件。

### 1.3 通过条件

- SolidWorks不崩溃；
- 文件可保存、关闭、冷重开；
- 坐标系特征存在；
- 名称持久化；
- 原点和旋转矩阵与输入一致；
- API可重新枚举该特征；
- 无外部引用；
- 进程正常退出；
- 诊断副本哈希、字节数和日志完整。

输出：

- `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_GATE.json`
- `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM.json`
- `08_REVIEWS/B51R1_SINGLE_CS_DIAGNOSTIC_LOG.md`
- 保存前、保存后、冷重开截图。

若失败：

`SINGLE_COORDINATE_SYSTEM_DIAGNOSTIC_HOLD`

停止后续原生CAD创建。

## 2. 原生Master Skeleton

诊断通过后创建：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT`

要求：

- 每次只增加一个坐标系或参考特征；
- 每增加一项即保存检查点；
- 命名实体来自中性见证真值；
- 每个坐标系冷重开验证；
- 配置：
  - COMMON_CANONICAL
  - MODE_A_EVALUATION
  - MODE_B_EVALUATION
- 不创建质量实体；
- 不默认裁决H9。

原生Skeleton导出STEP后与R2中性见证比较。

## 3. 10个Carrier

文件名必须从accepted link名称派生。

每个Carrier只包含：

- link frame；
- parent joint frame；
- child joint frame；
- joint axis；
- zero plane；
- visual mount frame。

不得加入质量实体，不得在Carrier中写入新的惯量真值。

每个零件单独完成：

- 创建；
- 保存；
- 关闭；
- 冷重开；
- 命名实体枚举；
- 坐标变换回读；
- 哈希登记。

## 4. Carrier-only 关节链

建立：

`B51R1_CARRIER_CHAIN_NATIVE.SLDASM`

按accepted拓扑逐关节添加，禁止一次性创建。

每个R关节测试：

- q0；
- +1°；
- -1°；
- lower；
- upper；
- q0复位；
- 冷重开。

每个P关节测试：

- q0；
- 小正位移；
- 小负位移；
- lower；
- upper；
- q0复位；
- 冷重开。

两P保持独立，除非accepted URDF明确给出mimic关系。

## 5. 为控制研究同步生成寄存器

在创建原生CAD的同时维护：

- `B51R1_JOINT_ZERO_SIGN_LIMIT_REGISTER.yaml`
- `B51R1_JOINT_ACTUATION_PARAMETER_REGISTER.csv`
- `B51R1_SENSOR_FRAME_REGISTER.yaml`
- `B51R1_BASE_INTERFACE_COMPLIANCE.yaml`
- `B51R1_STOW_RELEASE_STATE_MACHINE.yaml`
- `B51R1_COLLISION_MODEL_MAPPING.yaml`
- `B51R1_MECH_CONTROL_HANDOFF_CONTRACT.yaml`

规则：

- URDF已有值直接引用路径和哈希；
- CAD测得值记录来源和测量方法；
- 未知执行器、刚度、摩擦、回差和传感器参数标为`PROVISIONAL_TBD`；
- 不得以典型工业机械臂参数补空。

## 6. 中间Gate

成功上限：

`B51R1_NATIVE_SKELETON_AND_CARRIER_CHAIN_PASS_CONTROL_HANDOFF_DRAFT_CREATED`

它只说明：

- 原生骨架和Carrier链可用；
- 控制接口草案存在；
- 不说明精细几何、H10、完整T005、G07/G08或结构分析通过。

继续保持：

- H9 HOLD；
- H10 0/28；
- G2 FAIL；
- G3 HOLD，直到完整T005通过；
- G4 HOLD；
- G5/G6 NOT_RUN。
