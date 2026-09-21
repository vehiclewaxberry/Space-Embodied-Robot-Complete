# V2 Mechanical Interface Preliminary Design Report

> `STATUS: INTERFACE_RESPONSIBILITY_CLOSED_PHYSICAL_DEFINITION_OPEN`  
> `INTERFACE_COUNT: 10`  
> `CAD_AUTHORING: NOT_AUTHORIZED`

## 1. Interface design rule

每个接口必须同时回答：

1. parent/child 是谁；
2. 使用哪个 frame/transform；
3. 哪些几何已绑定；
4. 哪个 owner 提供载荷和物理连接；
5. B3 允许建立什么；
6. 哪些字段必须保持 null；
7. 哪个证据关闭接口。

“有一块接触面”不等于接口闭合；“有 reference geometry”也不等于连接、载荷或资格完成。

## 2. Robot mount interfaces

### IF-RM-001 — spacecraft primary structure to adapter

已绑定：

- parent：front task-face primary structure；
- child：robot mount adapter；
- frame：`M`；
- transform：`T_SM`；
- mount origin：`[185.25, 0, 0] mm` in `S`；
- orientation：`Ry=+90°`；
- existing flange/adapter envelope。

保持未知：

- bolt/locator pattern；
- tolerance/fit；
- fastener/preload；
- material/surface；
- 六维 interface wrench；
- allowable displacement、stiffness、strength、modal target。

未来 B3 只能建立 named plane、adapter envelope、load-path overlay 和 null-property fields。

### IF-RM-002 — adapter to accepted B601

已绑定：

- frame：`A0`；
- `T_MA0=identity contract`；
- B601 10-link/9-joint topology；
- accepted URDF read-only source。

保持未知：

- physical stack-up、tolerance、fasteners；
- electrical/thermal bonding；
- physical vendor STEP。

未来 B3 可以插入受控 visual/reference identity，不得修改 URDF 或重建供应商内部结构。

## 3. Deployable interfaces

### IF-SA-L / IF-SA-R

根 frame 和 origin 已绑定：

- `F_L=[-56.75,+113.15,0] mm`；
- `F_R=[-56.75,-113.15,0] mm`。

hinge、lock/release、drive、harness、stowed envelope、root loads 和 deployment dynamics 均未知。PDR 仅定义 root plane、owner、swept-zone owner 和 configuration separation。

## 4. Payload and end-effector interfaces

### IF-PL-001

感知载荷只有 reservation owner。`T_SC`、相机型号、FOV、标定、质量和 BOM 均为空。B3 只可建立 zero-solid mount region、线束通道 owner 和 occlusion review overlay。

### IF-EE-001

保留 `G/E_virtual`，但 `T_E_TCP`、physical TCP、contact patch、force sensor 和 compliant tool 均为空。B3 不创建实体接触或目标 mate。

## 5. Internal packaging interfaces

### IF-AV-001

middle bay 的 C&DH、EPS/PMAD、battery、ADCS 是四个独立 volume owner。未来每个 owner 必须分别提供 mount plane、service direction、harness entry 和 thermal interface。

### IF-SV-001

rear bay 的 propulsion、communications、thermal 和 service 是四个独立 owner。plume、antenna/RF、radiator 和 rear access 均需专属 keepout，不得用一个总盒体冒充接口闭合。

### IF-MA-001

维护接口覆盖 panel removal、tray extraction、tool access 和 assembly sequence。当前方向为 proposal，不包括工具尺寸、紧固件或在轨维护能力。

## 6. Mission target interface

### IF-TG-001

target/debris 保持 `EXCLUDED`：

- active assembly：false；
- mate/contact：false；
- `T_ST/T_SD`：null；
- 只允许独立场景和任务语义水印。

## 7. Interface change control

以下任一变化要求重新 PDR：

- `T_SM` 或 `T_MA0` 变化；
- B601 topology/source hash 变化；
- 任一 unknown interface field 获得真实输入；
- target、physical TCP 或 selected sensor 被要求进入 active assembly；
- solar root 或 configuration 定义变化；
- profile/deployer 边界变化。

## 8. PDR disposition

十个接口的身份、frame、owner、允许动作和关闭证据均已规定。其物理连接、载荷、硬件和资格多数仍未闭合，因此当前裁决是：

`INTERFACE_RESPONSIBILITY_CLOSED / PHYSICAL_INTERFACE_DEFINITION_OPEN`
