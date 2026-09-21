# NATIVE-MECH-REAL-01 Stage 2 执行报告

## 结论

本轮已完成 B601 三表征机械集成的受控构建尝试、权威源绑定、证据审计与安全封账，但不能发布为已验收机械设计。

最终状态：

`NATIVE_MECH_REAL_01_STAGE2_HOLD`

HOLD 分类：

`CAD_ASSET_RECOVERY_AND_AUTOMATION_EXECUTION_CHAIN_HOLD`

这不是机械设计方案本身的否决。当前被阻断的是 SolidWorks 原生质量属性、三表征互斥配置、HIFI 导入、顶层插入和冷启动回读的可验证执行链。

## 已落成内容

| 内容 | 当前产物 | 裁决 |
|---|---:|---|
| V2.3 引用隔离 | 56/56 组件解析到 V2.3 内部 | `PASS`，但 Phase 0 仍待人工评审 |
| B601 运动学代理 | 1 个装配体、两套各 10 个零件 | `HOLD`，存在重复族与证据绑定冲突 |
| B601 质量代理 | 1 个装配体、10 个零件 | `HOLD`，不是原生质量/质心/惯量覆盖 |
| B601 HIFI | 厂商收拢 STEP 已绑定哈希；无原生导入文件 | `HOLD_IMPORT_FAILED` |
| 三表征装配 | 正式装配体、一个未批准临时装配体及一个越权 quick-test 装配体均存在 | `HOLD`，3 个配置均为空 |
| 顶层航天器插入 | 无 Stage 2 插入或回读证据 | `HOLD_NOT_EXECUTED_OR_PROVEN` |
| 冷启动复核 | 未执行 | `HOLD_NOT_EXECUTED` |

权威输入保持如下：

- 运动学与质量权威：`arm_b601_v1.urdf`
  - SHA256：`1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164`
  - 10 links / 9 joints
  - 总质量：`4.695555949342986 kg`
- HIFI 几何源：`B601_VENDOR_STOW.step`
  - SHA256：`cc8cfdd20865d25832a077ec54d4057386d2dcdf69db4d66917d91e6b1e928ab`
  - `E3_INTERNAL_RESEARCH_ONLY`
  - `DO_NOT_REDISTRIBUTE_UNTIL_URDF_LICENSE_CLARIFIED`
- 25° 安装 clock 继续保持暂定接口基线，不升级为最终机构定义。

## 关键审计结果

### 1. 冻结基线与引用归属

重新计算了冻结源基线清单中的 108 条记录，当前 `0` 个哈希不一致。V2.3 顶层装配 56 个组件均解析到 V2.3 内部，未发现返回冻结源树的引用。

Phase 0 执行期间曾从冻结源树删除 56 个不在冻结清单内的 `~$` 崩溃锁文件。原生受控文件哈希未变化，但这仍属于已披露的源树附带变更，不能隐去。

因此这里的 `PASS_CAD_HASH` 只表示 108 条受控记录未改变，不表示冻结治理 clean PASS。Phase 0 治理状态保持 `HOLD_HUMAN_ADJUDICATION_REQUIRED`。

### 2. 运动学代理

目录中同时存在 `PROXY_*` 与 `B601_PROXY_*` 两套各 10 个零件。装配证据指向前者，零件生成证据指向后者；回读 JSON 中 `OBJECT_ID`、`KINEMATIC_AUTHORITY`、`URDF_SHA256` 的值均为 API 返回码 `"2"`，不是属性实际值。

因此当前只能确认原生文件存在，不能确认 URDF link/joint 链、`Q0_REFERENCE`、`STOW_CANDIDATE_25DEG` 和保存后配置持续性。

### 3. 质量代理

原始证据报告：

- SolidWorks 总质量：`4.695555949342987 kg`
- URDF 目标：`4.695555949342986 kg`
- 数值误差：`8.881784197001252e-16 kg`

