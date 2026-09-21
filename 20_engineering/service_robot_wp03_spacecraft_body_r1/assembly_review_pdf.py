"""Print actual CAD review snapshots and measured configuration dimensions."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
HERE=Path(__file__).resolve().parent
PAGES=[
 ('servicer_service_iso','航天服务星 · 服务工作态','service','完整 B601 / 双翼展开 / 保持器折退 / 无 GSE'),
 ('servicer_parking_iso','完整机械臂 · 开放停放参考','parking','OPEN_PARKING_REFERENCE；尚未得到紧凑飞行收拢结论'),
 ('servicer_released_iso','随星保持器 · 释放后关键帧','released','臂仍保持停放姿态；先退出保持器，再进行机械臂首动'),
 ('body_equipment_cutaway_internal','主承力结构与设备舱 · 内部观察',None,'显示时隐藏两侧剪力板以观察内部；真实装配与质量仍保留剪力板'),
 ('body_equipment_cutaway_opposite','主承力结构与设备舱 · 反向剖视',None,'相贴为候选安装关系；预紧、真实底脚与传热能力待核实'),
 ('body_exploded_iso','星体结构与设备 · 爆炸示意',None,'显示位移只用于装配说明，不用于碰撞、包络或质量惯量'),
 ('wing_module_iso','双翼与外置铰链 · 独立模块',None,'三叶翼固定偏置坐标；叶片为预算代理，驱动和锁止待实选'),
 ('retention_module_iso','屋顶安装保持器 · 独立模块',None,'拔销 26 mm → 上盖 100° → 下鞋 80 mm → 桅杆 90°'),
 ('ground_ait_iso','地面装调装配 · 辅助视图',None,'同一整星 + 独立 GSE 底板/支脚；GSE 不进入随星质量')
]
def main():
    font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc');used=[]
    with PdfPages(HERE/'drawings/WP03_ASSEMBLY_REVIEW.pdf') as pdf:
        for i,(prefix,title,state,note) in enumerate(PAGES,1):
            paths=sorted((HERE/'snapshots').glob(prefix+'_*.png'))
            if not paths:raise FileNotFoundError(prefix)
            path=paths[-1];used.append(str(path));fig=plt.figure(figsize=(11.7,8.3),facecolor='white')
            fig.text(.055,.947,title,fontproperties=font,fontsize=18,color='#183951')
            fig.text(.055,.901,note,fontproperties=font,fontsize=10,color='#435b6b')
            ax=fig.add_axes([.045,.20,.91,.67]);ax.imshow(plt.imread(path));ax.axis('off')
            if state:
                r=json.loads((HERE/f'results/{state}_instances.json').read_text(encoding='utf-8'));b=r['bounds']
                dims=' × '.join(f'{v:.3f}' for v in b['size_mm']);mn=', '.join(f'{v:.3f}' for v in b['min_mm']);mx=', '.join(f'{v:.3f}' for v in b['max_mm'])
                fig.text(.055,.155,'全显示几何（含功能保留区）X × Y × Z：'+dims+' mm',fontproperties=font,fontsize=10,color='#183951')
                fig.text(.055,.116,f'S extrema / mm: min [{mn}]   max [{mx}]',fontsize=9,color='#435b6b')
            else:fig.text(.055,.145,'实际 CAD 渲染；设备、执行器及线缆的代理表示不构成实选硬件。',fontproperties=font,fontsize=10,color='#435b6b')
            fig.text(.055,.058,'WP03 R1 | NOT_FOR_MANUFACTURE | NOT_FLIGHT_QUALIFIED | CAD snapshots',fontsize=9,color='#a84219')
            fig.text(.918,.045,f'{i:02d}/{len(PAGES):02d}',fontsize=9,color='#435b6b')
            pdf.savefig(fig);plt.close(fig)
    (HERE/'results/ASSEMBLY_PDF_SOURCES.json').write_text(json.dumps(used,indent=2),encoding='utf-8')
    print('Saved 9-page actual-CAD assembly review PDF')
if __name__=='__main__':main()
