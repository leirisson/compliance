"""Mapeia todas as colunas do cabeçalho real (linha 2) da planilha LO."""
import io
import requests
import openpyxl

URL = "https://www.ipaam.am.gov.br/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx"

resp = requests.get(URL, timeout=30)
wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

header = rows[1]  # linha 2 = índice 1
print("=== Colunas (linha 2) ===")
for i, col in enumerate(header):
    if col is not None:
        print(f"  [{i:02d}] {col}")

print("\n=== Última linha (para ver coluna de validade) ===")
last = [r for r in rows if any(v is not None for v in r)][-1]
for i, val in enumerate(last):
    if val is not None and i < len(header) and header[i] is not None:
        print(f"  [{i:02d}] {header[i]}: {val}")
