from pathlib import Path
import json,hashlib,sys
from candidate_context import WP02
sys.path.insert(0,str(WP02/'runtime_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext,Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration,ColorPolicy,BackgroundPolicy
H=Path(__file__).resolve().parent;p=H/'r07_interfaces.dxf';doc=ezdxf.readfile(p);outputs=[]
for i,name in enumerate(['upper_cap','lower_spacer','retention_lug','retention_foot','rear_bulkhead','web_relief']):
    fig=plt.figure(figsize=(12,8));ax=fig.add_axes([.02,.02,.96,.96])
    ctx=RenderContext(doc)
    Frontend(ctx,MatplotlibBackend(ax),config=Configuration(color_policy=ColorPolicy.BLACK,background_policy=BackgroundPolicy.WHITE)).draw_layout(doc.modelspace(),finalize=True)
    fig.set_size_inches(12,8);col=i%3;row=i//3
    if i<4:
        ax.set_xlim(col*430-15,col*430+190);ax.set_ylim(-row*400-85,-row*400+50)
    else:
        ax.set_xlim(col*430-22,col*430+390);ax.set_ylim(-row*400-105,-row*400+260)
    ax.set_aspect('equal',adjustable='box');ax.set_axis_off()
    out=H/'results'/('drawing_r07_'+name+'.png');fig.savefig(out,dpi=150,facecolor='white');plt.close(fig);outputs.append(str(out))
(H/'results/R07_DRAWING_RENDER.json').write_text(json.dumps(dict(source=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),outputs=outputs,method='ezdxf direct render of final face-projected DXF'),indent=2),encoding='utf-8')
print(json.dumps(outputs))
