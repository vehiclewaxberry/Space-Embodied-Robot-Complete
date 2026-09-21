from pathlib import Path
import os,subprocess,json,shutil,hashlib,sys
N=Path(__file__).resolve().parents[1];E=N/'ecad';rt=N.parents[4]/'70_tools/runtime_wp09_kicad/portable'
# Project root is six ancestors above this run.
rt=next(p/'70_tools/runtime_wp09_kicad/portable' for p in N.parents if (p/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe').exists())
cli=rt/'bin/kicad-cli.exe';cfg=E/'runtime_config';cfg.mkdir(exist_ok=True);env=os.environ.copy();env.update(KICAD_CONFIG_HOME=str(cfg),KICAD10_SYMBOL_DIR=str(rt/'share/kicad/symbols'),KICAD10_FOOTPRINT_DIR=str(rt/'share/kicad/footprints'))
up=E/'upstream_review';up.mkdir(exist_ok=True);src=N/'sources/oresat-flatsat/flatsat-breakout'
for p in src.iterdir():
 if p.is_file() and p.suffix in ['.kicad_sch','.kicad_pcb','.kicad_pro'] and not (up/p.name).exists():shutil.copy2(p,up/p.name)
(up/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Connector_Generic") (type "KiCad") (uri "${KICAD10_SYMBOL_DIR}/Connector_Generic.kicad_sym") (options "") (descr "")) (lib (name "power") (type "KiCad") (uri "${KICAD10_SYMBOL_DIR}/power.kicad_sym") (options "") (descr "")))')
libs=['Connector_IDC','Connector_PinHeader_2.54mm','MountingHole'];s='(fp_lib_table (version 7) '+''.join(f'(lib (name "{x}") (type "KiCad") (uri "${{KICAD10_FOOTPRINT_DIR}}/{x}.pretty") (options "") (descr ""))' for x in libs)
s+=f'(lib (name "oresat-connectors") (type "KiCad") (uri "{(N/"sources/oresat-kicad/oresat-footprints/oresat-connectors.pretty").as_posix()}") (options "") (descr "locked source")))';(up/'fp-lib-table').write_text(s)
v=E/'exports';v.mkdir(exist_ok=True);receipts=[]
def run(args,key):
 p=subprocess.run([str(cli),*map(str,args)],env=env,encoding='utf8',errors='replace',capture_output=True,timeout=90)
 (N/'logs'/('kicad_'+key+'.stdout.log')).write_text(p.stdout,encoding='utf8');(N/'logs'/('kicad_'+key+'.stderr.log')).write_text(p.stderr,encoding='utf8')
 receipts.append(dict(key=key,args=list(map(str,args)),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(key,p.returncode,flush=True)
run(['version'],'version')
for folder,name in [(E,'wp09_system'),(E,'rs422_gse_splice'),(up,'flatsat-breakout-main')]:
 inp=folder/(name+'.kicad_sch')
 run(['sch','export','netlist','--format','kicadxml','-o',v/(name+'.xml'),inp],name+'_netlist')
 run(['sch','erc','--format','json','--severity-all','--exit-code-violations','-o',v/(name+'_erc.json'),inp],name+'_erc')
 svgdir=v/(name+'_schematic');svgdir.mkdir(exist_ok=True)
 run(['sch','export','svg','-o',svgdir,inp],name+'_svg')
 if name!='wp09_system':
  run(['pcb','drc','--format','json','--severity-all','--schematic-parity','--exit-code-violations','-o',v/(name+'_drc.json'),folder/(name+'.kicad_pcb')],name+'_drc')
  boarddir=v/(name+'_pcb');boarddir.mkdir(exist_ok=True)
  run(['pcb','export','svg','--layers','F.Cu,F.SilkS,Edge.Cuts','--page-size-mode','2','-o',boarddir/(name+'.svg'),folder/(name+'.kicad_pcb')],name+'_pcb_svg')
(N/'results/KICAD_RUN.json').write_text(json.dumps(dict(cli=str(cli),cli_sha256=hashlib.sha256(cli.read_bytes()).hexdigest(),version=receipts[0]['stdout'].strip(),commands=receipts,global_install=False,runtime_config_isolated=True,manufacturing_exports_generated=False),indent=2),encoding='utf8')
