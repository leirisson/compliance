"""IPAAM scraper — CNPJ → razão social (ReceitaWS) → busca nas planilhas Excel do IPAAM.

Fonte: ipaam.am.gov.br/transparencia-tecnica-licencas-ambientais-concedidadas
Nenhuma planilha do IPAAM contém CNPJ — todas usam razão social (INTERESSADO).
Estratégia: planilha consolidada (2018-2026) primeiro, fallback por tipo individual.
"""
import io
import json
import os
import re
import unicodedata
from datetime import date
import requests
import openpyxl
from .base import BaseScraper, ScraperResult
from utils.date_parser import parse_br_date

IPAAM_BASE_URL = os.getenv("IPAAM_BASE_URL", "https://www.ipaam.am.gov.br")
RECEITAWS_URL = os.getenv("RECEITAWS_URL", "https://receitaws.com.br/v1/cnpj/{cnpj}")

# Planilha consolidada — todas as licenças 2018 a março/2026
# Cabeçalho na linha 1 (índice 0), dados a partir da linha 2 (índice 1)
_CONSOLIDADA_URL = f"{IPAAM_BASE_URL}/wp-content/uploads/2026/04/TODAS-AS-LICENCAS-2018-a-2026-Marco.xlsx"
_CONSOLIDADA_HEADER_IDX = 0

# Planilhas individuais por tipo — cabeçalho linha 2 (índice 1), dados a partir do índice 2
_SHEETS_BY_TYPE: dict[str, list[str]] = {
    "LO": [
        f"{IPAAM_BASE_URL}/wp-content/uploads/2026/04/LO_MAR_2026.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2025/01/LO_DEZ_2024.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2022/07/LO-MAIO-2022.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-DEZ-2021.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-DEZ-2020.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2019/01/LO-12-2019.xlsx",
    ],
    "LP": [
        f"{IPAAM_BASE_URL}/wp-content/uploads/2026/04/LP_MAR_2026.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2025/01/LP_DEZ_2024.xlsx",
    ],
    "LI": [
        f"{IPAAM_BASE_URL}/wp-content/uploads/2026/04/LI_MAR_2026.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2025/01/LI_DEZ_2024.xlsx",
    ],
    "LAU": [
        f"{IPAAM_BASE_URL}/wp-content/uploads/2026/04/LAU_MAR_2026.xlsx",
        f"{IPAAM_BASE_URL}/wp-content/uploads/2025/01/LAU_DEZ_2024.xlsx",
    ],
}

