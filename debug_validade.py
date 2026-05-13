"""Verifica o valor exato da coluna VALIDADE e testa _resolve_expiry."""
import io, requests, openpyxl
from datetime import datetime

URL = "https://www.ipaam.am.gov.br/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx"
resp = requests.get(URL, timeout=30)
wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
rows = list(wb.active.iter_rows(values_only=True))

# linha 3 = índice 2 = Saint-Gobain
row = rows[2]
validade_raw = row[11]
emissao_raw = row[10]

print("validade repr:", repr(validade_raw))
print("emissao repr: ", repr(emissao_raw))
print("validade bytes:", validade_raw.encode("utf-8") if isinstance(validade_raw, str) else "não é str")

# Testa o _resolve_expiry diretamente
import sys; sys.path.insert(0, ".")
from scrapers.ipaam import _resolve_expiry
resultado = _resolve_expiry(str(validade_raw), emissao_raw)
print("expiry calculado:", resultado)
