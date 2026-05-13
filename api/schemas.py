from datetime import datetime
from pydantic import BaseModel


class ResponsavelTecnicoSchema(BaseModel):
    nome: str
    titulo: str | None
    registro_crea: str | None
    situacao: str | None


class RegistroPjSchema(BaseModel):
    situacao: str | None
    numero_registro: str | None
    data_registro: str | None


class CreaDetailsSchema(BaseModel):
    registro_pj: RegistroPjSchema
    responsaveis_tecnicos: list[ResponsavelTecnicoSchema]


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


class CreaComplianceResponse(ComplianceResponse):
    details: CreaDetailsSchema
