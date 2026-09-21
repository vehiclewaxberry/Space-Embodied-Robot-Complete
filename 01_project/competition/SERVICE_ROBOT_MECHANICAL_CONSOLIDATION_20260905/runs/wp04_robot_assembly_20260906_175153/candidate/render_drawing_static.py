"""Render the validated exchange DXF directly; no edits to its geometry."""
from pathlib import Path
import json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext,Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration,ColorPolicy,BackgroundPolicy
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=HERE/'r01_interfaces.dxf';before=sha(p);doc=ezdxf.readfile(p);outputs=[]
for i,name in [(0,'lower_deck'),(2,'lower_angle_web'),(5,'upper_deck'),(10,'shear_web')]:
    fig=plt.figure(figsize=(12,9));ax=fig.add_axes([.02,.02,.96,.96])
    ctx=RenderContext(doc);ctx.set_current_layout(doc.modelspace());ctx.current_layout_properties.set_colors(bg='#ffffff',fg='#111827')
    Frontend(ctx,MatplotlibBackend(ax),config=Configuration(color_policy=ColorPolicy.BLACK,background_policy=BackgroundPolicy.WHITE)).draw_layout(doc.modelspace(),finalize=True)
    fig.set_size_inches(12,9)
    col=i%3;row=i//3;ax.set_xlim(col*480-30,col*480+410);ax.set_ylim(-row*400-140,-row*400+235);ax.set_aspect('equal',adjustable='box');ax.set_axis_off()
    out=HERE/'results'/('drawing_'+name+'.png');fig.savefig(out,dpi=160,facecolor='white');plt.close(fig);outputs.append(str(out))
assert before==sha(p)
(HERE/'results/DRAWING_STATIC_REVIEW.json').write_text(json.dumps(dict(source=str(p),source_sha256=before,outputs=outputs,geometry_modified=False,reason='Installed DXF package builder emits geometry.json while snapshot launcher expects preview.glb; validated DXF rendered directly with ezdxf Matplotlib backend'),indent=2),encoding='utf-8')
print(json.dumps(outputs))
