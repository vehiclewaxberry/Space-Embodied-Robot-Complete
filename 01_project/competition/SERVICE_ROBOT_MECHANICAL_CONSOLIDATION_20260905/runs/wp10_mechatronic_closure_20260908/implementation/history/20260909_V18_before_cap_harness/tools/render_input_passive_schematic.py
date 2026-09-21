from pathlib import Path
import json
from pypdf import PdfReader
import pypdfium2 as pdfium
A=Path(__file__).resolve().parents[1]
p=A/'ecad/wp10_system.pdf'
reader=PdfReader(p); selected=[]
for i,page in enumerate(reader.pages):
 t=page.extract_text() or ''
 if '1025HC30-RTR' in t or 'ELXG101VSN222MR50S' in t:selected.append(i)
pdf=pdfium.PdfDocument(p)
for i in selected:
 dest=A/'review'/f'input_passive_native_page_{i+1}.png'
 pdf[i].render(scale=1.35).to_pil().save(dest)
print(json.dumps(dict(page_count=len(reader.pages),selected_pages=[i+1 for i in selected])))

