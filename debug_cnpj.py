"""Busca direta do CNPJ em todas as planilhas LO usando o scraper corrigido."""
import sys
sys.path.insert(0, ".")
from scrapers.ipaam import IpaamScraper, _LO_SHEETS, _normalize_cnpj, _HEADER_ROW_INDEX
import io, requests, openpyxl

CNPJ = "60357147000165"

for url in _LO_SHEETS:
    print(f"\nPlanilha: {url.split('/')[-1]}")
    resp = requests.get(url, timeout=30)
    wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    header = [str(c).strip() if c else "" for c in rows[_HEADER_ROW_INDEX]]
    cnpj_col = next((i for i, h in enumerate(header) if "CNPJ" in h.upper()), None)
    print(f"  Linhas de dados: {len(rows) - 2} | Coluna CNPJ: {cnpj_col} ({header[cnpj_col] if cnpj_col is not None else 'N/A'})")

    achou = any(
        _normalize_cnpj(row[cnpj_col]) == CNPJ
        for row in rows[_HEADER_ROW_INDEX + 1:]
        if cnpj_col is not None and row[cnpj_col]
    )
    print(f"  CNPJ {CNPJ}: {'ENCONTRADO' if achou else 'não encontrado'}")
