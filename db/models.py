from datetime import datetime
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cnpj: Mapped[str] = mapped_column(String(14), index=True, nullable=False)
    orgao: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    validade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    numero_licenca: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tipo_licenca: Mapped[str | None] = mapped_column(String(100), nullable=True)
    days_to_expiry: Mapped[int | None] = mapped_column(nullable=True)
    payload_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_consulta: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
