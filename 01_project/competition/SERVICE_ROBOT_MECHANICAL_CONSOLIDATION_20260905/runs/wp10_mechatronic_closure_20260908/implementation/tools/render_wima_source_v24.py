from pathlib import Path
import subprocess
A=Path(__file__).resolve().parents[1]
subprocess.run(['pdftoppm','-f','2','-singlefile','-scale-to','1800','-png',
 str(A/'sources/wima_mkp2_v24.pdf'),str(A/'review/WIMA_MKP2_DIMENSIONS_V24')],check=True)
print('Rendered OEM PDF page2')
