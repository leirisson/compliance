# Spec-Driven Development (SDD) - Projeto Compliance Manaus

Este documento define a especificação técnica para a Prova de Conceito (POC) do SaaS de consulta de conformidade regulatória, focado inicialmente em órgãos ambientais e sanitários da região de Manaus/AM.

---

## 1. Feature Specs

### SPEC-AM-001 — Motor de Consulta Regional (IPAAM)

**Escopo:** Automação de consulta no Instituto de Proteção Ambiental do Amazonas (IPAAM).

Desenvolver uma API em Python que realiza o scraping de dados no portal do IPAAM para validar a vigência de Licenças de Operação (L.O.) via CNPJ, consolidando os dados em um banco de dados PostgreSQL para histórico e auditoria.

### SPEC-AM-002 — Licenciamento Sanitário Estadual (FVS/DEVISA)

**Escopo:** Verificação de sujeição ao Licenciamento Sanitário Estadual do Amazonas pelo DEVISA/FVS-RCP.

O portal FVS não expõe base pública consultável por CNPJ. A estratégia adotada é:

1. Consultar a Receita Federal via ReceitaWS para obter os CNAEs da empresa.
2. Cruzar os CNAEs com a lista oficial de atividades fiscalizadas pelo DEVISA (Risco III), extraída do documento `4.Atividade-CNAE-DEVISA.pdf`.
3. Retornar se a empresa está sujeita ao licenciamento e direcionar para o sistema de consulta manual correto: **SLIM** (Manaus) ou **SIGED** (interior do AM).

### SPEC-AM-003 — Registro Profissional no CREA-AM

**Escopo:** Verificação de regularidade de registro profissional junto ao Conselho Regional de Engenharia e Agronomia do Amazonas (CREA-AM).

