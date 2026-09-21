# 真实 STEP 材料惯性补充交付

本包为现有 873 实例参数包中的 **306 个候选材料实例**补入实际几何计算得到的质量、质心与质心惯量。237 个唯一 STEP 源均读取成功，采用候选均匀材料密度。机器状态为 `PASS_PARTIAL_MATERIAL_INERTIA_SUPPLEMENT__NO_COMPLETE_SPACECRAFT_MODEL`。这是一组可接入后续模型的材料参数，整星完整质量与惯量仍为 null，`whole_spacecraft_inertia_complete=false`。

该 306 实例集合的 service 态材料质量小计为 **7.87230336740122 kg**。这一小计包含现有候选集合中的结构与接口零件；其飞行/GSE 配置处置尚未完成。不能把它作为整星质量，也不能再粗加 84 个 CIC 平均质量或 B601 整臂 4.5 kg 后宣称已得到整星惯量。872 个物理/表征实体中，其余 566 个尚无完整 m/COM/I 模型；873 中另有 1 个非物理保留对象。

## 读取入口

| 文件 | 内容 |
|---|---|
| `MATERIAL_INERTIA_DELIVERY.json` | 本包状态、覆盖、部分质量、校验与资源护栏摘要、输出 SHA256 |
| `MATERIAL_INERTIA_INSTANCES.json` | 306 实例；局部 m/COM/I；各态独立源与局部参数；S 系 COM/I；不确定度身份 |
| `MATERIAL_MODEL_STATES.json` | service、parking、released 三态的 306 实例集合静态部分 COM/I |
| `MATERIAL_INERTIA_LINEAGE.json` | 237 源 STEP → 几何积分回执 → 对应 worker 版本，逐项 SHA256 |
| `MASS_METHOD_COMPARISON.csv` | 每实例旧质量、同方法默认读回、采用主值与比较积分的质量差 |
| `results/QUADRATURE_ENGINEERING_SCREENS.json` | 逐源惯量求积差与数值筛选阈值 |
| `results/INERTIA_ALGEBRA_CHECKS.json` | 8376 项单位、源绑定、矩阵、变换与聚合检查 |
| `results/RESOURCE_AUDIT.json` | 护栏、峰值、超时、已回收自有 worker 与正式回执 SHA256 |
| `results/guard_receipts/` | 护栏正式收据，交付无需依赖 logs 目录 |
| `SHA256.csv` | 封存清单，排除自身与 logs |

原 `mechanical_intake/PARAMETER_PACKET.json`、父系统目录 C、既有 URDF 与科学 Gate 均未修改。原材料密度由已封存参数包继承：铝候选 2700 kg/m³、钢候选约 7850 kg/m³。本包没有新增材料厂家认证或实物测量。

## 几何积分方法与适用范围

直接使用 cadquery-ocp 7.9.3.1.1 的 `STEPControl_Reader` 读取实际 STEP BRep，逐源验证源 SHA、毫米单位、有效体和闭壳数量，全部无需网格近似。运行环境为 Python 3.13.9、NumPy 2.3.5。build123d 的系统字体扫描出现字体格式异常后改用其底层 OCP API，未修改字体、CAD 或用户软件。

15 个源的主值采用 `BRepGProp.VolumePropertiesGK`，局部 1e-7/1e-9 两组求积，显式启用 CGFlag 与 IFlag；222 个源采用 `BRepGProp.VolumeProperties` 默认非三角化面求积主值，并以普通自适应面求积进行逐源比较。每个实例和每个状态均标记真实主值方法，m、COM 与 I 始终由同一组积分形成。初版全 GK 对复杂源耗时过长的两次 180 秒超时保留在资源审计中；已完成的源没有重算覆盖。

默认值与比较值的惯量使用 Frobenius 范数筛选：

`||I_A − I_B||_F ≤ 1e-5 × max(||I_A||_F, ||I_B||_F) + 1e-4 mm^5`

237/237 源通过；最大相对范数差为 **4.120234544291987e-6**。绝对项用于接近零的几何惯量，换算为质量惯量时乘 `rho × 1e-15`。这是工程数值一致性筛选阈值，不是任意形状的严格误差界，也不是实物制造误差或概率分布。

独立解析偏置箱体与圆柱验证了局部坐标、中心惯量、曲面求积和 SI 换算。全 GK 夹具 4 项、实用默认/普通自适应夹具 6 项均通过。保留的 `NON_GK_INERTIA_NEGATIVE_CONTROL.json` 记录：仅约束体积的求积 eps 即使返回极小体积误差估计，圆柱惯量仍可有约 3.77e-8 的相对差。该结果说明体积 eps 不能解释为惯量误差界；其数值差仍在本包工程筛选范围内。

