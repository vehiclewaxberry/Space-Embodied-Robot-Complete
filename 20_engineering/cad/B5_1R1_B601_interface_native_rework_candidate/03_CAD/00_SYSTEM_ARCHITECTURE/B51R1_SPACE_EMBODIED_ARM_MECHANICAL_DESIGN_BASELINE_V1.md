# B5.1R1 空间具身智能机械臂机械设计基线 V1

状态：`ENGINEERING_CANDIDATE_BASELINE_NO_FLIGHT_CREDIT`

本方案把机械系统分成五层：零实体 Master Skeleton、十个零质量运动
Carrier、按 link 刚性挂接的精细几何、绕过可拆面板的航天器接口与收拢
约束，以及位于 VLA 和执行器之间的物理/SAFE 层。

## 机构主线

运动拓扑严格保持 accepted URDF 的 `6R + 1 fixed + 2 independent P`。
父 Carrier 的 joint-side frame 承载一次 URDF origin；子 Carrier 的对应
frame 为 link-local identity。任何 child 侧再次施加 origin 的实现均判为
失败。两指没有 mimic 或共享宽度驱动。

## 航天器接口

共同约束为 160 × 160 mm 候选安装面和 Ø100 mm 中央禁入通道。101.65 mm
是纵梁轴，110.15 mm 是主结构参考面，113.15 mm 仅为可拆面板/footprint
层。面板永远不获得根部弯矩主载荷路径信用。

S10 比较三种候选：双横梁四纵梁节点桥接、前后主框桥接、局部闭合加强
环。当前不作飞行架构下选；所有尺寸、材料、紧固件和载荷门槛在缺少
launcher/deployer ICD 与正式载荷谱时保持 provisional。

## G07/G08/HDRM

采用“两站运动学兼容约束”候选：G07 为主 V 形定位站，约束两个局部法向
并允许臂轴向浮动；G08 为次级平面浮动鞍座，仅约束一个局部法向。HDRM
沿鞍座法向施加预紧，释放后撤出残余禁入包络。所有支撑通过独立支柱或
桥架接入命名主框/纵梁，并与可拆面板留隙。最终约束信用必须由接触
Jacobian、容差角点和六向单位载荷反力闭合给出。

## Gate 顺序

先完成刚体名义连续间隙 G8a，再由结构/模态阶段生成结构变形、垫压缩、
热、制造装配公差、回差和线束不确定度包络，最后运行鲁棒连续间隙 G8b。
任一包络来源未知即保持 UNKNOWN/HOLD。H9 在没有权威 ICD 时维持
Mode A/Mode B 双分支。
