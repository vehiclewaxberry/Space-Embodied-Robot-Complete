"""Analytic 3-D circular fillets and arc-length slicing. No CAD dependency."""
import math
def add(a,b):return [x+y for x,y in zip(a,b)]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def mul(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def unit(a):
 n=norm(a);assert n>1e-10
 return mul(a,1/n)
def point(seg,t):
 assert -1e-9<=t<=1+1e-9
 if seg['kind']=='line':return add(seg['start'],mul(sub(seg['end'],seg['start']),t))
 ang=seg['angle']*t
 return add(seg['center'],add(mul(seg['radial'],seg['radius']*math.cos(ang)),mul(seg['tangent'],seg['radius']*math.sin(ang))))
def tangent(seg,t):
 if seg['kind']=='line':return unit(sub(seg['end'],seg['start']))
 ang=seg['angle']*t
 return add(mul(seg['radial'],-math.sin(ang)),mul(seg['tangent'],math.cos(ang)))
def fillet_path(vertices,radius):
 assert radius>0 and len(vertices)>=3
 corners={}
 for i in range(1,len(vertices)-1):
  a,b,c=vertices[i-1:i+2];u=unit(sub(b,a));v=unit(sub(c,b));theta=math.acos(max(-1,min(1,dot(u,v))))
  assert 1e-7<theta<math.pi-1e-7
  trim=radius*math.tan(theta/2);p= sub(b,mul(u,trim));q=add(b,mul(v,trim))
  normal=unit(sub(v,mul(u,dot(u,v))));center=add(p,mul(normal,radius))
  corners[i]=dict(kind='arc',start=p,end=q,center=center,radial=mul(normal,-1),tangent=u,radius=radius,angle=theta,length=radius*theta,trim=trim)
 segs=[];current=vertices[0]
 for i in range(1,len(vertices)):
  end=corners[i]['start'] if i in corners else vertices[i]
  incoming=unit(sub(vertices[i],vertices[i-1]));gap=dot(sub(end,current),incoming)
  assert gap>1e-6, 'Fillets consume/overlap the available straight segment'
  segs.append(dict(kind='line',start=current,end=end,length=norm(sub(end,current))))
  if i in corners:segs.append(corners[i]);current=corners[i]['end']
 for a,b in zip(segs,segs[1:]):
  assert norm(sub(a['end'],b['start']))<1e-8 and norm(sub(tangent(a,1),tangent(b,0)))<1e-8
 return segs
def slice_path(segs,start,end):
 L=sum(s['length'] for s in segs);assert 0<=start<end<=L+1e-8
 result=[];cursor=0
 for s in segs:
  lo=max(0,(start-cursor)/s['length']);hi=min(1,(end-cursor)/s['length'])
  if hi>lo+1e-12:
   q=s.copy();q['start']=point(s,lo);q['end']=point(s,hi);q['length']=s['length']*(hi-lo)
   if s['kind']=='arc':
    q['radial']=unit(sub(q['start'],s['center']));q['tangent']=tangent(s,lo);q['angle']=s['angle']*(hi-lo)
   result.append(q)
  cursor+=s['length']
 assert abs(sum(s['length'] for s in result)-(end-start))<1e-7
 return result
