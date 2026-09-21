from pathlib import Path
import sys,json
def main(sw,types,job):
 def v(o,n,*a):
  q=getattr(o,n);return q(*a) if callable(q) else q
 d={'revision':v(sw,'RevisionNumber'),'docs':v(sw,'GetDocumentCount'),'preferences':{}}
 for n in [24,25,26]:d['preferences'][str(n)]=sw.GetUserPreferenceStringValue(n)
 for n in [291,691]:d['preferences'][str(n)]=sw.GetUserPreferenceToggle(n)
 a=v(sw,'ActiveDoc')
 if a:d['active']={'title':v(a,'GetTitle'),'path':v(a,'GetPathName'),'type':v(a,'GetType')}
 return d

