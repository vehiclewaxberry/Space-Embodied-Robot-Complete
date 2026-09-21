from pathlib import Path
import pypdfium2 as pdfium,json,hashlib
A=Path(__file__).resolve().parents[1]
pdf=pdfium.PdfDocument(A/'ecad/wp10_system.pdf')
assert len(pdf)==12,len(pdf)
page=pdf[11];im=page.render(scale=2).to_pil();out=A/'review/ERC_POWER_DECLARATIONS_V16.png';im.save(out)
print(json.dumps({'pages':len(pdf),'image':str(out),'dimensions':im.size}))
