"""CREA-AM scraper — consulta registro de PJ via portal SITAC público."""
import json
import re
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup

from .base import BaseScraper, ScraperResult

_SITAC_URL = (
    "https://crea-am.sitac.com.br/app/view/sight/externo.php"
    "?form=PesquisarProfissionalEmpresa"
)
_AJAX_PATH = "../requests.ajax/PessoaExternoAjaxRequest.php"

_SITUACOES_ATIVAS = {"ATIVO", "ATIVA", "REGULAR"}
_SITUACOES_IRREGULARES = {"SUSPENSO", "CANCELADO", "INATIVO"}
_TITULOS_RT = {"ENGENHEIRO", "AGRÔNOMO", "ARQUITETO", "GEÓGRAFO", "GEÓLOGO"}
_TIPO_CRQPJ = "Certidão de Registro e Quitação de Pessoa Jurídica (CRQPJ)"


@dataclass
class ResponsavelTecnico:
    """Responsável Técnico vinculado ao registro de PJ."""

    nome: str
    titulo: str | None
    registro_crea: str | None
    situacao: str | None


@dataclass
class CreaAmResult:
    """Resultado estendido do CREA-AM: ScraperResult + detalhes do registro PJ."""

    scraper_result: ScraperResult
    situacao_pj: str | None = None
    numero_registro: str | None = None
    data_registro: date | None = None
    responsaveis_tecnicos: list[ResponsavelTecnico] = field(default_factory=list)


