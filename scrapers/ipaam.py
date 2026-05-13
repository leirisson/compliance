"""IPAAM scraper — busca Licença de Operação nas planilhas Excel públicas do IPAAM."""
import io
import json
import os
import requests
import openpyxl
from .base import BaseScraper, ScraperResult
from utils.date_parser import parse_br_date

IPAAM_BASE_URL = os.getenv("IPAAM_BASE_URL", "https://www.ipaam.am.gov.br")

# Planilhas LO publicadas em ordem decrescente — última disponível: Maio/2022
# Fonte: ipaam.am.gov.br/licencas-ambientais-concedidas
_LO_SHEETS = [
    f"{IPAAM_BASE_URL}/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx",
    f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-DEZ-2021.xlsx",
    f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-DEZ-2020.xlsx",
    f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-12-2019.xlsx",
]


def _normalize_cnpj(value: str) -> str:
    return "".join(c for c in str(value) if c.isdigit()).zfill(14)


class IpaamScraper(BaseScraper):
    """Busca LO (Licença de Operação) nas planilhas Excel públicas do IPAAM.

    Sem portal de busca em tempo real — dados em Excel estático por mês/ano.
    Estratégia: baixar planilha LO mais recente → lookup por CNPJ na memória.
    """

    def fetch(self, cnpj: str) -> ScraperResult:
        cnpj = self._clean_cnpj(cnpj)

        for sheet_url in _LO_SHEETS:
            result = self._search_in_sheet(cnpj, sheet_url)
            if result.expiry_date is not None or result.numero_licenca is not None:
                return result

        return ScraperResult(
            cnpj=cnpj, orgao="IPAAM",
            numero_licenca=None, tipo_licenca="Licença de Operação (L.O.)",
            expiry_date=None, raw_payload=None,
        )

    def available_sheets(self) -> list[str]:
        """Retorna as URLs das planilhas LO configuradas."""
        return list(_LO_SHEETS)

    def _search_in_sheet(self, cnpj: str, url: str) -> ScraperResult:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return ScraperResult(
                cnpj=cnpj, orgao="IPAAM",
                numero_licenca=None, tipo_licenca=None,
                expiry_date=None, raw_payload=None,
            )

        wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return ScraperResult(cnpj=cnpj, orgao="IPAAM", numero_licenca=None,
                                 tipo_licenca=None, expiry_date=None, raw_payload=None)

        header = [str(c).strip().upper() if c else "" for c in rows[0]]

        cnpj_col = next((i for i, h in enumerate(header) if "CNPJ" in h), None)
        validade_col = next((i for i, h in enumerate(header)
                             if any(k in h for k in ("VALID", "VENCIM", "EXPIR", "DATA"))), None)
        numero_col = next((i for i, h in enumerate(header)
                           if any(k in h for k in ("LICENÇA", "NUMERO", "N°", "Nº"))), None)

        if cnpj_col is None:
            return ScraperResult(cnpj=cnpj, orgao="IPAAM", numero_licenca=None,
                                 tipo_licenca=None, expiry_date=None, raw_payload=None)

        for row in rows[1:]:
            cell_cnpj = _normalize_cnpj(row[cnpj_col]) if row[cnpj_col] else ""
            if cell_cnpj != cnpj:
                continue

            raw_payload = json.dumps(
                {header[i]: str(v) for i, v in enumerate(row) if v is not None},
                ensure_ascii=False,
            )
            validade_raw = str(row[validade_col]) if validade_col is not None and row[validade_col] else None
            numero = str(row[numero_col]) if numero_col is not None and row[numero_col] else None

            return ScraperResult(
                cnpj=cnpj,
                orgao="IPAAM",
                numero_licenca=numero,
                tipo_licenca="Licença de Operação (L.O.)",
                expiry_date=parse_br_date(validade_raw) if validade_raw else None,
                raw_payload=raw_payload,
            )

        return ScraperResult(cnpj=cnpj, orgao="IPAAM", numero_licenca=None,
                             tipo_licenca=None, expiry_date=None, raw_payload=None)
