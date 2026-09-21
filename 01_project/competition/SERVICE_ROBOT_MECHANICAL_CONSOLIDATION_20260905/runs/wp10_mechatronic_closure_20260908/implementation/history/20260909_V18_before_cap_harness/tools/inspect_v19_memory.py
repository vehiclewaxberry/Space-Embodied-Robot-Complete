"""Read-only process inventory. Do not output unrelated command-line contents."""
import psutil,json
rows=[]
for p in psutil.process_iter(['pid','ppid','name','memory_info','create_time']):
 try:
  r=p.info;mem=r['memory_info'].rss/2**20
  if mem<25:continue
  cmd=' '.join(p.cmdline()).lower();kind='unclassified'
  for needle,label in [('wp10_mechatronic','WP10_task'),('cad-viewer','CAD_viewer'),('kicad-mcp','KiCad_MCP'),('mcp','MCP_tool')]:
   if needle in cmd:kind=label;break
  rows.append(dict(pid=r['pid'],ppid=r['ppid'],name=r['name'],rss_mib=round(mem,1),kind=kind,created=r['create_time']))
 except (psutil.Error,OSError):pass
print(json.dumps(dict(available_mib=psutil.virtual_memory().available/2**20,top=sorted(rows,key=lambda r:r['rss_mib'],reverse=True)[:35]),indent=2))