class CreaAmScraper(BaseScraper):
    """Consulta registro de PJ e RTs no portal SITAC público do CREA-AM.

    O SITAC é uma SPA em JS — requer Playwright para renderizar e interagir.
    Estratégia:
      1. Abre o formulário público sem login.
      2. Seleciona radio EMPRESA (TIPOPESSOA=2) e preenche o campo #CNPJ.
      3. Clica em Pesquisar e aguarda networkidle.
      4. Extrai: situação do registro PJ, nº registro e lista de RTs.
      5. Conformidade: PJ ATIVO + ao menos 1 RT ATIVO → CONFORME (R7 + R8).
    """

    def fetch(self, cnpj: str) -> ScraperResult:
        return self._fetch_crea(self._clean_cnpj(cnpj)).scraper_result

    def fetch_detailed(self, cnpj: str) -> CreaAmResult:
        """Retorna CreaAmResult completo com lista de RTs (usado pelo endpoint da API)."""
        return self._fetch_crea(self._clean_cnpj(cnpj))

    @staticmethod
    def _format_cnpj(cnpj_digits: str) -> str:
        """Formata 14 dígitos em XX.XXX.XXX/XXXX-XX (esperado pelo campo do SITAC)."""
        d = cnpj_digits.zfill(14)
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"

    def _fetch_crea(self, cnpj: str) -> CreaAmResult:
        try:
            from playwright.sync_api import (  # noqa: PLC0415
                TimeoutError as PWTimeout,
                sync_playwright,
            )
        except ImportError as exc:
            raise RuntimeError(
                "Playwright não instalado. "
                "Execute: pip install playwright && playwright install chromium"
            ) from exc

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = ctx.new_page()
            ajax_html: list[str] = []

            def _intercept(route, request):
                if "PessoaExternoAjaxRequest" in request.url:
                    resp = route.fetch()
                    body = resp.text()
                    ajax_html.append(body)
                    route.fulfill(response=resp)
                else:
                    route.continue_()

            page.route("**/*", _intercept)
            try:
                page.goto(_SITAC_URL, wait_until="networkidle", timeout=30_000)
                # Selecionar EMPRESA, preencher CNPJ e clicar — o JS do botão
                # gera um novo token reCAPTCHA antes de disparar o AJAX
                page.locator("input[name='TIPOPESSOA'][value='2']").check()
                page.wait_for_selector("#CNPJ", state="visible", timeout=5_000)
                # SITAC rejeita CNPJ sem formatação — enviar com máscara
                page.locator("#CNPJ").fill(self._format_cnpj(cnpj))
                page.locator("#PESQUISAR").click()
                # Aguardar o AJAX ser interceptado (até 20s)
                page.wait_for_function(
                    "() => document.querySelector('#Result_pesquisa') && "
                    "document.querySelector('#Result_pesquisa').innerHTML.trim() !== '' && "
                    "!document.querySelector('#Result_pesquisa').innerHTML.includes('ajaxindicator')",
                    timeout=20_000,
                )
                html = ajax_html[0] if ajax_html else ""
                return self._parse_ajax_result(html, cnpj)
            except PWTimeout:
                html = ajax_html[0] if ajax_html else ""
                if html:
                    return self._parse_ajax_result(html, cnpj)
                return self._empty_result(cnpj, "Timeout aguardando resultado do SITAC CREA-AM")
            finally:
                browser.close()

    def _parse_ajax_result(self, html: str, cnpj: str) -> CreaAmResult:
        """Parseia o HTML retornado pelo endpoint AJAX do SITAC."""
        if not html or html.startswith("AJAX_ERROR:"):
            return self._empty_result(cnpj, html or "Resposta vazia do servidor SITAC")

        soup = BeautifulSoup(html, "html.parser")
        text_upper = soup.get_text(" ").upper()

        not_found_msgs = [
            "NENHUM RESULTADO", "NÃO ENCONTRADO", "NENHUM REGISTRO",
            "NADA LOCALIZADO", "CNPJ INV",
        ]
        if any(msg in text_upper for msg in not_found_msgs):
            return self._empty_result(cnpj, "Empresa não encontrada no CREA-AM")

        situacao_pj: str | None = None
        numero_registro: str | None = None
        responsaveis: list[ResponsavelTecnico] = []
        raw_payload: dict = {}

        for row in soup.select("table tr"):
            cells = [td.get_text(" ", strip=True) for td in row.select("td")]
            if not cells:
                continue
            row_text = " ".join(cells).upper()
            cnpj_digits = re.sub(r"\D", "", cnpj)

            # Linha da empresa: contém o CNPJ
            if cnpj_digits in re.sub(r"\D", "", row_text):
                for cell in cells:
                    cu = cell.upper()
                    if cu in _SITUACOES_ATIVAS | _SITUACOES_IRREGULARES:
                        situacao_pj = cu
                        break
                numero_registro = cells[0] if cells else None
                raw_payload["empresa_row"] = cells

            # Linha de Responsável Técnico: contém título de engenheiro/afins
            if any(t in row_text for t in _TITULOS_RT):
                responsaveis.append(ResponsavelTecnico(
                    nome=cells[0] if len(cells) > 0 else "",
                    titulo=cells[1] if len(cells) > 1 else None,
                    registro_crea=cells[2] if len(cells) > 2 else None,
                    situacao=cells[3] if len(cells) > 3 else None,
                ))

        raw_payload["responsaveis_count"] = len(responsaveis)

        return CreaAmResult(
            scraper_result=ScraperResult(
                cnpj=cnpj,
                orgao="CREA-AM",
                numero_licenca=numero_registro,
                tipo_licenca=_TIPO_CRQPJ,
                expiry_date=None,
                raw_payload=json.dumps(raw_payload, ensure_ascii=False),
            ),
            situacao_pj=situacao_pj,
            numero_registro=numero_registro,
            data_registro=None,
            responsaveis_tecnicos=responsaveis,
        )

    def _empty_result(self, cnpj: str, motivo: str) -> CreaAmResult:
        return CreaAmResult(
            scraper_result=ScraperResult(
                cnpj=cnpj,
                orgao="CREA-AM",
                numero_licenca=None,
                tipo_licenca=_TIPO_CRQPJ,
                expiry_date=None,
                raw_payload=json.dumps({"motivo": motivo}, ensure_ascii=False),
            )
        )
