"""Diagnóstico: baixa a planilha LO mais recente e busca o CNPJ manualmente."""
import io
import requests
import openpyxl

CNPJ = "60357147000165"
URL = "https://www.ipaam.am.gov.br/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx"

print(f"Baixando {URL} ...")
resp = requests.get(URL, timeout=30)
print(f"Status HTTP: {resp.status_code} — {len(resp.content)} bytes")

wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

print(f"Total de linhas: {len(rows)}")
print(f"Cabeçalho: {rows[0]}")

encontrado = False
for i, row in enumerate(rows[1:], start=2):
    for cell in row:
        normalizado = "".join(c for c in str(cell) if c.isdigit()).zfill(14) if cell else ""
        if normalizado == CNPJ:
            print(f"\nCNPJ encontrado na linha {i}:")
            print(dict(zip(rows[0], row)))
            encontrado = True
            break

if not encontrado:
    print(f"\nCNPJ {CNPJ} NÃO encontrado na planilha.")
    print("Primeiros 3 CNPJs da planilha para referência:")
    col_cnpj = next((i for i, h in enumerate(rows[0]) if h and "CNPJ" in str(h).upper()), None)
    if col_cnpj is not None:
        for row in rows[1:4]:
            print(" ", row[col_cnpj])
