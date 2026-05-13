"""Executa o IpaamScraper diretamente e imprime o ScraperResult."""
import sys; sys.path.insert(0, ".")
from scrapers.ipaam import IpaamScraper

result = IpaamScraper().fetch("61064838009785")
print("cnpj          :", result.cnpj)
print("orgao         :", result.orgao)
print("numero_licenca:", result.numero_licenca)
print("tipo_licenca  :", result.tipo_licenca)
print("expiry_date   :", result.expiry_date)
print("raw_payload   :", result.raw_payload[:120] if result.raw_payload else None)
