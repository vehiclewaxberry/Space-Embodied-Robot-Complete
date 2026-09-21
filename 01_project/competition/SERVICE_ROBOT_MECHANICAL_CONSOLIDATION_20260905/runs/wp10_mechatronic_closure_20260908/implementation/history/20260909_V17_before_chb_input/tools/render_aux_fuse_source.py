from pathlib import Path
import pypdfium2 as pdfium
from pypdf import PdfReader
A=Path(__file__).resolve().parents[1];p=A/'sources/eaton_mda_2025.pdf'
r=PdfReader(p);print(r.pages[0].extract_text()[:160])
for index in [1,2,3,5]:
 print(r.pages[index].extract_text())
doc=pdfium.PdfDocument(p)
for index in [1,2,3,5]:
 page=doc[index];bitmap=page.render(scale=2);out=A/f'review/eaton_mda_2025_page_{index+1}.png';bitmap.to_pil().save(out);print(out);bitmap.close();page.close()
doc.close()
