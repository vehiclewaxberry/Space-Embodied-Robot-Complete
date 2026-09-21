# Route-C 授权前 CAD Brief V1

状态：`PRELIMINARY_PROPOSAL_ONLY / CAD_ENTRY_HOLD`。这是详细设计获批后的建模合同，不是 CAD 授权，不产生或修改任何 STEP、STL、GLB、FCStd 或 URDF。

## CAD brief

- Model：B601 六关节机械臂 Route-C 全程受导向 dress-pack，包含储线盒、移动导向/rolling loop、腕部定曲率 wrap 与安装件；属于新建、独立版本的装配体，不修改既有机械臂或太阳翼几何。
- Task type：授权后的 STEP-first 参数化装配设计；本文件当前仅为授权前 brief。
- Units：长度统一 mm，质量 kg，惯量 kg·m²，角度 rad（展示可附 deg），力 N，力矩 N·m；任何输入不得隐式剥离单位。
- Coordinate convention：根坐标、六个关节轴和链节坐标以已接受 URDF 为唯一运动学权威；新增导向件使用具名局部安装基准并显式记录到 URDF link frame 的变换，但不得回写已接受 URDF。
- Frozen geometry：已接受 URDF SHA-256 `1BC2B748...71C164` 与 Solar R2 STEP SHA-256 `21FF77B8...15795` 均只读。
- Proposed architecture：J1 封闭定曲率储线盒；J2/J3 父子链节半约束移动导向或 rolling loop；J4 局部旁路与导向 rolling loop 待权衡；J5/J6 定曲率腕部 wrap。该组合只是 ODR-42 的首选提案，不是已选飞行构型。
- Split power/data：仅保留为权衡项，必须等待电流/数据率、屏蔽与 EMC、连接器、可用体积和弯折寿命输入，不得在 CAD 中预先假定。
- Named parameters：每一项必须携带值、单位、公差/标准不确定度或有界分布、来源和版本；至少包括 bundle OD、各产品静态/动态最小弯曲半径、线密度、导向槽/衬垫间隙、固定点、活动行程、储线容量、恢复力矩曲线和安装公差。
- Route-B seed quarantine：10 mm bundle OD、30 mm terminal bend、4001.158 mm cut length 均为被拒 Route-B 的 provisional seed，获批后必须按选定产品和 Route-C 路径重建；0.68406762184 kg 诊断质量禁止继承。
- Functional features：封闭防脱出通道、可检查/可装配盖板、受控出口切线、无锐边衬垫、具名限位与服务环、可验证夹持界面、J2/J3 运动载体、J1 容量/行程指示基准以及 J5/J6 定曲率路径。
- Positioning/mating：所有安装面、关节轴、导向入口/出口切线、移动载体端位和 keep-out 界面使用具名 datum；装配源中显式定义约束和变换，禁止依赖视觉摆放。
- Manufacturing assumptions：材料、涂层、衬垫、紧固件、锁紧和航天适用性均未选；不得用通用 CAD 默认值替代产品或工艺权威。
- Output paths after approval：另建受控 Route-C 参数化源目录及同名 STEP；本授权前包内禁止生成几何。
- Validation targets：闭合正体、稳定标签/基准、装配自由度正确、8/8 连续任务轨迹、10/10 强制状态、间隙/弯曲/夹挤/长度/载体闭合/恢复力矩/Solar keep-out 联合谓词、质量/CG/惯量与不确定度、磨耗/TVAC/寿命及安装后电测。
- Snapshot rule：几何获批并首次生成或可见修改后，必须对主 STEP 生成并人工审查快照；本轮无几何，故 `NOT_APPLICABLE`。

CAD 启动门和下游释放门分层：C2 启动只要求 Owner 授权，以及 bundle OD、适用弯曲限制、芯线/连接器定义、安装界面和寿命目标这些最低产品/接口输入。8/8 连续轨迹、最终质量/CG/惯量、恢复力矩和资格计划是 C3-C7 的并行/下游释放条件，不得前移形成“先有轨迹结果才能建模”的循环。

## 一次通过闭环顺序（均为计划态）

| 阶段 | Entry | Exit | Fail-closed rollback |
|---|---|---|---|
| C0 授权 | ODR-42 请求、冻结资产哈希和边界已提交 | Owner 独立签发的决定引用本请求哈希 | 未签发/范围变化：停在 HOLD，不建模 |
| C1 电气/机械输入冻结 | C0 获批、责任人和配置位置确定 | C2 启动所需最低产品/接口输入受控；其余资格级输入继续留在下游登记册 | 最低输入任一缺项：回 C1，禁止用 Route-B seed 冒充真值 |
| C2 STEP-first 参数化设计 | C1 完成、接受 URDF/Solar R2 哈希仍匹配 | 独立版本源与主 STEP 可复现，具名 datum/关节/安装约束及快照审查完成 | 几何无效、哈希漂移或装配不定：回 C2；不得改冻结资产 |
| C3 8/8 连续任务轨迹 | C2 候选可加载、8 条轨迹定义具权威 | 8/8 连续轨迹均发布、连续性/采样/时间基准和输入哈希可审计 | 缺一条或 UNKNOWN：回 C3，mission coverage=HOLD |
| C4 精确耦合验证 | C2+C3 完成、比较集合非空 | 任务域所有采样的间隙/弯曲/夹挤/长度/导向闭合/Solar keep-out 均 SAFE；只有声明全域时才追加全硬件域扫描 | 任一 UNKNOWN/UNSAFE：回 C2 或 C3，禁止缩小集合后宣称通过 |
| C5 质量/CG/惯量与恢复力矩 | C1 产品数据+C2 几何+C4 运动域可用 | 九构型质量属性和关节恢复负载均有单位、不确定度、来源并满足预算 | 缺数据/超预算：回 C1/C2，禁止更新动力学 SSOT |
| C6 磨耗/TVAC/寿命计划 | C1 材料/工艺和 C4/C5 载荷域受控 | 试件、环境、循环、速率、检查、电测及接受准则获批 | 计划或覆盖不完整：保持 HOLD，不作资格鉴定声明 |
| C7 Handoff/consumer 重绑定 | C4-C6 证据完成、独立验证无 HIGH/CRITICAL | 新接口绑定 Route-C 哈希，运行时 harness gate 对 UNKNOWN/UNSAFE 确实拒绝，负控通过 | 消费者仍绑旧版本或可绕过：ABORT/diagnostic-only，不进入 production/RL |

这个顺序的“一次通过”含义是预先冻结入口、出口和回退点，减少返工；不表示任何阶段已经 PASS。

## 方法来源边界

NASA-STD-8739.4、ECSS-E-ST-33-01C Rev.2、NASA LLIS 687 与 30101 仅用于工作质量、机构生命周期、导向防挂和安装后检查/电测的方法规划。它们不提供本项目的 bundle 尺寸、弯曲半径、间隙、质量、寿命或合格判据。
