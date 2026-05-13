from datetime import date, datetime


def parse_br_date(raw: str) -> date | None:
    """Converts Brazilian date strings (DD/MM/YYYY) to date objects."""
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def days_until(expiry: date) -> int:
    return (expiry - date.today()).days
