from pathlib import Path
import pypdfium2 as pdf
A=Path(__file__).resolve().parents[1]
for name,pages in [('cincon_chb500w',[1,8,9]),('pmm35',[2]),('mc35',[1,2]),('chb500w_application',[2,3,14])]:
 p=A/'sources'/f'{name}.pdf'
 if not p.exists():continue
 d=pdf.PdfDocument(p)
 for n in pages:
  if n>=len(d):continue
  page=d[n];page.render(scale=1.65).to_pil().save(A/'review'/f'{name}_p{n+1}.png');page.close()
 d.close()
print('source pages rendered')