既有 8 个旧 wing edge frame 源的默认积分与普通自适应结果仍有差异：体积相对差约 1.94e-6～3.03e-6，惯量范数差约 3.29e-6～4.12e-6，COM 分量差最高约 3.17e-4 mm。差异均逐源保留。通过采用**相同默认积分口径**对拍旧质量，306/306 实例兼容，最大质量差约 6.92e-13 kg；没有把不同积分法之间的差异伪判为零。

## 坐标与单位

STEP 源坐标为 mm；输出遵守列向量 `p_S = R p_local + t`，其中输出 T 的 t 已为 m。原生矩阵 `MatrixOfInertia` 是关于几何质心、轴平行于源局部坐标系的矩阵。该语义经过偏置箱体独立验证，与 [OCCT GProp_GProps 参考文档](https://occt3d.com/dev/doc/refman/html/class_g_prop___g_props.html) 一致；运行时 API 文档已保存在 probe 回执中。

- `m_kg = volume_mm3 × 1e-9 × rho_kg_m3`
- `COM_m = COM_mm × 1e-3`
- `I_COM_kg_m2 = I_COM_mm5 × rho_kg_m3 × 1e-15`
- `I_COM_S = R I_COM_local Rᵀ`
- `I_S_origin = I_COM_S + m [(cᵀc)E − ccᵀ]`

几何密度取 1 时惯量量纲为 **mm⁵**；不能直接按 kg·mm² 乘 1e-6。必须先连同密度换算。已加入错误缩放、负惯量特征值、三角不等式破坏、不对称矩阵、左手系与非正交变换负例。

6 个 hold 夹持件在 parking 状态使用不同 STEP 源。本包分别使用该状态实际 SHA 对应的局部 COM/I，再应用该状态 T；不能把 service 源局部 COM 直接代入所有状态。共完成 711 次真实 BRep 刚性置姿求积，其中 693 次源 SHA 与其配置状态一致，另外 18 次为同源在代表性 T 下的数学坐标变换诊断。306 实例 × 3 状态的 918 组输出均按实际状态源绑定。

三态的部分质量分别约为 7.87230336740122、7.872303367401311、7.87230336740122 kg；微小差异保留为数值积分差。部分集合 COM 与惯量由状态实际 m/COM/I 聚合，独立使用两条平行轴路径核对。它们仅适用于该 306 实例集合，不构成整星刚化假设。

## 后续消费条件

应同时读取原参数包与本补充包并验证 SHA；使用每个状态的 `state_specific_local_parameters` 和源绑定。若需要切换默认/GK 方法，应成组切换 m/COM/I，不能混搭。用于预测当前真实样机动力学性能前，仍须完成状态配置处置、实体到真实运动 link 的归属、B601 关节轴与运动树、剩余模块质量分布，以及实物质量/质心/惯量识别。声明假设的材料模型与理论研究可以使用本包开展，但须明确缺项和适用域；实物识别不是所有纯数值研究的额外 Gate。

本包未将全部 873 件固定装配冒充 B601 运动树；`dynamic_link_id=null`、`motion_tree_complete=false`。未从外形包络、CIC 平均质量或整臂整机标称质量构造均匀密度惯量；未启动动力学、控制或强化学习仿真。候选均匀材料模型与实物证据分开，不获得既有科学 Gate 或硬件放行信用。

厂家/测量未提供的密度不确定度、标准不确定度、分布、自由度以及严格惯量误差界均为 null，不能把这些 null 解释为零。制造公差也没有被自动转成独立均匀分布。

## 资源与复现

所有几何 worker 串行运行，Windows Job 对自有子进程执行 1400 MiB 提交量上限，采样 RSS 上限 1400 MiB；启动可用内存至少 2048 MiB、运行至少 512 MiB，0.25 秒采样。实际最高采样 RSS **295.265625 MiB**，最低系统可用内存 **2892.1484375 MiB**。无内存保护触发；两次全 GK 批次时间保护触发后，自有 worker 已确认退出，随后按实用方法继续。没有终止未知用户进程，没有启动 SolidWorks。

数值收集器不导入 CAD/OCC，可从本包已有积分回执重新计算 SI 和部分聚合。原始读取脚本拒绝覆盖既有 `Gxxx.json`；任何将来的几何重算应使用新目录并保留本封存包。正式护栏回执已复制到 `results/guard_receipts/`，源几何、源参数包、方法脚本、几何回执和正式输出均有 SHA256 绑定。
