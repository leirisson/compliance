import re
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import ComplianceRecord
from scrapers.ipaam import IpaamScraper
from scrapers.fvs import FvsScraper
from scrapers.crea_am import CreaAmScraper, CreaAmResult
from utils.compliance_rules import evaluate_status
from .schemas import (
    ComplianceResponse, ResponseHeader, ComplianceInfo, DocumentInfo, AnalysisInfo,
    CreaComplianceResponse, CreaDetailsSchema, RegistroPjSchema, ResponsavelTecnicoSchema,
)

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


@router.get("/am/{cnpj}/fvs", response_model=ComplianceResponse)
def get_compliance_fvs(cnpj: str, db: Session = Depends(get_db)):
    cnpj_clean = _clean_cnpj(cnpj)
    if not CNPJ_RE.match(cnpj_clean):
        raise HTTPException(status_code=422, detail="CNPJ inválido. Informe 14 dígitos numéricos.")

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    cached: ComplianceRecord | None = (
        db.query(ComplianceRecord)
        .filter(
            ComplianceRecord.cnpj == cnpj_clean,
            ComplianceRecord.orgao == "FVS/DEVISA",
            ComplianceRecord.data_consulta >= cutoff,
        )
        .order_by(ComplianceRecord.data_consulta.desc())
        .first()
    )

    if cached:
        return _build_response(cached, is_cached=True)

    result = FvsScraper().fetch(cnpj_clean)
    status, days, alert = evaluate_status(result.expiry_date)

    record = ComplianceRecord(
        cnpj=cnpj_clean,
        orgao="FVS/DEVISA",
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


@router.get("/am/{cnpj}/crea", response_model=CreaComplianceResponse)
def get_compliance_crea(cnpj: str, db: Session = Depends(get_db)):
    cnpj_clean = _clean_cnpj(cnpj)
    if not CNPJ_RE.match(cnpj_clean):
        raise HTTPException(status_code=422, detail="CNPJ inválido. Informe 14 dígitos numéricos.")

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    cached: ComplianceRecord | None = (
        db.query(ComplianceRecord)
        .filter(
            ComplianceRecord.cnpj == cnpj_clean,
            ComplianceRecord.orgao == "CREA-AM",
            ComplianceRecord.data_consulta >= cutoff,
        )
        .order_by(ComplianceRecord.data_consulta.desc())
        .first()
    )

    if cached:
        return _build_crea_response(cached, crea_result=None, is_cached=True)

    try:
        crea_result = CreaAmScraper().fetch_detailed(cnpj_clean)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    status, alert = _evaluate_crea_status(crea_result)
    record = ComplianceRecord(
        cnpj=cnpj_clean,
        orgao="CREA-AM",
        status=status,
        validade=None,
        numero_licenca=crea_result.numero_registro,
        tipo_licenca=crea_result.scraper_result.tipo_licenca,
        days_to_expiry=None,
        payload_extraido=crea_result.scraper_result.raw_payload,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return _build_crea_response(record, crea_result=crea_result, is_cached=False)


def _evaluate_crea_status(result: CreaAmResult) -> tuple[str, str]:
    """Conformidade CREA: PJ ATIVO + ao menos 1 RT ATIVO → CONFORME (R7 + R8)."""
    _ativas = {"ATIVO", "ATIVA", "REGULAR"}
    pj_ativo = result.situacao_pj is not None and result.situacao_pj.upper() in _ativas
    rt_ativo = any(
        rt.situacao and rt.situacao.upper() in _ativas
        for rt in result.responsaveis_tecnicos
    )
    if pj_ativo and rt_ativo:
        return "CONFORME", "LOW"
    if pj_ativo and not rt_ativo:
        return "ATENÇÃO", "MEDIUM"
    return "NÃO CONFORME", "CRITICAL"


def _build_crea_response(
    record: ComplianceRecord,
    crea_result: CreaAmResult | None,
    is_cached: bool,
) -> CreaComplianceResponse:
    status = record.status
    alert = "LOW" if status == "CONFORME" else ("MEDIUM" if status == "ATENÇÃO" else "CRITICAL")

    if crea_result is not None:
        rts = [
            ResponsavelTecnicoSchema(
                nome=rt.nome,
                titulo=rt.titulo,
                registro_crea=rt.registro_crea,
                situacao=rt.situacao,
            )
            for rt in crea_result.responsaveis_tecnicos
        ]
        details = CreaDetailsSchema(
            registro_pj=RegistroPjSchema(
                situacao=crea_result.situacao_pj,
                numero_registro=crea_result.numero_registro,
                data_registro=(
                    crea_result.data_registro.isoformat()
                    if crea_result.data_registro else None
                ),
            ),
            responsaveis_tecnicos=rts,
        )
    else:
        # cache hit: reconstrói details mínimo a partir do record
        details = CreaDetailsSchema(
            registro_pj=RegistroPjSchema(
                situacao=None,
                numero_registro=record.numero_licenca,
                data_registro=None,
            ),
            responsaveis_tecnicos=[],
        )

    return CreaComplianceResponse(
        header=ResponseHeader(
            cnpj=record.cnpj,
            region="AM",
            provider="CREA-AM",
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
                days_to_expiry=record.days_to_expiry,
                alert_level=alert,
            ),
        ),
        details=details,
    )


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