_TIPO_LABEL = {
    "LO": "Licença de Operação (L.O.)",
    "LP": "Licença Prévia (L.P.)",
    "LI": "Licença de Instalação (L.I.)",
    "LAU": "Licença Ambiental Única (L.A.U.)",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().upper()


def _normalize_cnpj(value) -> str:
    return "".join(c for c in str(value) if c.isdigit()).zfill(14)


def _razao_social_from_receita(cnpj: str) -> str | None:
    url = RECEITAWS_URL.format(cnpj=cnpj)
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "compliance-scraper/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "ERROR":
            return None
        return data.get("nome") or None
    except (requests.RequestException, ValueError):
        return None


def _resolve_expiry(validade_texto, data_emissao) -> date | None:
    if isinstance(data_emissao, date):
        emissao = data_emissao
    elif hasattr(data_emissao, "date"):
        emissao = data_emissao.date()
    else:
        emissao = parse_br_date(str(data_emissao)) if data_emissao else None

    # Validade já é uma data direta (datetime do Excel)
    if hasattr(validade_texto, "date"):
        return validade_texto.date()
    if isinstance(validade_texto, date):
        return validade_texto

    if not validade_texto:
        return None

    texto = str(validade_texto).strip().upper()

    # Tenta parse direto como data (ex: "31/12/2024")
    parsed = parse_br_date(texto)
    if parsed:
        return parsed

    if emissao is None:
        return None

    # "2 ANOS", "02 ANOS", "1 ANO"
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

    return None


class IpaamScraper(BaseScraper):
    """Busca licenças ambientais (LO, LP, LI, LAU) nas planilhas Excel públicas do IPAAM.

    Fluxo:
      1. Consulta ReceitaWS com o CNPJ para obter razão social.
      2. Busca na planilha consolidada (todas as licenças 2018-2026) por INTERESSADO.
      3. Fallback: percorre planilhas individuais por tipo (LO → LP → LI → LAU).
    """

    def fetch(self, cnpj: str) -> ScraperResult:
        cnpj = self._clean_cnpj(cnpj)

        razao_social = _razao_social_from_receita(cnpj)
        if not razao_social:
            return ScraperResult(
                cnpj=cnpj, orgao="IPAAM",
                numero_licenca=None, tipo_licenca=None,
                expiry_date=None,
                raw_payload=json.dumps(
                    {"erro": "CNPJ não encontrado na Receita Federal"},
                    ensure_ascii=False,
                ),
            )

        # 1. Planilha consolidada
        result = self._search_in_sheet(
            razao_social, _CONSOLIDADA_URL,
            header_idx=_CONSOLIDADA_HEADER_IDX, tipo_label=None,
        )
        if result.numero_licenca is not None or result.expiry_date is not None:
            result.cnpj = cnpj
            return result

        # 2. Fallback por tipo individual (header na linha 2, índice 1)
        for tipo_key, urls in _SHEETS_BY_TYPE.items():
            for url in urls:
                result = self._search_in_sheet(
                    razao_social, url,
                    header_idx=1, tipo_label=_TIPO_LABEL[tipo_key],
                )
                if result.numero_licenca is not None or result.expiry_date is not None:
                    result.cnpj = cnpj
                    return result

        return ScraperResult(
            cnpj=cnpj, orgao="IPAAM",
            numero_licenca=None, tipo_licenca=None,
            expiry_date=None,
            raw_payload=json.dumps(
                {"razao_social_consultada": razao_social,
                 "resultado": "não encontrado no IPAAM"},
                ensure_ascii=False,
            ),
        )

    def available_sheets(self) -> dict:
        return {"consolidada": _CONSOLIDADA_URL, "por_tipo": _SHEETS_BY_TYPE}

    def _search_in_sheet(
        self, razao_social: str, url: str, header_idx: int, tipo_label: str | None
    ) -> ScraperResult:
        _empty = ScraperResult(cnpj="", orgao="IPAAM", numero_licenca=None,
                               tipo_licenca=None, expiry_date=None, raw_payload=None)
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return _empty

        wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if len(rows) <= header_idx:
            return _empty

        raw_header = rows[header_idx]
        header = [str(c).strip() if c else "" for c in raw_header]
        header_upper = [_normalize(h) for h in header]

        interessado_col = next((i for i, h in enumerate(header_upper) if "INTERESSADO" in h), None)
        numero_col = next((i for i, h in enumerate(header_upper) if "MERO DA LICEN" in h), None)
        validade_col = next((i for i, h in enumerate(header_upper) if "VALIDADE" in h), None)
        emissao_col = next((i for i, h in enumerate(header_upper)
                            if "RECEBIMENTO" in h or "EMISS" in h), None)
        tipo_col = next((i for i, h in enumerate(header_upper)
                         if "TIPOLOGIA" in h or ("TIPO" in h and "LICEN" in h)), None)

        if interessado_col is None:
            return _empty

        target = _normalize(razao_social)

        for row in rows[header_idx + 1:]:
            cell = row[interessado_col]
            if not cell:
                continue
            if target not in _normalize(str(cell)):
                continue

            numero = str(row[numero_col]) if numero_col is not None and row[numero_col] else None
            validade_val = row[validade_col] if validade_col is not None else None
            emissao_val = row[emissao_col] if emissao_col is not None else None
            expiry = _resolve_expiry(validade_val, emissao_val)

            tipo = None
            if tipo_col is not None and row[tipo_col]:
                raw_tipo = str(row[tipo_col]).strip().upper()
                tipo = _TIPO_LABEL.get(raw_tipo, raw_tipo)
            if not tipo:
                tipo = tipo_label

            raw_payload = json.dumps(
                {"razao_social_consultada": razao_social,
                 **{header[i]: str(v) for i, v in enumerate(row) if v is not None}},
                ensure_ascii=False,
            )

            return ScraperResult(
                cnpj="", orgao="IPAAM",
                numero_licenca=numero, tipo_licenca=tipo,
                expiry_date=expiry, raw_payload=raw_payload,
            )

        return _empty
