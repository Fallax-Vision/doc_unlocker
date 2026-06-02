import io, os, msoffcrypto, openpyxl
wb = openpyxl.Workbook(); ws = wb.active
ws["A1"] = "Android engine test"; ws["A2"] = 2026
xb = io.BytesIO(); wb.save(xb)
enc = io.BytesIO()
msoffcrypto.OfficeFile(io.BytesIO(xb.getvalue())).encrypt("Crack3d!", enc)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture.xlsx")
open(out, "wb").write(enc.getvalue())
print("wrote", out, len(enc.getvalue()), "bytes")
