from pathlib import Path
import pypdfium2 as pdfium
from pypdf import PdfReader
A=Path(__file__).resolve().parents[1];p=A/'sources/eaton_1025hc_2025.pdf'
reader=PdfReader(p);print(reader.pages[0].extract_text()[:350])
doc=pdfium.PdfDocument(p)
for index in [1,2]:
 page=doc[index];bitmap=page.render(scale=2.4);image=bitmap.to_pil();out=A/f'review/eaton_1025hc_2025_page_{index+1}.png';image.save(out);print(str(out));bitmap.close();page.close()
doc.close()
