"""Print-friendly vector drawing sheets from the same CAD projected contours."""
from pathlib import Path
from interface_drawings import geometry_rows,HERE
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties

def main():
    font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
    with PdfPages(HERE/'drawings/WP02_INTERFACE_DRAWINGS.pdf') as pdf:
        for i,(pn,title,geo,notes,shape) in enumerate(geometry_rows(),1):
            fig=plt.figure(figsize=(11.7,8.3),facecolor='white')
            fig.text(.065,.93,title,fontproperties=font,fontsize=17,color='#183951')
            fig.text(.065,.885,pn,fontsize=10,color='#51647a')
            ax=fig.add_axes([.07,.24,.47,.59]);ax.set_aspect('equal');ax.set_axis_off()
            polys=[geo] if geo.geom_type=='Polygon' else list(geo.geoms)
            for p in polys:
                xy=list(p.exterior.coords);ax.fill([r[0] for r in xy],[r[1] for r in xy],facecolor='#dfeaf0',edgecolor='#102d40',lw=1)
                for ring in p.interiors:
                    xy=list(ring.coords);ax.fill([r[0] for r in xy],[r[1] for r in xy],facecolor='white',edgecolor='#102d40',lw=.8)
            x0,y0,x1,y1=geo.bounds;w=x1-x0;h=y1-y0;off=max(w,h)*.12
            ax.annotate('',(x0,y0-off),(x1,y0-off),arrowprops=dict(arrowstyle='<->',lw=.8,color='#334155'))
            for x in [x0,x1]:ax.plot([x,x],[y0-off*1.15,y0],color='#64748b',lw=.7)
            ax.text((x0+x1)/2,y0-off*1.5,f'{w:.3f} mm',ha='center',va='top',fontsize=10)
            ax.annotate('',(x1+off,y0),(x1+off,y1),arrowprops=dict(arrowstyle='<->',lw=.8,color='#334155'))
            for y in [y0,y1]:ax.plot([x1,x1+off*1.15],[y,y],color='#64748b',lw=.7)
            ax.text(x1+off*1.5,(y0+y1)/2,f'{h:.3f} mm',rotation=90,ha='center',fontsize=10)
            ax.plot([x0,x1],[0,0],color='#4b718c',ls='--',lw=.5);ax.plot([0,0],[y0,y1],color='#4b718c',ls='--',lw=.5)
            ax.set_xlim(x0-2*off,x1+3*off);ax.set_ylim(y0-3*off,y1+off)
            fig.text(.59,.79,'INTERFACE / DATUM NOTES',fontsize=12,weight='bold',color='#183951')
            for j,line in enumerate(notes):fig.text(.59,.735-j*.059,line,fontsize=9,color='#263a4f')
            fig.text(.065,.16,'TOP FACE PROJECTION FROM GENERATED BREP | mm | WP02 R1',fontsize=10,color='#183951')
            fig.text(.065,.12,'NOT_FOR_MANUFACTURE',fontsize=13,weight='bold',color='#aa3a16')
            fig.text(.065,.078,'Material, thread engagement, tolerances, preload and hardware registration remain unverified.\nContour sampling <= 0.25 mm; use STEP geometry for exact circular interfaces. CAD dimensions are not physical measurements.',fontsize=8,color='#596a7c')
            fig.text(.91,.045,f'{i:02d}/05',fontsize=9)
            pdf.savefig(fig)
            fig.savefig(HERE/'drawings'/f'{i:02d}_{pn}.png',dpi=160)
            plt.close(fig)
    print('Saved five checked CAD-projection sheets as PDF and PNG')
if __name__=='__main__':main()
