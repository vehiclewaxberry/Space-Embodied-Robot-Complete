"""Append execution facts to the preparation matrix without rewriting it."""
from pathlib import Path
import csv,json
R=Path(__file__).resolve().parents[1]
source=R/'results/MECHANICAL_MODULE_MATRIX.csv'
rows=list(csv.DictReader(source.open(encoding='utf-8-sig')))
facts={
'M01':('三种固定姿态原生装配均已保存/冷读并独立核验；每态597实例、978实体。','三态固定位置不含运动配合；整机STEP未输出。','results/NATIVE_DELIVERY_CHECK_ALL.json'),
'M02':('WP06侧连接八替换、四删除、十六新增已集成三态。','后舱板四加强肋、盖板连接与首次装入仍未闭环。','results/INTEGRATION_MANIFEST.json'),
'M03':('B601实体在三态原生装配中已回读；显示网格恢复同源BRep。','WP05的10项几何HOLD继承；实装版本、载荷及支承区未确认。','results/NATIVE_DELIVERY_CHECK_ALL.json'),
'M04':('两站17件候选+1件鞍座上下文分别形成18件SLDASM/STEP；各475局部检查及各三态邻件9895项通过。','新保持机构仍为独立局部候选，未集成597整机；驱动、销帽、全程释放及强度仍OPEN。','results/RETENTION_NATIVE_S0_c03_v1.json;results/RETENTION_NATIVE_S1_c03_v1.json'),
'M05':('继承太阳翼几何已随三态原生回读；补入未选型太阳板机械参考。','太阳翼真实质量、叶框连接、轴向保持、HDRM、锁止及活动线束未关闭。','results/PCB_REFERENCE_STEP_READBACK.json'),
'M06':('EPS端点与机械安装必填项已登记。','没有选定星载EPS；24V臂与低压母线转换/保护须等实际负载数据。','ecad/ELECTRICAL_INTERFACE_CONTRACT.json'),
'M07':('电池参考板轮廓/孔系形成STEP并读回；预算箱保持原定义。','参考板未选用；实际电芯、组件、端接、固定与热界面未绑定。','results/PCB_REFERENCE_STEP_READBACK.json'),
'M08':('计算主板机械参考已生成；共享设备与电气owner已登记。','未选定主板与驱动设备，不将参考板当成已安装设备。','ecad/ELECTRICAL_MODULE_MATRIX.csv'),
'M09':('背板参考STEP已生成；按预算箱六正交方向做尺寸筛查。','未形成实装卡笼；板卡集合、连接器堆叠和载体尺寸待定。','results/ELECTRICAL_MECHANICAL_FIT_SCREEN.json'),
'M10':('ADCS功能/电气端点已登记，继承设备预算。','轮组、星敏、IMU实物与安装轴基准未绑定。','ecad/ELECTRICAL_MODULE_MATRIX.csv'),
'M11':('通信共享设备、天线与线缆接口缺项已登记。','实际天线孔系、馈线、支架固定及拆装未关闭。','ecad/ELECTRICAL_MODULE_MATRIX.csv'),
'M12':('任务感知供电/数据/安装接口缺项已登记。','相机镜头实物、固定孔系、光轴标定与端口未绑定。','ecad/ELECTRICAL_MODULE_MATRIX.csv'),
'M13':('线束逻辑端点、供电与通信未知项已形成拒绝不完整通电的合同。','真实针脚、OD、动态弯曲半径、扭转与活动自由段未闭环。','results/ELECTRICAL_CONTRACT_CHECK.json'),
'M14':('热控与EMC接触、回流/搭接、绝缘要求已登记。','耗散、表面材料、预紧与热带端接仍待硬件参数。','ecad/ELECTRICAL_INTERFACE_CONTRACT.json'),
'M15':('推进功能与共享预算质量归属已登记。','无已选型推力器、储箱或管路实体。','ecad/ELECTRICAL_MODULE_MATRIX.csv'),
'M16':('保持机构条件装入/拆卸路径与工具空间已局部核验。','整机地面支承、机械臂卸载、定位和防倾覆未关闭。','results/retention_detail_c03/station_0/CHECK_local.json'),
}
out=R/'results/MECHANICAL_MODULE_EXECUTION_STATUS.csv'
assert not out.exists() and len(rows)==16 and len(facts)==16
fields=['module_id','functional_module','actual_execution','remaining_boundary','evidence','engineering_design_complete']
with out.open('w',encoding='utf-8-sig',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for row in rows:
        actual,boundary,evidence=facts[row['module_id']]
        writer.writerow(dict(module_id=row['module_id'],functional_module=row['functional_module'],actual_execution=actual,remaining_boundary=boundary,evidence=evidence,engineering_design_complete=False))
print(json.dumps({'path':str(out),'rows':16,'original_preparation_matrix_unchanged':True}))
