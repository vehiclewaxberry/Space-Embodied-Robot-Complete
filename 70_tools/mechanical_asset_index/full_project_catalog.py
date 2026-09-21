"""Bounded full-workspace catalog; static parsing only, no business-code execution.

All results and recoverable prior bytes live in the existing catalog database.
The cleanup command is deliberately separate from enumeration and content reading.
"""
from pathlib import Path
from collections import Counter,defaultdict
import os,sys,json,csv,sqlite3,hashlib,datetime,re,ast,zipfile,struct,subprocess,zlib,time
import xml.etree.ElementTree as ET
from functools import lru_cache

ROOT=Path(__file__).resolve().parents[2]
SESSION=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905'
DB=SESSION/'runs/loop0_20260905/screening/full_project_catalog.sqlite'
DOMAINS=['01_project','10_research','20_engineering','30_simulation','40_evidence','50_literature','70_tools','80_third_party']
TEXT_EXT={'.md','.txt','.json','.yaml','.yml','.xml','.urdf','.srdf','.py','.m','.ps1','.bat','.cmd','.c','.h','.cpp','.hpp','.tex','.bib','.csv','.tsv','.log','.ini','.cfg','.toml','.html','.htm','.js','.ts','.css','.sh','.gitignore','.gitattributes','.inp','.apdl','.mac','.dat','.out','.err','.rst','.sql','.r','.ipynb','.sdf','.xacro'}
CODE_EXT={'.py','.m','.ps1','.bat','.cmd','.c','.h','.cpp','.hpp','.js','.ts','.sh','.apdl','.mac'}
RUNTIME_NAMES={'node_modules','site-packages','.venv','venv','runtime','runtime_deps','__pypackages__'}
CACHE_NAMES={'__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','__cadgen__','.cache'}
NATIVE_EXT={'.sldasm','.sldprt','.slddrw','.step','.stp','.stl','.fcstd','.cae','.odb','.sim','.rst','.rdb','.cdb','.wbpj','.db','.msh','.mesh','.glb','.gltf','.vtk','.vtu','.npy','.npz','.mat','.h5','.hdf5'}
SECRET_RE=re.compile(r'(^\.env($|\.)|credential|secret|token|password|auth\.json)',re.I)
ABS_RE=re.compile(r'[A-Za-z]:[\\/][^\r\n\t\"<>|\x00]+')
LINK_RE=re.compile(r'\]\((?:<([^>]+)>|([^\s)]+))\)')
DOMAIN_RE=re.compile(r'(?:01_project|10_research|20_engineering|30_simulation|40_evidence|50_literature|70_tools|80_third_party)[\\/][^\s\"\x27<>`),;\]}]+')


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def relative(p):return p.relative_to(ROOT).as_posix()
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE IF NOT EXISTS entries(path TEXT PRIMARY KEY,parent TEXT,kind TEXT,extension TEXT,size INTEGER,mtime_ns INTEGER,device TEXT,inode TEXT,nlink INTEGER,reparse INTEGER,link_target TEXT,git_scope TEXT,tracked INTEGER,scan_status TEXT,read_status TEXT,domain TEXT,role TEXT,purpose_summary TEXT,configuration TEXT,declared_status TEXT,verified_status TEXT,sha256 TEXT,read_method TEXT,coverage TEXT,unresolved_dependencies TEXT,action TEXT,reason TEXT,confidence TEXT,semantic_review TEXT,post_state TEXT DEFAULT 'PRESENT');
    CREATE TABLE IF NOT EXISTS contents(sha256 TEXT PRIMARY KEY,read_status TEXT,method TEXT,coverage TEXT,summary TEXT,configuration TEXT,declared_status TEXT,semantic_review TEXT);
    CREATE TABLE IF NOT EXISTS refs(id INTEGER PRIMARY KEY,source TEXT,target TEXT,raw TEXT,kind TEXT,line INTEGER,resolution TEXT,UNIQUE(source,target,raw,kind,line));
    CREATE TABLE IF NOT EXISTS archive_members(archive TEXT,member TEXT,size INTEGER,compressed INTEGER,encrypted INTEGER,safe_path INTEGER,content_status TEXT,PRIMARY KEY(archive,member));
    CREATE TABLE IF NOT EXISTS snapshots(path TEXT,stage TEXT,sha256 TEXT,bytes INTEGER,compressed_blob BLOB,created_utc TEXT,PRIMARY KEY(path,stage));
    CREATE TABLE IF NOT EXISTS actions(path TEXT PRIMARY KEY,kind TEXT,target TEXT,basis TEXT,pre_sha256 TEXT,pre_mtime_ns INTEGER,status TEXT,rollback TEXT,bytes INTEGER,executed_utc TEXT,error TEXT);
    CREATE TABLE IF NOT EXISTS dir_review(path TEXT PRIMARY KEY,files INTEGER,bytes INTEGER,processed INTEGER,roles TEXT,entries TEXT,purpose TEXT,mixed INTEGER,action TEXT,reason TEXT);
    CREATE TABLE IF NOT EXISTS reviews(path TEXT,reviewer TEXT,method TEXT,findings TEXT,read_scope TEXT,PRIMARY KEY(path,reviewer));
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at TEXT,kind TEXT,detail TEXT);
    CREATE INDEX IF NOT EXISTS entries_status ON entries(read_status);
    CREATE INDEX IF NOT EXISTS entries_sha ON entries(sha256);
    CREATE INDEX IF NOT EXISTS entries_role ON entries(role);
    ''')
    return c
def meta(c,key,value):c.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',(key,json.dumps(value,ensure_ascii=False)))
def backup(c,path,stage):
    data=path.read_bytes()
    c.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?,?,?)',(relative(path),stage,hashlib.sha256(data).hexdigest(),len(data),zlib.compress(data),now()))
def is_reparse(p):
    s=p.lstat();return bool(getattr(s,'st_file_attributes',0)&0x400) or p.is_symlink()
def classify(path,parts,kind):
    domain=parts[0] if parts and parts[0] in DOMAINS else 'ROOT_OR_NONSTANDARD'
    if '.git' in parts:return domain,'VERSION_STORAGE','ENVIRONMENT_METADATA_ONLY','KEEP_RUNTIME'
    if any(x in RUNTIME_NAMES for x in parts):return domain,'RUNTIME','ENVIRONMENT_METADATA_ONLY','KEEP_RUNTIME'
    if any(x in CACHE_NAMES for x in parts):return domain,'CACHE','CACHE_ROLE_IDENTIFIED_CONTENT_NOT_REVIEWED','HOLD_UNRESOLVED'
    if parts and parts[0] in {'.claude','.codex','.agents','.playwright-cli'}:return domain,'AGENT_CONFIGURATION','NOT_YET_READ','KEEP_CURRENT'
    if '80_third_party' in parts:return domain,'THIRD_PARTY','NOT_YET_READ','KEEP_EXTERNAL_SOURCE'
    if any(x in path.lower() for x in ('fail','negative','falsif','path30','r1_findings')):return domain,'FAILED_COUNTEREXAMPLE','NOT_YET_READ','KEEP_FROZEN_EVIDENCE'
    if any(x in parts for x in ('results','artifacts','archive','_archive')):return domain,'FROZEN_EVIDENCE','NOT_YET_READ','KEEP_FROZEN_EVIDENCE'
    if kind=='directory':return domain,'DIRECTORY','DIRECTORY_CONTENTS_REGISTERED','KEEP_CURRENT'
    if Path(path).suffix.lower() in CODE_EXT:return domain,'SOURCE_CODE','NOT_YET_READ','KEEP_CURRENT'
    return domain,'BUSINESS_DOCUMENT_OR_DATA','NOT_YET_READ','HOLD_UNRESOLVED'


def enumerate_all(c):
    if c.execute("SELECT value FROM meta WHERE key='enumeration_complete'").fetchone():
        print('Enumeration snapshot reused; parsing resumes from saved statuses.',flush=True);return
    assert ROOT.resolve()==Path('F:/China Graduate Future Flight Vehicle Innovation Competition').resolve()
    cutoff=now();meta(c,'snapshot_cutoff_utc',cutoff);meta(c,'root',str(ROOT));meta(c,'authority','Latest direct user request authorizes actual redundant-file cleanup; attached read-only plan treated as guidance, not an overriding restriction.')
    for p in [SESSION/x for x in ['CURRENT_candidate.md','issues.json','dependency_manifest.json','run_manifest.json']]:backup(c,p,'BEFORE_FULL_PROJECT_CONSOLIDATION')
    parent=[]
    for p in ROOT.parent.iterdir():
        try:parent.append({'name':p.name,'kind':'directory' if p.is_dir() else 'file','reparse':is_reparse(p)})
        except OSError as e:parent.append({'name':p.name,'error':type(e).__name__})
    meta(c,'parent_F_one_level_metadata',parent)
    tracked=set()
    try:
        r=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,timeout=30)
        if r.returncode:raise RuntimeError('git ls-files failed: ownership unknown')
        tracked={x.decode('utf-8','replace').replace('\\','/') for x in r.stdout.split(b'\0') if x}
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=10).stdout.strip()
        meta(c,'git_head_at_cutoff',head)
    except Exception as e:
        meta(c,'git_metadata_error',str(e));c.commit()
        raise RuntimeError('Enumeration stopped: Git ownership could not be established') from e
    count=0;errors=[];stack=[ROOT];nested=[]
    while stack:
        folder=stack.pop()
        try:items=list(os.scandir(folder))
        except OSError as e:
            errors.append({'path':str(folder),'error':str(e)});continue
        for item in items:
            p=Path(item.path);rel=relative(p)
            try:
                st=p.lstat();reparse=is_reparse(p);kind='directory' if item.is_dir(follow_symlinks=False) else 'file'
                target=os.readlink(p) if reparse else None
                domain,role,status,action=classify(rel,p.relative_to(ROOT).parts,kind)
                if reparse:status='LINK_NOT_FOLLOWED';role='EXTERNAL_OR_LINKED_PATH';action='HOLD_UNRESOLVED'
                if rel==relative(DB) or rel.startswith(relative(DB)+'-'):role='OUTPUT_OF_THIS_REVIEW';status='OUTPUT_OF_THIS_REVIEW'
                scope='ROOT_GIT'
                if p.name=='.git' and p.parent!=ROOT:nested.append(relative(p.parent))
                c.execute('INSERT OR REPLACE INTO entries(path,parent,kind,extension,size,mtime_ns,device,inode,nlink,reparse,link_target,git_scope,tracked,scan_status,read_status,domain,role,verified_status,action,confidence,semantic_review) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (rel,relative(p.parent) if p.parent!=ROOT else '',kind,p.suffix.lower(),st.st_size if kind=='file' else 0,st.st_mtime_ns,str(st.st_dev),str(st.st_ino),st.st_nlink,int(reparse),target,scope,int(rel in tracked),'REGISTERED',status,domain,role,'NOT_DOMAIN_VALIDATED',action,'TYPE_AND_PATH_ONLY','NOT_HUMAN_REVIEWED'))
                if kind=='directory' and not reparse:stack.append(p)
            except OSError as e:
                c.execute('INSERT OR REPLACE INTO entries(path,parent,kind,scan_status,read_status,reason,action) VALUES(?,?,?,?,?,?,?)',(rel,relative(p.parent) if p.parent!=ROOT else '','unknown','READ_ERROR','PERMISSION_DENIED',str(e),'HOLD_UNRESOLVED'))
            count+=1
            if count%5000==0:c.commit();print('Enumerated',count,'paths',flush=True)
    meta(c,'enumeration_errors',errors);meta(c,'nested_repositories',nested)
    for boundary in sorted(nested,key=len):c.execute('UPDATE entries SET git_scope=? WHERE path=? OR path LIKE ?',(boundary,boundary,boundary+'/%'))
    meta(c,'enumeration_complete',{'at':now(),'registered_paths':count});c.commit();print('Enumeration complete',count,flush=True)


def clean_summary(s):
    s=re.sub(r'(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+',r'\1=[SUPPRESSED]',s)
    return s.strip()[:600]
@lru_cache(maxsize=100000)
def reference_resolution(target):
    normalized=os.path.normcase(os.path.abspath(target))
    root_normal=os.path.normcase(str(ROOT))
    if normalized!=root_normal and not normalized.startswith(root_normal+os.sep):
        return 'EXTERNAL_REFERENCE_RECORDED_NOT_TRAVERSED'
    return 'EXISTS_TEXT_REFERENCE_NOT_PROOF_OF_ACTIVITY' if os.path.exists(target) else 'MISSING_OR_RELATIVE_BASE_UNRESOLVED'
def add_ref(c,source,raw,kind,line):
    raw=raw.strip().strip('`<>"\'').replace('\\\\','\\')
    if not raw or len(raw)>1400:return
    if raw.startswith(('http:','https:','mailto:','data:','#')):return
    from urllib.parse import unquote
    value=unquote(raw.split('#')[0]).replace('\\','/')
    if any(x in value for x in ('$','{','}','*','<','>')):target=value;resolution='DYNAMIC_OR_PATTERN_UNRESOLVED'
    else:
        p=Path(value)
        if not p.is_absolute():
            p=ROOT/p if value.split('/')[0] in DOMAINS else (ROOT/source).parent/p
        target=os.path.abspath(os.path.normpath(str(p)))
        resolution=reference_resolution(target)
    c.execute('INSERT OR IGNORE INTO refs(source,target,raw,kind,line,resolution) VALUES(?,?,?,?,?,?)',(source,target,clean_summary(raw),kind,line,resolution))


def process_text(c,path,row):
    chunks=[];h=hashlib.sha256();total=0
    with path.open('rb') as f:
        while data:=f.read(1024*1024):h.update(data);total+=len(data);chunks.append(data)
    data=b''.join(chunks);identity=h.hexdigest()
    previous=c.execute('SELECT * FROM contents WHERE sha256=?',(identity,)).fetchone()
    encoding='utf-8-sig'
    try:text=data.decode(encoding)
    except UnicodeDecodeError:
        if data[:2] in (b'\xff\xfe',b'\xfe\xff'):encoding='utf-16';text=data.decode(encoding)
        else:
            try:encoding='gb18030';text=data.decode(encoding)
            except UnicodeDecodeError:return identity,'PARTIALLY_READ','UNDECODABLE_TEXT_BYTES',{'bytes_hashed':total,'text_decoded':False},'编码未能可靠解码',None,None
    if '\x00' in text[:4096]:return identity,'NATIVE_CONTENT_NOT_READ','BINARY_HEADER',{'bytes_hashed':total},'后缀为文本但包含二进制字节',None,None
    summary='';declared=[];cfg=[];dep_count=0
    for line_no,line in enumerate(text.splitlines(),1):
        stripped=line.strip()
        if not summary and stripped and not stripped.startswith(('<!--','#!/','<?xml','{','[','---')):summary=stripped
        if any(k in line for k in ('verdict','CURRENT','status','STATUS','configuration','schema:')) and len(declared)<8:declared.append(clean_summary(stripped))
        for x in re.findall(r'\b(?:WP\d{2}[A-Z0-9_]*|F\dR\d[A-Z0-9_]*|sim_\d+|e\d{2}_[A-Za-z0-9_]+)\b',line):
            if x not in cfg and len(cfg)<12:cfg.append(x)
        if dep_count<5000:
            found=[]
            for m in LINK_RE.finditer(line):found.append((m.group(1) or m.group(2),'MARKDOWN_NAVIGATION'))
            found += [(x,'DOMAIN_PATH_TEXT') for x in DOMAIN_RE.findall(line)]
            found += [(x,'ABSOLUTE_PATH_TEXT') for x in ABS_RE.findall(line)]
            for raw,kind in found:add_ref(c,row['path'],raw,kind,line_no);dep_count+=1
    method='FULL_TEXT_DECODE_AND_STATIC_PATH_EXTRACTION';coverage={'bytes':total,'lines':len(text.splitlines()),'encoding':encoding,'model_semantic_review':False,'dependency_matches':dep_count,'dependency_extract_limit':5000}
    status='FULL_TEXT_READ'
    if row['extension']=='.py':
        try:
            tree=ast.parse(text)
            doc=ast.get_docstring(tree)
            if doc:summary=doc.splitlines()[0]
            for node in ast.walk(tree):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or '']
                    for name in names:
                        module=(path.parent/name.replace('.','/')).with_suffix('.py')
                        if module.exists():add_ref(c,row['path'],str(module),'PYTHON_IMPORT_LOCAL',node.lineno)
                        else:c.execute('INSERT OR IGNORE INTO refs(source,target,raw,kind,line,resolution) VALUES(?,?,?,?,?,?)',(row['path'],name,name,'PYTHON_IMPORT_MODULE',node.lineno,'ENVIRONMENT_OR_DYNAMIC_IMPORT_UNRESOLVED'))
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {'unlink','rmdir','write_text','write_bytes','replace','rename'}:coverage.setdefault('write_side_effect_calls',[]).append({'line':node.lineno,'method':node.func.attr})
            method='FULL_TEXT_AND_PYTHON_AST_STATIC_ANALYSIS';status='STRUCTURED_CONTENT_READ'
        except (SyntaxError,ValueError) as e:coverage['parse_error']=str(e);coverage['syntax_language_version_not_assumed']=True
    elif row['extension']=='.json' and total<32*1024*1024:
        try:
            obj=json.loads(text);method='FULL_JSON_PARSE_AND_PATH_EXTRACTION';status='STRUCTURED_CONTENT_READ'
            coverage['root_type']=type(obj).__name__
            if isinstance(obj,dict):
                coverage['top_level_keys']=list(obj)[:80]
                declared=[clean_summary(str(obj[k])) for k in ('schema','status','verdict','configuration') if k in obj]
                summary=next((str(obj[k]) for k in ('purpose','description','scope','schema','status') if k in obj),summary)
        except (ValueError,RecursionError) as e:coverage['parse_error']=str(e)
    elif row['extension'] in {'.xml','.urdf','.srdf','.sdf','.xacro'}:
        try:
            tree=ET.fromstring(text);method='FULL_XML_PARSE';status='STRUCTURED_CONTENT_READ';coverage['xml_root']=tree.tag
            for node in tree.iter():
                for key in ('filename','file','href'):
                    if key in node.attrib:add_ref(c,row['path'],node.attrib[key],'XML_OR_MESH_REFERENCE',0)
        except ET.ParseError as e:coverage['parse_error']=str(e)
    elif row['extension'] in {'.csv','.tsv'}:
        try:
            rows=csv.reader(text.splitlines(),delimiter='\t' if row['extension']=='.tsv' else ',');first=next(rows,[]);count=1+sum(1 for _ in rows)
            method='FULL_DELIMITED_TABLE_PARSE';status='STRUCTURED_CONTENT_READ';coverage.update({'rows':count,'columns':first[:60]});summary='表格字段：'+', '.join(first[:8])
        except csv.Error as e:coverage['parse_error']=str(e)
    summary=clean_summary(summary or path.name)
    c.execute('INSERT OR IGNORE INTO contents VALUES(?,?,?,?,?,?,?,?)',(identity,status,method,json.dumps(coverage,ensure_ascii=False),summary,json.dumps(cfg),json.dumps(declared,ensure_ascii=False),'AUTOMATED_CONTENT_EXTRACTION_NOT_FULL_EXPERT_REVIEW'))
    if previous:
        coverage['same_bytes_first_parse_reused']=True;coverage['per_path_references_still_extracted']=True;status='SAME_BYTES_CONTENT_REUSED'
    return identity,status,method,coverage,summary,json.dumps(cfg),json.dumps(declared,ensure_ascii=False)


def process_zip(c,path,row):
    coverage={'members_listed':0,'xml_members_read':0,'images_not_visually_reviewed':0,'errors':[]};texts=[]
    office=row['extension'] in {'.docx','.xlsx','.pptx'}
    with zipfile.ZipFile(path) as z:
        for m in z.infolist():
            safe=not(Path(m.filename).is_absolute() or '..' in Path(m.filename).parts or re.match(r'^[A-Za-z]:',m.filename))
            encrypted=bool(m.flag_bits&1);member_status='ARCHIVE_MEMBER_LISTED_ONLY'
            if office and safe and not encrypted and m.filename.endswith('.xml') and m.file_size<20*1024*1024 and m.file_size/max(m.compress_size,1)<1000:
                try:
                    tree=ET.fromstring(z.read(m));coverage['xml_members_read']+=1;member_status='STRUCTURED_XML_CONTENT_READ'
                    for node in tree.iter():
                        if node.tag.rsplit('}',1)[-1] in {'t','v'} and node.text:texts.append(node.text)
                except Exception as e:coverage['errors'].append(type(e).__name__)
            if '/media/' in m.filename:coverage['images_not_visually_reviewed']+=1
            c.execute('INSERT OR REPLACE INTO archive_members VALUES(?,?,?,?,?,?,?)',(row['path'],m.filename,m.file_size,m.compress_size,int(encrypted),int(safe),member_status));coverage['members_listed']+=1
    coverage['visual_layout_reviewed']=False
    if office:return digest(path),'STRUCTURED_CONTENT_READ','OOXML_FULL_XML_TEXT_AND_MEMBER_STRUCTURE',coverage,clean_summary(' '.join(texts[:5])),None,None
    return digest(path),'ARCHIVE_MEMBER_LISTED_ONLY','ZIP_CENTRAL_DIRECTORY_ONLY',coverage,'压缩包成员已登记，未把成员清单当成全文阅读',None,None


def pdf_child(path):
    from pypdf import PdfReader
    r=PdfReader(path);chars=0;empty=[];heads=[]
    for i,p in enumerate(r.pages):
        t=p.extract_text() or '';chars+=len(t)
        if len(t.strip())<20:empty.append(i+1)
        if len(heads)<3:heads.extend(x for x in t.splitlines() if x.strip())
    print(json.dumps({'pages':len(r.pages),'text_characters':chars,'image_review_needed_pages':empty,'all_figures_and_layout_unreviewed':True,'head':clean_summary(' '.join(heads[:3]))},ensure_ascii=False))


def process_files(c):
    total=c.execute("SELECT count(*) FROM entries WHERE kind='file' AND read_status='NOT_YET_READ'").fetchone()[0]
    done=0
    while True:
        rows=c.execute("SELECT * FROM entries WHERE kind='file' AND read_status='NOT_YET_READ' ORDER BY CASE WHEN parent='' THEN 0 ELSE 1 END,path LIMIT 100").fetchall()
        if not rows:break
        for row in rows:
            p=ROOT/row['path'];identity=None;cfg=None;declared=None
            try:
                before=p.stat()
                if SECRET_RE.search(p.name) or p.name=='.mcp.json':
                    data=p.read_bytes();identity=hashlib.sha256(data).hexdigest();coverage={'bytes_read':len(data),'values_suppressed':True}
                    try:obj=json.loads(data.decode('utf-8-sig'));coverage['root_keys']=list(obj) if isinstance(obj,dict) else type(obj).__name__
                    except Exception:pass
                    status='SECRET_CONTENT_SUPPRESSED';method='SENSITIVE_STRUCTURE_ONLY';summary='敏感配置结构已登记，内容值未写入报告'
                elif row['extension'] in TEXT_EXT or p.name in {'.gitignore','.gitattributes','LICENSE','NOTICE','Makefile','Dockerfile'}:
                    if before.st_size>64*1024*1024:
                        identity=digest(p);status='PARTIALLY_READ';method='LARGE_TEXT_IDENTITY_ONLY';coverage={'text_not_loaded_due_to_current_memory':True,'bytes_hashed':before.st_size};summary='大文本待流式专项解析，未称全文审阅'
                    else:identity,status,method,coverage,summary,cfg,declared=process_text(c,p,row)
                elif row['extension'] in {'.zip','.docx','.xlsx','.pptx','.fcstd'}:identity,status,method,coverage,summary,cfg,declared=process_zip(c,p,row)
                elif row['extension']=='.pdf':
                    identity=digest(p)
                    prev=c.execute('SELECT * FROM contents WHERE sha256=?',(identity,)).fetchone()
                    if prev:status='SAME_BYTES_CONTENT_REUSED';method=prev['method'];coverage=json.loads(prev['coverage']);summary=prev['summary']
                    else:
                        r=subprocess.run([sys.executable,str(Path(__file__)),'--pdf-child',str(p)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=35)
                        if r.returncode!=0:raise ValueError('PDF_PARSE_FAILED: '+r.stderr[-250:])
                        coverage=json.loads(r.stdout);summary=coverage.pop('head');status='STRUCTURED_CONTENT_READ';method='ALL_PDF_PAGES_TEXT_EXTRACTED_VISUALS_UNREVIEWED'
                        c.execute('INSERT OR IGNORE INTO contents VALUES(?,?,?,?,?,?,?,?)',(identity,status,method,json.dumps(coverage),summary,None,None,'TEXT_EXTRACTION_ONLY_FIGURES_NOT_REVIEWED'))
                else:
                    with p.open('rb') as f:head=f.read(65536)
                    coverage={'header_bytes':len(head),'native_references_not_verified':True};status='NATIVE_CONTENT_NOT_READ';method='HEADER_ONLY_IDENTITY_PENDING';summary='二进制文件头；SHA身份待补，原生内容未验证'
                    if row['extension'] in {'.step','.stp'}:
                        t=head.decode('ascii','replace');coverage.update({'iso_10303_21':t.startswith('ISO-10303-21'),'header_contains_file_schema':'FILE_SCHEMA' in t});status='CAD_REFERENCE_METADATA_READ';summary='STEP头信息；未加载BRep或解析全部外参'
                    elif row['extension']=='.stl':
                        if len(head)>=84:
                            n=int.from_bytes(head[80:84],'little');coverage.update({'possible_binary_triangle_count':n,'binary_length_matches':84+50*n==before.st_size})
                        status='CAD_REFERENCE_METADATA_READ';summary='STL头/长度校核；未几何重验'
                    elif row['extension']=='.glb' and len(head)>=12:coverage['glb_magic_matches']=head[:4]==b'glTF';status='CAD_REFERENCE_METADATA_READ'
                    elif row['extension'] not in NATIVE_EXT and row['extension'] not in {'.png','.jpg','.jpeg','.gif','.mp4','.webm','.avi','.ico','.dll','.pyd','.exe','.whl'}:status='UNSUPPORTED_FORMAT'
                after=p.stat()
                if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):status='CHANGED_DURING_READ';coverage['concurrent_change']=True
                c.execute('UPDATE entries SET read_status=?,sha256=?,read_method=?,coverage=?,purpose_summary=?,configuration=?,declared_status=?,verified_status=?,semantic_review=?,confidence=?,unresolved_dependencies=? WHERE path=?',
                    (status,identity,method,json.dumps(coverage,ensure_ascii=False),summary,cfg,declared,'CONTENT_HANDLING_ONLY_NO_DOMAIN_PASS','AUTOMATED_EXTRACTION; expert review separately recorded','READ_METHOD_EXPLICIT','Static path extraction is not complete dynamic/native dependency closure.',row['path']))
            except subprocess.TimeoutExpired:
                c.execute('UPDATE entries SET read_status=?,read_method=?,reason=? WHERE path=?',('PARTIALLY_READ','PDF_TEXT_EXTRACTION_TIMEOUT','35-second isolated parse ended; pages/figures not credited complete.',row['path']))
            except Exception as e:
                failure_status='PERMISSION_DENIED' if isinstance(e,PermissionError) else 'CHANGED_DURING_READ' if isinstance(e,FileNotFoundError) else 'PARTIALLY_READ'
                c.execute('UPDATE entries SET read_status=?,reason=? WHERE path=?',(failure_status,str(e)[:700],row['path']))
            done+=1
            # Release the writer between files; a PDF batch can otherwise hold it
            # for minutes and prevent navigation snapshots from being saved.
            c.commit()
            if done%100==0:print('Content handled',done,'/',total,flush=True)
        c.commit()
    meta(c,'content_pass_finished_utc',now());c.commit()


def finalize(c):
    dirs={r['path']:{'files':0,'bytes':0,'processed':0,'roles':Counter(),'entries':[]} for r in c.execute("SELECT path FROM entries WHERE kind='directory'")};dirs['']={'files':0,'bytes':0,'processed':0,'roles':Counter(),'entries':[]}
    for row in c.execute("SELECT * FROM entries WHERE kind='file'"):
        ancestors=['']+['/'.join(row['path'].split('/')[:i]) for i in range(1,len(row['path'].split('/')))]
        for parent in ancestors:
            if parent not in dirs:continue
            d=dirs[parent];d['files']+=1;d['bytes']+=row['size'] or 0;d['processed']+=row['read_status']!='NOT_YET_READ';d['roles'][row['role']]+=1
        if row['parent'] in dirs and Path(row['path']).name.lower().startswith(('readme','current','start_here','project_map')):dirs[row['parent']]['entries'].append(row['path'])
    for path,d in dirs.items():
        roles=dict(d['roles']);mixed=bool('CACHE' in roles and any(x in roles for x in ['SOURCE_CODE','BUSINESS_DOCUMENT_OR_DATA','FROZEN_EVIDENCE']))
        c.execute('INSERT OR REPLACE INTO dir_review VALUES(?,?,?,?,?,?,?,?,?,?)',(path,d['files'],d['bytes'],d['processed'],json.dumps(roles),json.dumps(d['entries']),'; '.join(roles) or '空目录，需按用途判断',int(mixed),'KEEP_PATH_AND_CONSOLIDATE_NAVIGATION','Mixed generated/source content' if mixed else 'Path role registered; no automatic migration'))
    # Fill purpose/coverage for intentionally metadata-only classes without claiming content review.
    c.execute("UPDATE entries SET purpose_summary=COALESCE(purpose_summary,role || ': ' || path),read_method=COALESCE(read_method,'TYPE_PATH_METADATA'),coverage=COALESCE(coverage,'{\"content_reviewed\":false}'),reason=COALESCE(reason,'Classification is not authorization to delete.')")
    stats={'at':now(),'root_entries':c.execute("SELECT count(*) FROM entries WHERE parent='' ").fetchone()[0],
           'files':c.execute("SELECT count(*) FROM entries WHERE kind='file'").fetchone()[0],
           'directories':c.execute("SELECT count(*) FROM entries WHERE kind='directory'").fetchone()[0],
           'logical_bytes':c.execute("SELECT sum(size) FROM entries WHERE kind='file'").fetchone()[0],
           'independent_file_identities':c.execute("SELECT count(*) FROM (SELECT DISTINCT device,inode FROM entries WHERE kind='file')").fetchone()[0],
           'read_status_counts':dict(c.execute("SELECT read_status,count(*) FROM entries WHERE kind='file' GROUP BY read_status")),
           'resolved_or_unresolved_text_reference_edges':c.execute('SELECT count(*) FROM refs').fetchone()[0],
           'archive_members':c.execute('SELECT count(*) FROM archive_members').fetchone()[0],
           'exact_duplicate_groups_hashed_content':c.execute('SELECT count(*) FROM (SELECT sha256 FROM entries WHERE sha256 IS NOT NULL AND size>0 GROUP BY sha256 HAVING count(*)>1)').fetchone()[0]}
    meta(c,'summary',stats);c.commit();print(json.dumps(stats,ensure_ascii=False,indent=2),flush=True)


def main():
    if '--pdf-child' in sys.argv:pdf_child(sys.argv[sys.argv.index('--pdf-child')+1]);return
    c=connect()
    if '--summary' in sys.argv:
        print(c.execute("SELECT value FROM meta WHERE key='summary'").fetchone()[0]);return
    enumerate_all(c)
    if '--enumerate-only' not in sys.argv:process_files(c)
    finalize(c);c.close()


if __name__=='__main__':main()
