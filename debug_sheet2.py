"""Inspeciona as primeiras linhas da planilha LO para mapear a estrutura real."""
import io
import requests
import openpyxl

URL = "https://www.ipaam.am.gov.br/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx"

resp = requests.get(URL, timeout=30)
wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))

print("=== Linhas 1 a 5 (estrutura) ===")
for i, row in enumerate(rows[:5], start=1):
    valores = [v for v in row if v is not None]
    print(f"Linha {i}: {valores[:10]}")  # primeiros 10 campos não-nulos
