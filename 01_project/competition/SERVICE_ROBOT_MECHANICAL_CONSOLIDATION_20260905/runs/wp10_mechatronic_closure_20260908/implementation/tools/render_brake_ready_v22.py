"""Render the actual native PDF's READY page for visual inspection."""
from pathlib import Path
import hashlib,json,subprocess,shutil
A=Path(__file__).resolve().parents[1]
from pypdf import PdfReader
p=A/'ecad/wp10_system_v22.pdf';doc=PdfReader(p)
found=[i for i,page in enumerate(doc.pages) if '10.5 V nominal bias READY' in page.extract_text()]
assert len(found)==1,found
out=A/'review/BRAKE_READY_NATIVE_V22.png';exe=shutil.which('pdftoppm');assert exe
command=[exe,'-f',str(found[0]+1),'-l',str(found[0]+1),'-png','-singlefile','-scale-to','1800',str(p),str(out.with_suffix(''))]
subprocess.run(command,check=True,capture_output=True)
(A/'results/BRAKE_READY_RENDER_V22.json').write_text(json.dumps(dict(native_pdf_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),page_index=found[0],page_count=len(doc.pages),image=str(out.relative_to(A)),image_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),command=command,visual_review_pending=True),indent=2),encoding='utf-8')
print(json.dumps(dict(page_index=found[0],page_count=len(doc.pages),image=str(out))))
