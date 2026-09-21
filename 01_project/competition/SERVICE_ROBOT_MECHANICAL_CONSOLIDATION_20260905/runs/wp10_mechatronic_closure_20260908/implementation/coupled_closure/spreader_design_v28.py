"""Shared geometric mask for proposed integral spreader increments; S frame mm."""
import numpy as np

def added_mask(x,y,p,region):
    x0,y0,x1,y1=region
    keep=(x>=x0)&(x<=x1)&(y>=y0)&(y<=y1)
    q=p['beam_reliefs']
    for xx in q['x_mm']:keep &= abs(x-xx)>=q['width_mm']/2
    for key in ['lower_fastener_blind_pockets','MIPS_blind_pockets']:
        q=p[key]
        for xx in q['x_mm']:
            for yy in q['y_mm']:keep &= (x-xx)**2+(y-yy)**2 >= (q['diameter_mm']/2)**2
    q=p['pillar_edge_notches']
    for xx in q['x_mm']:
        for yy in q['y_mm']:keep &= (x-xx)**2+(y-yy)**2 >= (q['diameter_mm']/2)**2
    for xx,yy in p['mount_centers_xy_mm']:
        keep &= (x-xx)**2+(y-yy)**2 >= p['boss_radius_mm']**2
    c=p['chb_path'];cx,cy=c['center_xy_mm'];w,h=c['seat_size_mm']
    keep &= ~((abs(x-cx)<=w/2)&(abs(y-cy)<=h/2))
    ya,yb=c['finger_riser_abs_y_mm']
    keep &= ~((abs(x-cx)<=w/2)&(abs(y)>=ya)&(abs(y)<=yb))
    return keep

def augment_sheet(sheet,p,region,height,k=130.):
    """Update the actual allocated thickness field, then rebuild its conductance."""
    from scipy.sparse import coo_matrix
    X,Y=sheet.X,sheet.Y;fraction=np.zeros_like(X)
    for ox in (np.arange(16)+.5)/16-.5:
        for oy in (np.arange(16)+.5)/16-.5:
            x=X+ox*sheet.dx;y=Y+oy*sheet.dy
            active=np.ones_like(X,dtype=bool)
            for xx,yy,d in sheet.face.get('holes_ab_d_mm',[]):active &= (x-xx)**2+(y-yy)**2 >= (d/2)**2
            fraction+=added_mask(x,y,p,region)*active/256
    sheet.thickness += np.divide(height*fraction,sheet.fraction,out=np.zeros_like(X),where=sheet.fraction>0)/1000
    rr=[];cc=[];vv=[];ny,nx=X.shape
    for j,i in zip(*np.where(sheet.active)):
        for jj,ii in [(j,i+1),(j+1,i)]:
            if jj>=ny or ii>=nx or not sheet.active[jj,ii]:continue
            f1,f2=sheet.fraction[j,i],sheet.fraction[jj,ii]
            t1,t2=sheet.thickness[j,i],sheet.thickness[jj,ii]
            g=k*(2*t1*t2/(t1+t2))*(2*f1*f2/(f1+f2))*(sheet.dy/sheet.dx if ii!=i else sheet.dx/sheet.dy)
            a,b=sheet.ids[j,i],sheet.ids[jj,ii]
            rr.extend([a,b,a,b]);cc.extend([a,b,b,a]);vv.extend([g,g,-g,-g])
    sheet.L=coo_matrix((vv,(rr,cc)),shape=(sheet.n,sheet.n)).tocsr()
    return float(fraction.sum()*sheet.dx*sheet.dy*height)
