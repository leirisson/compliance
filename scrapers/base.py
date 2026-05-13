from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class ScraperResult:
    cnpj: str
    orgao: str
    numero_licenca: str | None
    tipo_licenca: str | None
    expiry_date: date | None
    raw_payload: str | None


class BaseScraper(ABC):
    def __init__(self, headless: bool = True):
        self.headless = headless

    @abstractmethod
    def fetch(self, cnpj: str) -> ScraperResult:
        """Navigates the portal and returns structured compliance data."""
        ...

    def _clean_cnpj(self, cnpj: str) -> str:
        return "".join(c for c in cnpj if c.isdigit())
