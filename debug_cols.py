"""Verifica detecção de colunas e busca direta pelo CNPJ da Saint-Gobain."""
import io, requests, openpyxl

CNPJ_RAW = "61.064.838/0097-85"
CNPJ_NORM = "61064838009785"
URL = "https://www.ipaam.am.gov.br/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx"

resp = requests.get(URL, timeout=30)
wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
rows = list(wb.active.iter_rows(values_only=True))

header = [str(c).strip() if c else "" for c in rows[1]]
header_upper = [h.upper() for h in header]

print("=== Detecção de colunas ===")
for i, h in enumerate(header_upper):
    if h:
        print(f"  [{i:02d}] '{h}'")

cnpj_col = next((i for i, h in enumerate(header_upper) if "CNPJ" in h), None)
validade_col = next((i for i, h in enumerate(header_upper) if "VALIDADE" in h), None)
emissao_col = next((i for i, h in enumerate(header_upper) if "RECEBIMENTO" in h or "EMISS" in h), None)
numero_col = next((i for i, h in enumerate(header_upper) if "MERO DA LICEN" in h or ("LICEN" in h and h[:1] == "N")), None)

print(f"\ncnpj_col={cnpj_col}, numero_col={numero_col}, validade_col={validade_col}, emissao_col={emissao_col}")

print("\n=== Buscando CNPJ ===")
for i, row in enumerate(rows[2:], start=3):
    if not row[cnpj_col]:
        continue
    cell = str(row[cnpj_col]).strip()
    norm = "".join(c for c in cell if c.isdigit()).zfill(14)
    if norm == CNPJ_NORM:
        print(f"Linha {i}: {dict(zip(header, row))}")
        break
else:
    print(f"CNPJ {CNPJ_NORM} não encontrado.")
    print("Amostra de valores na coluna CNPJ:")
    for row in rows[2:5]:
        print(" ", repr(row[cnpj_col]))
