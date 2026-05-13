from datetime import datetime
from pydantic import BaseModel


class DocumentInfo(BaseModel):
    type: str | None
    number: str | None
    expiry_date: str | None


class AnalysisInfo(BaseModel):
    is_valid: bool
    days_to_expiry: int | None
    alert_level: str


class ComplianceInfo(BaseModel):
    status: str
    document: DocumentInfo
    analysis: AnalysisInfo


class ResponseHeader(BaseModel):
    cnpj: str
    region: str
    provider: str
    queried_at: datetime
    cached: bool


class ComplianceResponse(BaseModel):
    header: ResponseHeader
    compliance: ComplianceInfo