**Referência:** [CREA-AM — Emissão do Registro Profissional](https://crea-am.org.br/creaam_site/crea-am-tira-duvidas-sobre-a-emissao-do-registro-profissional-30883)

O CREA-AM é responsável pelo registro e fiscalização de profissionais e empresas das áreas de Engenharia, Agronomia e afins no Amazonas. Toda empresa que presta serviços técnicos nessas áreas é obrigada a possuir **Registro de Pessoa Jurídica (PJ)** no CREA, além da **Anotação de Responsabilidade Técnica (ART)** por profissional habilitado.

A estratégia adotada é:

1. Consultar o portal público de consulta de registros do **CFE/CREA** (sistema federal integrado) via CNPJ ou razão social.
2. Verificar o status do registro da empresa: **ATIVO**, **SUSPENSO**, **CANCELADO** ou **NÃO ENCONTRADO**.
3. Complementar com consulta ao portal do CREA-AM para validar jurisdição regional e listar os responsáveis técnicos vinculados.
4. Retornar se a empresa está em situação regular para execução de atividades técnicas regulamentadas no Amazonas.

**Documento-alvo:** Certidão de Registro e Quitação de Pessoa Jurídica (CRQPJ).

#### Mapeamento Técnico dos Portais

| Sistema | URL | Aceita CNPJ | Requer JS | Observação |
| :--- | :--- | :--- | :--- | :--- |
| SITAC CREA-AM (público) | `https://crea-am.sitac.com.br/app/view/sight/externo.php?form=PesquisarProfissionalEmpresa` | A confirmar | **Sim** | Endpoint público sem login; renderiza via JS |
| Portal de serviços CREA-AM | `http://servicos-crea-am.sitac.com.br/index.php` | A confirmar | **Sim** | Contém "Buscar Profissional/Empresa" sem login |
| Consulta Profissional CONFEA | `https://consultaprofissional.confea.org.br/` | **Não** (só CPF) | Não | Apenas PF: nome, CPF, nº registro nacional |
| Consulta Pública CONFEA | `https://consultapublica.confea.org.br/` | **Não** | Não | Portal de consultas normativas, não de registros |
| Registro Único CONFEA | `https://registrounico.confea.org.br/` | A confirmar | Sim | Potencial portal integrado PJ; conteúdo JS-only |

#### Estratégia de Scraping

O SITAC é uma **SPA renderizada por JavaScript** — requisições HTTP simples retornam apenas a página de compatibilidade de navegadores. A abordagem necessária é:

1. **Playwright (headless)** para renderizar o formulário em `externo.php?form=PesquisarProfissionalEmpresa`.
2. Preencher o campo de busca (presumivelmente CNPJ ou razão social) e submeter.
3. Aguardar carregamento dos resultados e extrair: situação do registro, número, data, e lista de RTs vinculados.
4. Capturar screenshot como evidência de auditoria (R5).

> **Obstáculo previsto:** O SITAC pode bloquear User-Agents não-browser. Usar `playwright` com `user_agent` de Chrome real e `headless=True`. Se houver CAPTCHA, escalar para `headless=False` com intervenção manual ou serviço de resolução.

#### Campos de busca a validar (inspeção manual necessária)

- [ ] Confirmar se o formulário aceita **CNPJ** (não apenas CPF ou nome) como parâmetro de busca de empresa.
- [ ] Identificar o `name` dos inputs e o endpoint do POST/XHR via DevTools (Network tab).
- [ ] Verificar se o resultado detalha **Responsáveis Técnicos** ou apenas status do registro PJ.

---

## 2. Regras de Negócio (Rules)

| ID | Regra | Descrição |
| :--- | :--- | :--- |
| **R1** | **Regionalidade** | O sistema deve priorizar seletores e fluxos específicos para os portais dos órgãos do Amazonas. |
| **R2** | **Normalização de Data** | Toda data extraída (ex: `30/06/2026`) deve ser convertida para o padrão ISO `YYYY-MM-DD` antes da persistência. |
| **R3** | **Lógica de Conformidade** | **CONFORME**: Validade > 90 dias. **ATENÇÃO**: Validade entre 1 e 90 dias. **NÃO CONFORME**: Data vencida ou licença não encontrada. |
| **R4** | **Política de Cache** | Se houver uma consulta no Postgres para o mesmo CNPJ realizada há menos de 24h, retornar o dado local e evitar novo scraping. |
| **R5** | **Evidência de Auditoria** | O sistema deve capturar o log da tabela extraída e, se possível, o link do documento oficial para fins de prova. |
| **R6** | **Enquadramento Sanitário** | Para órgãos sem base pública (ex: FVS/DEVISA), determinar sujeição ao licenciamento pelo CNAE da empresa e indicar o sistema de consulta manual adequado. |
| **R7** | **Registro CREA** | Toda empresa que executa atividades técnicas regulamentadas (Engenharia, Agronomia e afins) no AM deve possuir Registro de PJ ativo no CREA-AM. A verificação é obrigatória para qualificação de fornecedores dessas áreas. |
| **R8** | **Responsável Técnico** | O registro de PJ no CREA só é válido se houver ao menos um profissional com registro individual ativo vinculado como Responsável Técnico (RT). A ausência de RT implica status `NÃO CONFORME`. |

---

## 3. Lista de Tarefas (Text Tasks)

### Fase A: Infraestrutura e Dados

- [x] Configurar ambiente virtual Python 3.10+ e instalar dependências (`fastapi`, `sqlalchemy`, `psycopg2-binary`).
- [x] Criar arquivo `docker-compose.yml` para subir instância local do **PostgreSQL**.
- [x] Definir Model SQLAlchemy para a tabela `compliance_records`.

### Fase B: Scrapers

- [x] Implementar a classe base `BaseScraper`.
- [x] Implementar `IpaamScraper` — busca LO nas planilhas Excel públicas do IPAAM.
- [x] Implementar `IbamaScraper` — busca licenças no CSV público SISLIC/IBAMA.
- [x] Implementar `FvsScraper` — verifica enquadramento DEVISA pelo CNAE via ReceitaWS.
- [x] Implementar utilitário de parser para conversão de datas brasileiras em objetos `datetime`.

### Fase B2: Scraper CREA-AM (SPEC-AM-003)

- [x] Mapear endpoints públicos do sistema CONFEA/CREA disponíveis para consulta por CNPJ.
- [x] Validar manualmente via DevTools: campos confirmados — `name="TIPOPESSOA" value="2"` (radio EMPRESA) e `id="CNPJ"` (input CNPJ).
- [x] Adicionar dependência `playwright` e instalar browsers (`playwright install chromium`).
- [x] Implementar `CreaAmScraper` com Playwright headless — preenche formulário SITAC e extrai resultado.
- [x] Implementar lógica de status: cruzar situação do registro PJ (`ATIVO/SUSPENSO/CANCELADO`) com presença de RT ativo.
- [x] Implementar extração da Certidão de Registro e Quitação (CRQPJ): número, validade e situação.

### Fase C: API e Integração

- [x] Criar endpoint `GET /v1/compliance/am/{cnpj}` (IPAAM).
- [x] Criar endpoint `GET /v1/compliance/am/{cnpj}/fvs` (FVS/DEVISA).
- [x] Criar endpoint `GET /v1/compliance/am/{cnpj}/crea` (CREA-AM).
- [x] Implementar lógica de cache: `Verificar Cache → Executar Scraper → Persistir → Responder`.
- [x] Validar tratamento de erros (CNPJ inválido, órgão indisponível).

---

## 4. Spec Técnica (Functional Spec)

### Endpoints da API

| Método | Endpoint | Órgão | Descrição |
| :--- | :--- | :--- | :--- |
| `GET` | `/v1/compliance/am/{cnpj}` | IPAAM | Licença de Operação Ambiental |
| `GET` | `/v1/compliance/am/{cnpj}/fvs` | FVS/DEVISA | Licenciamento Sanitário Estadual |
| `GET` | `/v1/compliance/am/{cnpj}/crea` | CREA-AM | Registro de PJ e Responsável Técnico |

**Parâmetro:** `cnpj` — 14 dígitos numéricos (com ou sem formatação).

**Erros:**

- `422` — CNPJ inválido.
- `503` — Órgão externo indisponível.

---

### Payload de Resposta (200 OK)

Estrutura comum a todos os endpoints:

```json
{
  "header": {
    "cnpj": "00000000000100",
    "region": "AM",
    "provider": "IPAAM | FVS/DEVISA | IBAMA",
    "queried_at": "2026-05-13T10:00:00Z",
    "cached": false
  },
  "compliance": {
    "status": "CONFORME | ATENÇÃO | NÃO CONFORME",
    "document": {
      "type": "Licença de Operação (L.O.) | Licença Sanitária Estadual",
      "number": "123/2024",
      "expiry_date": "2026-12-31"
    },
    "analysis": {
      "is_valid": true,
      "days_to_expiry": 233,
      "alert_level": "LOW | MEDIUM | CRITICAL"
    }
  }
}
```

**Regras de `alert_level`:**

| Valor | Condição |
| :--- | :--- |
| `LOW` | Status `CONFORME` (validade > 90 dias) |
| `MEDIUM` | Status `ATENÇÃO` (validade entre 1 e 90 dias) |
| `CRITICAL` | Status `NÃO CONFORME` (vencido ou não encontrado) |

---

### Exemplo — IPAAM (200 OK)

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

### Exemplo — FVS/DEVISA (200 OK)

O campo `raw_payload` (armazenado internamente) contém os detalhes do enquadramento sanitário:

```json
{
  "header": {
    "cnpj": "36289472000153",
    "region": "AM",
    "provider": "FVS/DEVISA",
    "queried_at": "2026-05-13T10:00:00Z",
    "cached": false
  },
  "compliance": {
    "status": "NÃO CONFORME",
    "document": {
      "type": "Licença Sanitária Estadual",
      "number": null,
      "expiry_date": null
    },
    "analysis": {
      "is_valid": false,
      "days_to_expiry": null,
      "alert_level": "CRITICAL"
    }
  }
}
```

> **Nota FVS/DEVISA:** A licença sanitária não é consultável por CNPJ em base pública. O campo `payload_extraido` no banco de dados registra o CNAE da empresa, se está sujeita ao DEVISA e o sistema de consulta manual indicado (SLIM para Manaus, SIGED para o interior do AM).

### Exemplo — CREA-AM (200 OK)

O endpoint retorna o status do Registro de PJ e informações dos Responsáveis Técnicos vinculados:

```json
{
  "header": {
    "cnpj": "00000000000100",
    "region": "AM",
    "provider": "CREA-AM",
    "queried_at": "2026-05-13T10:00:00Z",
    "cached": false
  },
  "compliance": {
    "status": "CONFORME",
    "document": {
      "type": "Certidão de Registro e Quitação de Pessoa Jurídica (CRQPJ)",
      "number": "AM-12345/2024",
      "expiry_date": "2026-12-31"
    },
    "analysis": {
      "is_valid": true,
      "days_to_expiry": 233,
      "alert_level": "LOW"
    }
  },
  "details": {
    "registro_pj": {
      "situacao": "ATIVO",
      "numero_registro": "AM-12345",
      "data_registro": "2020-03-15"
    },
    "responsaveis_tecnicos": [
      {
        "nome": "João da Silva",
        "titulo": "Engenheiro Civil",
        "registro_crea": "AM-9999",
        "situacao": "ATIVO"
      }
    ]
  }
}
```

> **Nota CREA-AM:** O registro de PJ é considerado `NÃO CONFORME` se a situação for `SUSPENSO` ou `CANCELADO`, ou se não houver nenhum Responsável Técnico com registro individual `ATIVO` vinculado (R8). O campo `details` é armazenado no `raw_payload` para fins de auditoria.
