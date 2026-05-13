from datetime import date
from .date_parser import days_until


def evaluate_status(expiry_date: date | None) -> tuple[str, int | None, str]:
    """
    Returns (status, days_to_expiry, alert_level) per R3.
    NÃO CONFORME when expiry is None or already passed.
    ATENÇÃO when 1–90 days remaining.
    CONFORME when > 90 days remaining.
    """
    if expiry_date is None:
        return "NÃO CONFORME", None, "CRITICAL"

    days = days_until(expiry_date)

    if days <= 0:
        return "NÃO CONFORME", days, "CRITICAL"
    if days <= 90:
        return "ATENÇÃO", days, "MEDIUM"
    return "CONFORME", days, "LOW"
