# Compliance Manaus — API de Conformidade Regulatória

POC de um SaaS para consulta automatizada de conformidade regulatória de empresas junto aos órgãos ambientais, sanitários e de registro profissional da região de Manaus/AM.

A API consulta portais públicos via scraping, persiste os resultados no PostgreSQL com cache de 24h e devolve um status padronizado (`CONFORME`, `ATENÇÃO` ou `NÃO CONFORME`) por CNPJ.

---

## Órgãos Suportados

| Órgão | Escopo | Endpoint |
| :--- | :--- | :--- |
| **IPAAM** | Licença de Operação Ambiental (L.O.) | `GET /v1/compliance/am/{cnpj}` |
| **FVS/DEVISA** | Licenciamento Sanitário Estadual | `GET /v1/compliance/am/{cnpj}/fvs` |
| **CREA-AM** | Registro de PJ e Responsável Técnico | `GET /v1/compliance/am/{cnpj}/crea` |

---

## Stack

| Camada | Tecnologia |
| :--- | :--- |
| API | Python 3.10+ · FastAPI · Uvicorn |
| Banco de dados | PostgreSQL 16 · SQLAlchemy 2 · psycopg3 |
| Scraping | requests · openpyxl · Playwright (headless Chromium) |
| Validação | Pydantic v2 |
| Infra local | Docker Compose |

---

## Pré-requisitos

- Python 3.10+
- Docker e Docker Compose

---

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/leirisson/compliance.git
cd compliance

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\Activate.ps1       # Windows (PowerShell)

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Instale o browser do Playwright (necessário para o scraper CREA-AM)
playwright install chromium

# 5. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env conforme necessário
```

---

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
| :--- | :--- | :--- |
| `DATABASE_URL` | Connection string do PostgreSQL | `postgresql+psycopg://compliance:compliance@db:5432/compliance_db` |
| `IPAAM_BASE_URL` | URL base do portal IPAAM | `https://sistemas.ipaam.am.gov.br` |
| `CACHE_TTL_HOURS` | Tempo de vida do cache (horas) | `24` |

---

## Executando

### Com Docker Compose (recomendado)

```bash
docker compose up --build
```

A API ficará disponível em `http://localhost:8000`.

### Localmente (sem Docker)

```bash
# Suba apenas o banco via Docker
docker compose up db -d

# Rode a API
uvicorn main:app --reload
```

---

## Endpoints

### `GET /v1/compliance/am/{cnpj}`

Consulta a Licença de Operação Ambiental no portal IPAAM.

### `GET /v1/compliance/am/{cnpj}/fvs`

Verifica enquadramento no Licenciamento Sanitário Estadual (FVS/DEVISA) pelo CNAE da empresa via ReceitaWS. Como o portal FVS não expõe base pública, o resultado indica se a empresa está **sujeita** ao licenciamento e qual sistema usar para consulta manual (SLIM em Manaus, SIGED no interior do AM).

### `GET /v1/compliance/am/{cnpj}/crea`

Consulta o Registro de Pessoa Jurídica no CREA-AM via SITAC (Playwright headless). Retorna situação do registro e lista de Responsáveis Técnicos vinculados.

**Parâmetro:** `cnpj` — 14 dígitos numéricos, com ou sem formatação.

**Erros:**

- `422` — CNPJ inválido.
- `503` — Órgão externo indisponível.

---

## Formato de Resposta

Estrutura comum a todos os endpoints:

```json
{
  "header": {
    "cnpj": "00000000000100",
    "region": "AM",
    "provider": "IPAAM",
    "queried_at": "2026-05-13T10:00:00Z",
    "cached": false
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
```

### Regras de status

| Status | Condição | `alert_level` |
| :--- | :--- | :--- |
| `CONFORME` | Validade > 90 dias | `LOW` |
| `ATENÇÃO` | Validade entre 1 e 90 dias | `MEDIUM` |
| `NÃO CONFORME` | Vencido ou não encontrado | `CRITICAL` |

---

## Estrutura do Projeto

```text
compliance/
├── api/
│   ├── routes.py          # Endpoints FastAPI
│   └── schemas.py         # Schemas Pydantic de request/response
├── db/
│   └── models.py          # Model SQLAlchemy (compliance_records)
├── scrapers/
│   ├── base.py            # Classe base para todos os scrapers
│   ├── ipaam.py           # Scraper IPAAM (Excel público)
│   ├── ibama.py           # Scraper IBAMA (CSV SISLIC)
│   ├── fvs.py             # Scraper FVS/DEVISA (CNAE via ReceitaWS)
│   └── crea_am.py         # Scraper CREA-AM (Playwright headless)
├── utils/
│   ├── date_parser.py     # Normalização de datas BR → ISO
│   └── compliance_rules.py # Lógica de status e alert_level
├── main.py                # Entrypoint da aplicação
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Documentação Interativa

Com a API rodando, acesse:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
