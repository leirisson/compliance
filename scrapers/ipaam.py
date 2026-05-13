"""IPAAM scraper — busca Licença de Operação nas planilhas Excel públicas do IPAAM."""
import io
import json
import os
import re
from datetime import date, timedelta
import requests
import openpyxl
from .base import BaseScraper, ScraperResult
from utils.date_parser import parse_br_date

IPAAM_BASE_URL = os.getenv("IPAAM_BASE_URL", "https://www.ipaam.am.gov.br")

# Planilhas LO em ordem decrescente — última disponível: Maio/2022
# Fonte: ipaam.am.gov.br/licencas-ambientais-concedidas
_LO_SHEETS = [
    f"{IPAAM_BASE_URL}/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx",
    f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-DEZ-2021.xlsx",
    f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-DEZ-2020.xlsx",
    f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-12-2019.xlsx",
]

# Estrutura real da planilha LO-MAIO-2022 (linha 1 = título, linha 2 = cabeçalho)
_HEADER_ROW_INDEX = 1  # índice 0-based da linha de cabeçalho
_COL_CNPJ = "CNPJ/CPF"
_COL_NUMERO = "NÚMERO DA LICENÇA"
_COL_VALIDADE_TEXTO = "VALIDADE DA LICENÇA"   # ex: "01 ANO", "02 ANOS"
_COL_DATA_EMISSAO = "DATA DE RECEBIMENTO DA LICENÇA"  # datetime do Excel


def _normalize_cnpj(value) -> str:
    return "".join(c for c in str(value) if c.isdigit()).zfill(14)


def _resolve_expiry(validade_texto: str | None, data_emissao) -> date | None:
    """
    Calcula a data de validade real a partir do texto (ex: '01 ANO') e da data de emissão.
    Retorna None se não for possível calcular.
    """
    if isinstance(data_emissao, date):
        emissao = data_emissao
    elif hasattr(data_emissao, "date"):
        emissao = data_emissao.date()
    else:
        emissao = parse_br_date(str(data_emissao)) if data_emissao else None

    if emissao is None:
        return None

    if not validade_texto:
        return None

    texto = validade_texto.strip().upper()

    # "2 ANOS", "02 ANOS", "1 ANO", "01 ANO"
    match_anos = re.search(r"(\d+)\s*ANO", texto)
    if match_anos:
        anos = int(match_anos.group(1))
        return date(emissao.year + anos, emissao.month, emissao.day)

    # "6 MESES", "18 MESES"
    match_meses = re.search(r"(\d+)\s*M[EÊ]S", texto)
    if match_meses:
        meses = int(match_meses.group(1))
        total_months = emissao.month + meses
        year = emissao.year + (total_months - 1) // 12
        month = (total_months - 1) % 12 + 1
        return date(year, month, emissao.day)

    # Tenta parse direto como data (ex: "31/12/2024")
    return parse_br_date(validade_texto)


class IpaamScraper(BaseScraper):
    """Busca LO (Licença de Operação) nas planilhas Excel públicas do IPAAM.

    Sem portal de busca em tempo real — dados em Excel estático por mês/ano.
    Estratégia: baixar planilha LO mais recente → lookup por CNPJ na memória.
    Estrutura real: linha 1 = título, linha 2 = cabeçalho, linha 3+ = dados.
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
            return ScraperResult(cnpj=cnpj, orgao="IPAAM", numero_licenca=None,
                                 tipo_licenca=None, expiry_date=None, raw_payload=None)

        wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if len(rows) <= _HEADER_ROW_INDEX:
            return ScraperResult(cnpj=cnpj, orgao="IPAAM", numero_licenca=None,
                                 tipo_licenca=None, expiry_date=None, raw_payload=None)

        # Cabeçalho real na linha 2 (índice 1); normaliza removendo acentos via encode/decode
        raw_header = rows[_HEADER_ROW_INDEX]
        header = [str(c).strip() if c else "" for c in raw_header]
        header_upper = [h.upper() for h in header]

        cnpj_col = next((i for i, h in enumerate(header_upper) if "CNPJ" in h), None)
        # "NÚMERO DA LICENÇA" → sobrevive ao encoding como "N?MERO DA LICEN?A"
        numero_col = next((i for i, h in enumerate(header_upper) if "MERO DA LICEN" in h), None)
        validade_col = next((i for i, h in enumerate(header_upper) if "VALIDADE" in h), None)
        emissao_col = next((i for i, h in enumerate(header_upper)
                            if "RECEBIMENTO" in h or "EMISS" in h), None)

        if cnpj_col is None:
            return ScraperResult(cnpj=cnpj, orgao="IPAAM", numero_licenca=None,
                                 tipo_licenca=None, expiry_date=None, raw_payload=None)

        for row in rows[_HEADER_ROW_INDEX + 1:]:
            if not row[cnpj_col]:
                continue
            if _normalize_cnpj(row[cnpj_col]) != cnpj:
                continue

            raw_payload = json.dumps(
                {header[i]: str(v) for i, v in enumerate(row) if v is not None},
                ensure_ascii=False,
            )
            numero = str(row[numero_col]) if numero_col is not None and row[numero_col] else None
            validade_txt = str(row[validade_col]) if validade_col is not None and row[validade_col] else None
            data_emissao = row[emissao_col] if emissao_col is not None else None
            expiry = _resolve_expiry(validade_txt, data_emissao)

            return ScraperResult(
                cnpj=cnpj,
                orgao="IPAAM",
                numero_licenca=numero,
                tipo_licenca="Licença de Operação (L.O.)",
                expiry_date=expiry,
                raw_payload=raw_payload,
            )

        return ScraperResult(cnpj=cnpj, orgao="IPAAM", numero_licenca=None,
                             tipo_licenca=None, expiry_date=None, raw_payload=None)
