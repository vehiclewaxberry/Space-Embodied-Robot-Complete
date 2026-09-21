# V2 Mass Ownership Notes

> `STATUS: UNIQUE_OWNERSHIP_INPUT_READY_PHYSICAL_TRUTH_OPEN`  
> `CAD_MASS_AUTHORITY: false`  
> `DYNAMICS_AUTHORITY: false`

## 1. 当前唯一所有权

| group | selected representation | excluded alternative |
|---|---|---|
| servicer mass | bus `23.3032134` + two panels `0.3483933` each | whole-satellite 24 kg row不得与拆分表示相加 |
| adapter mass | plate + boss as one adapter `1.2 kg` | plate/boss 分别计重 |
| B601 mass | accepted URDF 10-link exact sum `4.6955559493429862 kg` | rounded YAML subtotal、其他 CAD material export |

当前可复算的 provisional design ledger：

```text
23.3032134
+ 0.3483933
+ 0.3483933
+ 1.2
+ 4.6955559493429862
= 29.8955559493429862 kg
```

正确称谓：

`PROVISIONAL_DESIGN_LEDGER_TOTAL`

禁止称谓：

- final vehicle mass；
- measured mass；
- V2 CAD mass；
- flight mass；
- dynamics-ready aggregate。

## 2. 未分配硬件

OBC、EPS/PMAD、电池、RW/IMU、传感器、推进、通信、热控和线束尚未选型，其 mass owner 已登记，但 mass value 必须为空，不进入当前 provisional total。

这意味着当前总数不是一个完整系统质量预算，而只是现有来源对象的唯一所有权账本。

## 3. CoM 与惯量

以下保持未知：

- articulated B601 configuration；
- V2 subsystem placement；
- aggregate CoM；
- aggregate inertia；
- mounting and harness mass；
- stowed/deployed configuration mass properties。

SolidWorks 默认材料、体积和“质量 0.00”均无权填补这些字段。

## 4. B3 使用规则

未来 B3 只允许：

- 把 `MASS_OWNER` 写入自定义属性；
- 检查一个实体是否被多个 owner 重复包含；
- 保留 source value 和 physical status；
- 输出 CAD visual-only mass authority = false。

B3 不允许：

- 用 CAD 重新计算结果覆盖本表；
- 给 unknown placeholder 分配默认密度；
- 把 target mass 加入 servicer；
- 把 panel 或 adapter 子几何重复计重。

## 5. 物理升级路径

```text
hardware selection
  → component weighing / datasheet provenance
  → configuration-specific placement
  → frame-consistent CoM/inertia recomposition
  → independent mass-property review
  → separate dynamics authorization
```
