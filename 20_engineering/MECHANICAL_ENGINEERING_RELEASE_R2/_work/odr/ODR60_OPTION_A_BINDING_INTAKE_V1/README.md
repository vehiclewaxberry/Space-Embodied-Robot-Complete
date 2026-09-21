# ODR-60 Option A binding intake V1

本目录只做三件事：证明 accepted B601 URDF 的 `1BC2...`/`408147...` 双哈希是同一内容；把经 ODR-45 确认的物理安装轨—动力学轨桥交叉绑定；冻结 mount、M01 scene 与 11,166 对 clearance policy 的 fail-closed intake。它不编辑 URDF/CAD，不打开现役几何，不运行 FK、pair、edge 或 path。

## 已解决的误判

- `1BC2B748...` 是 accepted URDF 磁盘 CRLF 原始字节哈希；`408147DD...` 是相同文件把 292 个 CRLF 替换为 LF 后的哈希。不存在旧/新 URDF、joint tree、axis、limit、geometry reference 或 inertial 语义冲突。
- 208 mm/25° 是 WP11 物理安装轨，185.25 mm/`Ry(+90°)` 是 ODR-01 动力学参考轨。唯一显式桥 `0ACEB659...` 已由 ODR-45 确认为 `CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE`。

## 仍未闭合

- 执行期 mount 采用 D6 6 位小数还是 ODR-43 12 位/full 拼写尚未绑定；当前 collision assets 到 accepted URDF frame 的 registration 也未签发。
- M01 的 9 个 required bindings 仍为 `0/9`。释放过程还必须拆为释放前常场景 edge、释放事件合同、释放后常场景 edge；Solar HDRM required 字段缺失，ARM HDRM/G07/G08/MID/target 也不在 150-object universe。
- clearance policy 只有不等式与 typed-row 合同，没有 11,166 个 Owner 数值 requirement rows。所有 wildcard、pair-class 默认、继承、caller override 与自动补零均被禁止。
- 系统 object motion certificates 为 0，C-section Hausdorff/radius 证书为 0/9，pair oracle backend 未绑定。

因此本包的正确结果是 `intake schema PASS / execution HOLD`。任何 `null` 被填入之前，都必须同时提供适用域、Owner/revision、来源字段与 SHA，并重发对应 binding；不能通过直接编辑本目录把 `false` 改成 `true` 获得权限。

## 文件

- `URDF_CONTENT_IDENTITY_AUDIT_V1.json`：双 EOL 哈希的机器证明。
- `PROVISIONAL_MOUNT_REBIND_CANDIDATE_V1.json`：双轨 frame/bridge 元数据与两个剩余执行 blocker。
- `SYSTEM_SCENE_STATE_INTAKE_V1.json`：9 字段零绑定、事件分段和对象宇宙缺口。
- `CLEARANCE_POLICY_INTAKE_V1.json`：11,166 行所需字段、数值账本与禁止默认规则；当前行数为 0。
- `BINDING_INTAKE_GATE_V1.json`：生成的 fail-closed Gate。
- `BINDING_INTAKE_SHA256_V1.csv`：外部来源与本包产品的哈希清单；不自包含自身哈希。

## 复现

```powershell
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/build_binding_intake_gate.py --write
python -m pytest -q 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/test_binding_intake_gate.py
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/build_binding_intake_gate.py --check
```

`--write` 只写本目录的 Gate 与 manifest；`--check` 不写文件，并要求两者与确定性重建逐字节一致。
