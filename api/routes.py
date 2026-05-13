import re
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import ComplianceRecord
from scrapers.ipaam import IpaamScraper
from utils.compliance_rules import evaluate_status
from .schemas import ComplianceResponse, ResponseHeader, ComplianceInfo, DocumentInfo, AnalysisInfo

import os

CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
CNPJ_RE = re.compile(r"^\d{14}$")

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])


def _clean_cnpj(cnpj: str) -> str:
    return "".join(c for c in cnpj if c.isdigit())


@router.get("/am/{cnpj}", response_model=ComplianceResponse)
def get_compliance_am(cnpj: str, db: Session = Depends(get_db)):
    cnpj_clean = _clean_cnpj(cnpj)
    if not CNPJ_RE.match(cnpj_clean):
        raise HTTPException(status_code=422, detail="CNPJ inválido. Informe 14 dígitos numéricos.")

    # R4: check cache
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    cached: ComplianceRecord | None = (
        db.query(ComplianceRecord)
        .filter(
            ComplianceRecord.cnpj == cnpj_clean,
            ComplianceRecord.orgao == "IPAAM",
            ComplianceRecord.data_consulta >= cutoff,
        )
        .order_by(ComplianceRecord.data_consulta.desc())
        .first()
    )

    if cached:
        return _build_response(cached, is_cached=True)

    # Run scraper
    result = IpaamScraper().fetch(cnpj_clean)
    status, days, alert = evaluate_status(result.expiry_date)

    record = ComplianceRecord(
        cnpj=cnpj_clean,
        orgao="IPAAM",
        status=status,
        validade=result.expiry_date.isoformat() if result.expiry_date else None,
        numero_licenca=result.numero_licenca,
        tipo_licenca=result.tipo_licenca,
        days_to_expiry=days,
        payload_extraido=result.raw_payload,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return _build_response(record, is_cached=False)


def _build_response(record: ComplianceRecord, is_cached: bool) -> ComplianceResponse:
    days = record.days_to_expiry
    status = record.status
    alert = "LOW" if status == "CONFORME" else ("MEDIUM" if status == "ATENÇÃO" else "CRITICAL")

    return ComplianceResponse(
        header=ResponseHeader(
            cnpj=record.cnpj,
            region="AM",
            provider=record.orgao,
            queried_at=record.data_consulta,
            cached=is_cached,
        ),
        compliance=ComplianceInfo(
            status=status,
            document=DocumentInfo(
                type=record.tipo_licenca,
                number=record.numero_licenca,
                expiry_date=record.validade,
            ),
            analysis=AnalysisInfo(
                is_valid=status == "CONFORME",
                days_to_expiry=days,
                alert_level=alert,
            ),
        ),
    )
