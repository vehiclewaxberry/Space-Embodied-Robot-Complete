from pathlib import Path
import pypdfium2 as pdfium
from pypdf import PdfReader
A=Path(__file__).resolve().parents[1]
for filename,pages in [('te_55a0111_drawing.pdf',[0,1]),('chb500w_application.pdf',[4])]:
 p=A/'sources'/filename;r=PdfReader(p);print(filename)
 doc=pdfium.PdfDocument(p)
 for i in pages:
  print(r.pages[i].extract_text()[:2500]);page=doc[i];bitmap=page.render(scale=2);out=A/f'review/{p.stem}_page_{i+1}.png';bitmap.to_pil().save(out);bitmap.close();page.close();print(out)
 doc.close()
