# Spec-Driven Development (SDD) - Projeto Compliance Manaus

Este documento define a especificação técnica para a Prova de Conceito (POC) do SaaS de consulta de conformidade regulatória, focado inicialmente em órgãos ambientais e sanitários da região de Manaus/AM.

---

## 1. Feature Spec: Motor de Consulta Regional (AM-IPAAM)
**ID:** `SPEC-AM-001`  
**Escopo:** Automação de consulta no Instituto de Proteção Ambiental do Amazonas (IPAAM).

### Descrição
Desenvolver uma API em Python que realiza o scraping de dados no portal do IPAAM para validar a vigência de Licenças de Operação (L.O.) via CNPJ, consolidando os dados em um banco de dados PostgreSQL para histórico e auditoria.

---

## 2. Regras de Negócio (Rules)

| ID | Regra | Descrição |
| :--- | :--- | :--- |
| **R1** | **Regionalidade** | O sistema deve priorizar seletores e fluxos específicos para o portal do IPAAM (Amazonas). |
| **R2** | **Normalização de Data** | Toda data extraída (ex: `30/06/2026`) deve ser convertida para o padrão ISO `YYYY-MM-DD` antes da persistência. |
| **R3** | **Lógica de Conformidade** | **CONFORME**: Validade > 90 dias.<br>**ATENÇÃO**: Validade entre 1 e 90 dias.<br>**NÃO CONFORME**: Data vencida ou licença não encontrada. |
| **R4** | **Política de Cache** | Se houver uma consulta no Postgres para o mesmo CNPJ realizada há menos de 24h, retornar o dado local e evitar novo scraping. |
| **R5** | **Evidência de Auditoria** | O sistema deve capturar o log da tabela extraída e, se possível, o link do documento oficial para fins de prova. |

---

## 3. Lista de Tarefas (Text Tasks)

### Fase A: Infraestrutura e Dados
- [ ] Configurar ambiente virtual Python 3.10+ e instalar dependências (`fastapi`, `playwright`, `sqlalchemy`, `psycopg2-binary`).
- [ ] Criar arquivo `docker-compose.yml` para subir instância local do **PostgreSQL**.
- [ ] Definir Model SQLAlchemy para a tabela `compliance_records` (campos: id, cnpj, orgao, status, validade, payload_extraido, data_consulta).

### Fase B: Automação (Python + Playwright)
- [ ] Implementar a classe base `BaseScraper` com tratamento de erros global.
- [ ] Implementar `IpaamScraper` com lógica de navegação no portal:
    - [ ] Input de CNPJ.
    - [ ] Bypass de alertas/popups.
    - [ ] Extração de dados da tabela de Licenças Emitidas.
- [ ] Implementar utilitário de parser para conversão de strings de data brasileiras em objetos `datetime`.

### Fase C: API e Integração
- [ ] Criar endpoint FastAPI `GET /compliance/am/{cnpj}`.
- [ ] Implementar lógica de serviço: `Check Cache -> Run Scraper (se necessário) -> Update DB -> Response`.
- [ ] Validar tratamento de erros (Ex: Site do órgão fora do ar ou CNPJ inválido).

---

## 4. Spec Técnica (Functional Spec)

### Endpoint da API
`GET /v1/compliance/am/{cnpj}`

### Payload de Resposta (Success 200)
```json
{
  "header": {
    "cnpj": "00000000000100",
    "region": "AM",
    "provider": "IPAAM",
    "queried_at": "2026-05-12T13:00:00Z"
  },
  "compliance": {
    "status": "CONFORME",
    "document": {
      "type": "Licença de Operação (L.O.)",
      "number": "123/2024",
      "expiry_date": "2026-12-31"
    },
    "analysis": {
      "is_valid": true,
      "days_to_expiry": 233,
      "alert_level": "LOW"
    }
  }
}