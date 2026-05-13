"""Insere um registro de exemplo no banco para demonstrar o retorno da API."""
from datetime import datetime, timezone
from db.session import SessionLocal, init_db
from db.models import ComplianceRecord

CNPJ_EXEMPLO = "04632844000188"  # CNPJ fictício formatado com 14 dígitos

init_db()
db = SessionLocal()

# Remove registro anterior do mesmo CNPJ, se existir
db.query(ComplianceRecord).filter(ComplianceRecord.cnpj == CNPJ_EXEMPLO).delete()

record = ComplianceRecord(
    cnpj=CNPJ_EXEMPLO,
    orgao="IPAAM",
    status="CONFORME",
    validade="2026-12-31",
    numero_licenca="LO-0472/2024",
    tipo_licenca="Licença de Operação (L.O.)",
    days_to_expiry=233,
    payload_extraido='{"RAZAO_SOCIAL": "EMPRESA EXEMPLO LTDA", "CNPJ": "04632844000188", "LICENÇA": "LO-0472/2024", "VALIDADE": "31/12/2026"}',
    data_consulta=datetime.now(tz=timezone.utc),
)
db.add(record)
db.commit()
print(f"Registro inserido para CNPJ {CNPJ_EXEMPLO}")
db.close()