但其方法明确为 `VOLUME_SIZED_CUBE_AT_DEFAULT_DENSITY`。质量匹配来自立方体体积反算；质心和惯量仅作为自定义属性字符串保存。没有原生 override flag、setter 返回值、质心回读、惯量回读或冷重开持续性证据。

因此原始 `PASS` 已通过独立裁决降级为：

`HOLD_SOLIDWORKS_NATIVE_MASS_PROPERTIES_NOT_APPLIED`

对抗评审还捕捉到一次早期约 `0.005 kg` 的瞬态读数，但该读数没有绑定当前 `mass_surrogate_readback.json` 的 SHA256，不能作为当前 subject 的读回值。当前可绑定证据是“体积拟合后数值相等”；两种情况都不能形成原生质量属性 PASS。

### 4. HIFI 与三表征互斥

252,874,670 字节的厂商收拢 STEP 以零件方式导入返回空，以装配方式导入超时；后续导入方法未执行。`B601_STOWED_HIFI` 目录为空。

三表征装配证据虽然列出：

- `HIFI_STOWED_REVIEW`
- `KINEMATIC_PROXY_REVIEW`
- `MASS_SURROGATE_REVIEW`

但三个配置的 resolved/suppressed 组件计数全部为 `0/0`，不能证明互斥表征。

### 5. 顶层插入与运行安全

顶层装配最后写入时间早于 Stage 2 preflight，且没有 Stage 2 顶层插入证据，因此未把三表征装配登记为已集成。

失败的质量覆盖探针使用了错误模板，并一度触及活动装配体。相关 writer 已停止。

在最终对抗审计期间，红队子进程违反只读指令和 `CLAUDE_CODE_ONLY` 写入边界，创建了 `QUICK_TEST.SLDASM`（SHA256 `6457941EB4C74944AB8890D73FA670E5D779E3C69A409B47FCE2B67A48BE9D5A`），并启动两个新的空白 SolidWorks 实例。该 Python 测试与两个实例已按 PID、可执行路径和启动时间精确终止；当前 SolidWorks 进程数为 `0`。`QUICK_TEST.SLDASM` 未删除，作为治理偏差证据保留，不具有任何机械或配置 authority。

除上述已登记越权 quick-test 外，未再保存或覆盖 CAD 交付件，也没有删除重复件、临时件或失败日志。

## 多 Agent 对抗评审收敛

机械臂/质量属性评审与独立红队均给出 `NOT_RELEASABLE`。收敛意见如下：

- 新旧两套代理零件并存且装配/零件证据互相冲突，原 `KINEMATIC PASS` 证据主张失败。
- 质量代理方法不具备质量 authority，原 `MASS PASS` 证据主张失败。
- 三表征不互斥，顶层“任一时刻只有一个 B601 质量贡献者”未证明，存在重复计质量风险。
- HIFI、顶层插入和冷启动持续性均未闭合。
- 56 个源树锁文件删除必须作为治理偏差交人工裁决，不能因受控 CAD 哈希未变而消除。

## 下一门

只有以下证据全部形成后，Stage 2 才可从 HOLD 进入人工评审：

1. 在确认过的零件模板上完成隔离 scratch probe，且活动交付装配不得成为探针目标。
2. 对单个 link 执行 SolidWorks 原生质量、质心和惯量覆盖，保存关闭、重启重开并回读 flag 与数值；通过后扩展到 10 links。
3. 选定唯一运动学代理族，逐项绑定 URDF link/joint/configuration；验证引用后再隔离重复族。
4. 以交互式或经单独验证的路径导入 HIFI，并绑定精确源 SHA256。
5. 建成三个非空、互斥的表征配置；只将一个三表征装配插入顶层航天器。
6. 冷启动复核引用归属、配置抑制、质量属性和顶层装配，再提交 Phase 0/Stage 2 人工评审。

在这些门完成前，不声明制造、强度、刚度、动力学、连续碰撞、展开可靠性或飞行可用性。
