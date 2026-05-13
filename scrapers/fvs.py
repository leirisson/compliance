"""FVS/DEVISA scraper — Licenciamento Sanitário Estadual do Amazonas.

Não existe portal público de busca por CNPJ. Estratégia:
  1. Consulta ReceitaWS para obter CNAE principal da empresa.
  2. Verifica se o CNAE está na lista de atividades fiscalizadas pelo DEVISA/FVS-RCP.
  3. Retorna resultado indicando sujeição ao licenciamento e instruções de consulta manual.

Fonte CNAE: https://www.fvs.am.gov.br/media/publicacao/4.Atividade-CNAE-DEVISA.pdf
"""
import json
import os
import re
import requests
from .base import BaseScraper, ScraperResult

RECEITAWS_URL = os.getenv("RECEITAWS_URL", "https://receitaws.com.br/v1/cnpj/{cnpj}")
FVS_PORTAL_URL = "https://www.fvs.am.gov.br/portal_servicos_view/1"
FVS_FORMULARIOS_URL = "https://www.fvs.am.gov.br/formularios"
SIGED_URL = "https://online.sefaz.am.gov.br/processo/"
SLIM_URL = "https://slim.manaus.am.gov.br"

# CNAEs sujeitos a Licenciamento Sanitário Estadual pelo DEVISA/FVS-RCP (Risco III).
# Fonte: Atividade-CNAE-DEVISA.pdf — atualizado em 2026-05.
# Formato: 7 ou 8 dígitos sem pontuação.
_DEVISA_CNAES: set[str] = {
    # Alimentos e bebidas
    "8924030", "1031700", "1032501", "1032599", "1041400", "1042200",
    "1053800", "1061901", "1061902", "1062700", "1063500", "1064300",
    "1065101", "1065102", "1065103", "1069400", "1069401", "1069402",
    "1071600", "1072401", "1072402", "1081301", "1081302", "1082100",
    "1091101", "1092900", "1093701", "1093702", "1094500", "1095300",
    "1096100", "1099602", "1099603", "1099605", "1099606", "1099607",
    "1099609", "1099699", "1121600", "1122403", "1122404", "1122499",
    # Embalagens para alimentos e saúde
    "1730100", "1732000", "1733800", "1742701", "1742702",
    # Químicos, gases, domissanitários, cosméticos e farmacêuticos
    "2014200", "2052500", "2061400", "2062200", "2063100",
    "2093200", "2093200",
    "2110600", "2121101", "2121102", "2121103", "2123800",
    # Borracha, plástico, vidro e cerâmica para uso médico ou alimentar
    "2219600", "2222600", "2312500", "2341900", "2349499", "2591800",
    # Equipamentos médicos e eletromédicos
    "2660400", "2829199", "3092000",
    "3250701", "3250702", "3250703", "3250704", "3250705", "3250702",
    "3250709", "3291400",
    # Esterilização e serviços de saúde
    "8129000", "8610101", "8610102",
    "8630501", "8630507",
    "8640203", "8640210", "8640211", "8640212", "8640213", "8640214",
    "8650007", "8704990",
}


def _normalize_cnae(raw: str) -> str:
    """Remove pontuação e retorna apenas dígitos."""
    return re.sub(r"\D", "", str(raw))


def _cnae_matches(cnae: str) -> bool:
    """Verifica se um CNAE (com ou sem pontuação) está na lista DEVISA."""
    digits = _normalize_cnae(cnae)
    # Compara pelos primeiros 7 dígitos (sem o dígito verificador quando há 8)
    return digits in _DEVISA_CNAES or digits[:7] in _DEVISA_CNAES


def _consulta_receita(cnpj: str) -> dict | None:
    url = RECEITAWS_URL.format(cnpj=cnpj)
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "compliance-scraper/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "ERROR":
            return None
        return data
    except (requests.RequestException, ValueError):
        return None


class FvsScraper(BaseScraper):
    """Licenciamento Sanitário Estadual — DEVISA/FVS-RCP.

    Não há API ou base pública consultável por CNPJ.
    O scraper determina se a empresa está sujeita ao licenciamento pelo CNAE
    e retorna as instruções de consulta manual via SIGED (interior) ou SLIM (Manaus).
    """

    def fetch(self, cnpj: str) -> ScraperResult:
        cnpj = self._clean_cnpj(cnpj)

        receita = _consulta_receita(cnpj)
        if receita is None:
            return ScraperResult(
                cnpj=cnpj, orgao="FVS/DEVISA",
                numero_licenca=None,
                tipo_licenca="Licença Sanitária Estadual",
                expiry_date=None,
                raw_payload=json.dumps(
                    {"erro": "CNPJ não encontrado na Receita Federal"},
                    ensure_ascii=False,
                ),
            )

        municipio = (receita.get("municipio") or "").upper()
        is_manaus = "MANAUS" in municipio

        # Coleta todos os CNAEs (principal + secundários)
        cnaes_empresa: list[str] = []
        cnae_principal = receita.get("atividade_principal", [{}])
        if isinstance(cnae_principal, list):
            for a in cnae_principal:
                if a.get("code"):
                    cnaes_empresa.append(a["code"])
        cnaes_secundarias = receita.get("atividades_secundarias", [])
        if isinstance(cnaes_secundarias, list):
            for a in cnaes_secundarias:
                if a.get("code"):
                    cnaes_empresa.append(a["code"])

        cnaes_devisa = [c for c in cnaes_empresa if _cnae_matches(c)]
        sujeita = bool(cnaes_devisa)

        consulta_url = SLIM_URL if is_manaus else SIGED_URL
        consulta_sistema = "SLIM (Manaus)" if is_manaus else "SIGED / protocolo@fvs.am.gov.br"

        payload = {
            "razao_social": receita.get("nome"),
            "municipio": receita.get("municipio"),
            "cnaes_empresa": cnaes_empresa,
            "cnaes_sujeitos_devisa": cnaes_devisa,
            "sujeita_licenciamento_fvs": sujeita,
            "consulta_manual": consulta_url,
            "sistema_consulta": consulta_sistema,
            "observacao": (
                "Licença sanitária não consultável por CNPJ em base pública. "
                "Verificar número do processo no sistema indicado."
            ),
        }

        return ScraperResult(
            cnpj=cnpj,
            orgao="FVS/DEVISA",
            numero_licenca=None,
            tipo_licenca="Licença Sanitária Estadual",
            expiry_date=None,
            raw_payload=json.dumps(payload, ensure_ascii=False),
        )

    def is_subject_to_licensing(self, cnpj: str) -> bool:
        """Retorna True se a empresa provavelmente está sujeita ao licenciamento DEVISA."""
        result = self.fetch(cnpj)
        if result.raw_payload:
            data = json.loads(result.raw_payload)
            return bool(data.get("sujeita_licenciamento_fvs"))
        return False
