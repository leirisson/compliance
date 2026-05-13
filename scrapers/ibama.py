"""IBAMA scraper — CNPJ → razão social (ReceitaWS) → busca no CSV público SISLIC."""
import csv
import io
import json
import os
import unicodedata
import requests
from datetime import date
from utils.date_parser import parse_br_date
from .base import BaseScraper, ScraperResult

IBAMA_CSV_URL = os.getenv(
    "IBAMA_CSV_URL",
    "https://dadosabertos.ibama.gov.br/dados/SISLIC/sislic-licencas.csv",
)
RECEITAWS_URL = os.getenv("RECEITAWS_URL", "https://receitaws.com.br/v1/cnpj/{cnpj}")


def _normalize(text: str) -> str:
    """Remove acentos e converte para maiúsculas para comparação robusta."""
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().upper()


def _razao_social_from_receita(cnpj: str) -> str | None:
    """Consulta ReceitaWS e retorna a razão social, ou None em caso de erro."""
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


def _load_sislic_csv() -> list[dict]:
    try:
        resp = requests.get(IBAMA_CSV_URL, timeout=60, headers={"User-Agent": "compliance-scraper/1.0"})
        resp.raise_for_status()
    except requests.RequestException:
        return []
    text = resp.content.decode("latin-1", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


def _best_match(rows: list[dict], razao_social: str) -> dict | None:
    """Retorna a linha com LO mais recente cuja NOM_PESSOA bate com a razão social."""
    target = _normalize(razao_social)
    # Prioridade: LO ativa > LO vencida > qualquer tipo
    candidates = [r for r in rows if target in _normalize(r.get("NOM_PESSOA", ""))]
    if not candidates:
        return None

    lo_rows = [r for r in candidates if "LO" in (r.get("DES_TIPOLICENCA") or "").upper()
               or "OPERA" in (r.get("DES_TIPOLICENCA") or "").upper()]

    pool = lo_rows if lo_rows else candidates

    # Ordena por data de vencimento mais recente
    def _sort_key(r: dict):
        d = parse_br_date(r.get("DAT_VENCIMENTO") or "")
        return d or date.min

    return max(pool, key=_sort_key)


class IbamaScraper(BaseScraper):
    """Busca licenças ambientais federais no CSV público SISLIC/IBAMA.

    Fluxo:
      1. Consulta ReceitaWS com o CNPJ para obter razão social.
      2. Filtra o CSV SISLIC por NOM_PESSOA (correspondência parcial normalizada).
      3. Retorna a LO mais recente encontrada, ou resultado vazio.
    """

    def fetch(self, cnpj: str) -> ScraperResult:
        cnpj = self._clean_cnpj(cnpj)

        razao_social = _razao_social_from_receita(cnpj)
        if not razao_social:
            return ScraperResult(
                cnpj=cnpj, orgao="IBAMA",
                numero_licenca=None, tipo_licenca=None,
                expiry_date=None,
                raw_payload=json.dumps(
                    {"erro": "CNPJ não encontrado na Receita Federal"},
                    ensure_ascii=False,
                ),
            )

        rows = _load_sislic_csv()
        row = _best_match(rows, razao_social)

        if row is None:
            return ScraperResult(
                cnpj=cnpj, orgao="IBAMA",
                numero_licenca=None, tipo_licenca=None,
                expiry_date=None,
                raw_payload=json.dumps(
                    {"razao_social_consultada": razao_social,
                     "resultado": "não encontrado no SISLIC"},
                    ensure_ascii=False,
                ),
            )

        expiry = parse_br_date(row.get("DAT_VENCIMENTO") or "")
        return ScraperResult(
            cnpj=cnpj,
            orgao="IBAMA",
            numero_licenca=row.get("NUM_LICENCA") or None,
            tipo_licenca=row.get("DES_TIPOLICENCA") or None,
            expiry_date=expiry,
            raw_payload=json.dumps(
                {"razao_social_consultada": razao_social, **{k: v for k, v in row.items() if v}},
                ensure_ascii=False,
            ),
        )
