"""Busca CNPJ em todas as planilhas LO e exibe o registro completo se encontrado."""
import io, requests, openpyxl, sys
sys.path.insert(0, ".")
from scrapers.ipaam import _LO_SHEETS, _HEADER_ROW_INDEX, _normalize_cnpj

CNPJ = "36289472000153"

for url in _LO_SHEETS:
    planilha = url.split("/")[-1]
    resp = requests.get(url, timeout=30)
    wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    header = [str(c).strip() if c else "" for c in rows[_HEADER_ROW_INDEX]]
    cnpj_col = next((i for i, h in enumerate(header) if "CNPJ" in h.upper()), None)

    if cnpj_col is None:
        print(f"{planilha}: sem coluna CNPJ detectada")
        continue

    achou = False
    for row in rows[_HEADER_ROW_INDEX + 1:]:
        if row[cnpj_col] and _normalize_cnpj(row[cnpj_col]) == CNPJ:
            print(f"\n{planilha}: ENCONTRADO")
            for h, v in zip(header, row):
                if v is not None:
                    print(f"  {h}: {v}")
            achou = True
            break

    if not achou:
        print(f"{planilha}: não encontrado ({len(rows)-2} registros)")
