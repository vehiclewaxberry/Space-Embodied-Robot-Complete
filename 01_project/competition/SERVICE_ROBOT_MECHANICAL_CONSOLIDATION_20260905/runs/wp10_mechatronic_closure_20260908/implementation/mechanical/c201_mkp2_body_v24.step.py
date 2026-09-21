"""Nominal WIMA catalog envelope; pin1 frame coincides with the KiCad footprint."""
from build123d import Box,Cylinder,Pos,Compound,Color,Align
def gen_step():
 body=Pos(2.5,0,8)*Box(7.2,11,16)
 body.label='C201_WIMA_MKP2_catalog_body_nominal';body.color=Color(0.72,0.035,0.035)
 leads=[]
 for pin,x in [(1,0),(2,5)]:
  lead=Pos(x,0,-6)*Cylinder(.25,6,align=(Align.CENTER,Align.CENTER,Align.MIN))
  lead.label='C201_pin_'+str(pin)+'_nominal';lead.color=Color(.65,.65,.68);leads.append(lead)
 return Compound(label='C201_MKP2C041001N00JSSD_nominal_not_OEM_internal',children=[body,*leads])

