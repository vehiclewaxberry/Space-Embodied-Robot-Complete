# Current R2 Mechanical–Dynamics–Control Increment V2

这是一个 **append-only 加性汇合包**。它以 27 个直接 bytes/SHA pin 固定并交叉核验上一版加性汇合、未重发的 parent V4、M01 刚体运动候选批、M4 C01–C09 几何执行矩阵、任务空间静态度量候选，以及抓取后空间惯量 synthetic fixture 内核与两个外部审计根。任务空间外审的 source lock、auditor、tests、README 和 receipt 均被本包直接固定；缺失或篡改任一项均 fail-closed。

本包的最高主张严格限定为：

```text
PASS_APPEND_ONLY_M01_NINE_CANDIDATE_BOUNDS_ZERO_NEW_SYSTEM_CERTIFICATES__M4_C01_C09_ZERO_OF_NINE_CURRENT_STEP_D01_SOURCE_ONLY_UNRUN__TASK_SPACE_STATIC_METRIC_CANDIDATE_ONLY__POSTCAPTURE_SYNTHETIC_FIXTURE_ONLY_C08_C09_NOT_EVALUATED__PARENT_V4_UNCHANGED__CAD_SCENE_PAIR_EDGE_PATH_CONTACT_ATTACHMENT_TIME_DOMAIN_HARDWARE_SAFE_SIM13_NONABORT_NEXT_RELEASE_HOLD
```

因此，本包的 PASS 只表示固定证据能够自洽汇合；它不重发 parent V4，不产生新的 M01 系统运动证书，不生成或运行 STEP/CAD，不绑定 scene/pair/edge/path，不把合成 post-capture fixture 提升为 C08/C09 当前构型结果，也不给 contact、attachment、时域控制、硬件、SAFE、Sim13、non-abort、next-stage 或 release 任何信用。

## 固定结论

- M01：9 个非基座 B601 物体具备 full-q-domain 设计筛选候选界；本批新增系统证书为 0；parent V4 仍为 0/150，外部已存在的 base append-only 观察总数仍仅 1/150。
- M4：C01–C09 current STEP 为 0/9；D01 只是 source-only、非 current 的 q0 诊断配方，尚未执行；没有 CAD kernel、STEP 或快照运行信用。
- 任务空间度量：只成立为 source-derived、dimensionless、静态候选；没有时域跟踪或控制闭环信用。
- Post-capture：只对 22 kg/150 kg synthetic fixtures 的空间惯量与动量初始化内核成立；C08/C09 均为 `NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3`。

## 复现

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B build_increment_gate_v2.py --check
python -B validate_increment_gate_v2.py --check
python -B -m pytest -q -p no:cacheprovider test_increment_gate_v2.py
```

若任一上游 bytes/SHA、严格 JSON 语义、主张、权限、数量或包清单发生漂移，验证必须 fail-closed；禁止在本包内重建上游。
