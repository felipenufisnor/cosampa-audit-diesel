# audit-diesel — POC de auditoria automatizada de diesel

POC para o consorcio **CLC / Rocha / Cosampa (ARCO Metropolitano JP)**. Demonstra
como agentes deterministicos cruzam quatro sistemas (GLPI, Gestao de Projetos,
Infleet, Auditoria Diesel) e identificam inconsistencias de abastecimento que
hoje sao tratadas em planilhas Excel.

## Status atual

- **Etapa 1 (concluido)**: ingestao + engine determinista + CLI.
- **Etapa 2 (concluido)**: camada de IA provider-agnostica (OpenAI-compatible) +
  FastAPI + frontend Next.js com dashboard e tela de auditoria.
- **Etapa 3 (concluido)**: gerador de PDF (WeasyPrint+Jinja2), tela `/consolidado`
  cross-NF, modo `DEMO_MODE` com cache em disco para resiliencia da
  apresentacao, polimento visual e roteiro de demo em `docs/roteiro_demo.md`.

Decisoes arquiteturais ficam registradas em [`docs/adr/`](docs/adr/).

## Stack

Backend:
- Python 3.11+, gerenciado via [uv](https://docs.astral.sh/uv/).
- pandas + openpyxl para ingestao de xlsx.
- SQLModel sobre SQLite local (`backend/data/audit.db`).
- click + rich para CLI; FastAPI + uvicorn para a API.
- SDK `openai` apontando para qualquer endpoint OpenAI-compatible
  (OpenRouter, Together, Groq, Ollama, vLLM). Sem dependencia de Anthropic.
- tenacity (retry com backoff) + structlog (JSON logs).
- pytest (83 testes verdes).

Frontend (Dia 2):
- Next.js 16 (App Router) + TypeScript + Tailwind v4 (light-mode only, sem
  dark mode, sem emojis).
- @tanstack/react-query para fetch/cache; zustand para estado de UI.
- lucide-react usado com parcimonia; sonner para toasts; react-markdown
  para renderizar o parecer.

## Estrutura

```
audit-diesel-poc/
|-- README.md
|-- .gitignore
+-- backend/
    |-- pyproject.toml
    |-- .env.example
    |-- scripts/postsync.sh
    |-- data/
    |   |-- raw/                       # xlsx originais (gitignored)
    |   +-- audit.db                   # gerado pela ingestao (gitignored)
    |-- src/audit_diesel/
    |   |-- config.py
    |   |-- models.py
    |   |-- ingestion/                 # normalizers, infleet, mobilizados, checklist, pipeline
    |   |-- audit/
    |   |   |-- indicators.py          # formulas §4 do escopo
    |   |   |-- alerts/                # 4 checagens deterministicas
    |   |   +-- engine.py
    |   +-- cli.py
    +-- tests/                         # 69 testes
```

## Setup

```bash
cd backend
uv sync --extra dev
# Copie os xlsx do cliente para data/raw/ caso ainda nao estejam la:
#   listagem_de_chamados___recebimento_de_diesel_ARCO JP.xlsx
#   relatorio_mobilizados_ARCO JP.xlsx
#   Infleet - Abastecimentos_ARCO JP.xlsx
```

### Dependencias nativas para o PDF (WeasyPrint)

WeasyPrint precisa de pango, cairo, gdk-pixbuf e libffi instalados no
sistema. No macOS:

```bash
brew install pango cairo gdk-pixbuf libffi
# Depois, em comandos que disparam WeasyPrint, anteponha o DYLD path:
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn audit_diesel.api.main:app
```

No Linux (Debian/Ubuntu):

```bash
apt install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0
# Sem export adicional necessario.
```

> **Nota macOS**: se ao rodar `uv run audit-diesel ...` aparecer
> `ModuleNotFoundError: No module named 'audit_diesel'`, e porque o uv marcou os
> arquivos `.pth` da venv como UF_HIDDEN. Rode `bash scripts/postsync.sh` (faz
> `chflags nohidden`) e tente de novo. O `tool.uv.package = true` no
> `pyproject.toml` ja minimiza a chance de isso acontecer; o script existe como
> rede de seguranca.

## Comandos da CLI

```bash
# 1) Ingere os 3 xlsx de data/raw/ no SQLite (idempotente):
uv run audit-diesel ingest

# 2) Lista as NFs disponiveis para auditar:
uv run audit-diesel listar-nfs

# 3) Roda a auditoria entre duas NFs sequenciais:
uv run audit-diesel auditar --nf-anterior 8108 --nf-atual 8187

# 4) Mesma auditoria, mas em JSON (consumo programatico, p.ex. pelo front no Dia 2):
uv run audit-diesel auditar --nf-anterior 8108 --nf-atual 8187 --json > out.json

# 5) Estatisticas globais do banco:
uv run audit-diesel stats
```

## Indicadores (escopo §4)

```
estoque_inicial_anterior        = tanque_anterior + comboio_anterior
estoque_final_teorico_anterior  = estoque_inicial_anterior + quantidade_descarregada_anterior
estoque_inicial_atual           = tanque_atual + comboio_atual
saida_teorica                   = estoque_final_teorico_anterior - estoque_inicial_atual
saidas_registradas              = sum(quantidade_litros) na janela [fim_descarga_anterior, fim_descarga_atual)
diferenca                       = saidas_registradas - saida_teorica
diferenca_pct                   = diferenca / saida_teorica
```

Regra de validacao final (§4.4): `APROVADO` se `abs(diferenca_pct) < 2%` **e**
nenhum equipamento nao cadastrado; senao `INCONSISTENTE`.

> TODO de validacao com cliente: o escopo §4.1 cita "Quantidade Descarregada"
> como sinonimo da quantidade da NF; usamos `quantidade_nf_litros`. Confirmar
> se ha cenarios em que `volume_conferido` deve substituir esse campo.

## Alertas implementados

| Tipo             | Severidade | Disparo                                                           |
|------------------|------------|-------------------------------------------------------------------|
| `NAO_CADASTRADO` | alta       | abastecimento de placa sem cadastro no GP                         |
| `POS_DESMOB`     | alta       | abastecimento com data > `data_desmobilizacao` do equipamento     |
| `OUTLIER`        | media      | z-score >3 do consumo do veiculo (n>=5 obs no historico)          |
| `DUPLICIDADE`    | baixa      | dois ou mais abastecimentos do mesmo veiculo no mesmo dia         |

## Sobre `AUDITORIA - DIESEL - REV04_ARCO JP.xlsx`

Inspecionado e descartado da ingestao automatica. As abas `Checklist`, `CTA`,
`Infleet` e `GP` duplicam (parcial e desatualizadamente) os outros tres
arquivos; `CTA` esta vazia neste dataset; e `Auditoria`, `Controle de
Combustiveis` e `Previsao` sao templates internos sem dados-fonte. A POC le
direto das fontes originais.

## API HTTP (Dia 2)

```bash
cd backend
AUDIT_AI_OFFLINE=1 uv run uvicorn audit_diesel.api.main:app --port 8001
# Docs: http://localhost:8001/docs
```

Endpoints principais (todos documentados via OpenAPI):

| Metodo + path                          | Resumo |
|----------------------------------------|--------|
| `GET  /healthz`                        | Status do DB e do provider de LLM |
| `GET  /stats`                          | Numeros agregados do dashboard |
| `GET  /nfs`                            | Listagem de NFs com ultima auditoria |
| `GET  /nfs/{nota_fiscal}`              | Detalhe + historico |
| `POST /auditorias`                     | Roda engine + parecer da IA |
| `GET  /auditorias/{id}`                | Recupera auditoria persistida |
| `POST /reconciliacao/sugerir`          | Pede sugestoes de match para nao-cadastrados |
| `POST /reconciliacao/aprovar`          | Vincula abastec.->mobilizado, re-roda auditoria |
| `GET  /auditorias/{id}/pdf`            | Gera PDF oficial da auditoria (WeasyPrint) |
| `GET  /auditorias/consolidado`         | Resumo cross-NF com agregados + alertas resumidos |
| `GET  /auditorias/consolidado.csv`     | Mesmo conteudo em CSV (BOM UTF-8 para Excel) |

Curl realmente executado contra o backend (modo offline) esta em
`backend/scripts/manual_test.http`.

## Camada de IA

Provider-agnostica: o codigo fala dialeto **OpenAI Chat Completions**, com
`base_url` e `api_key` configuraveis. Compatibilidade futura com LangChain /
Vercel AI SDK / LiteLLM eh natural porque todos seguem essa interface.

Configuracao via `.env` (modelos exemplares):

```
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=...
LLM_MODEL=qwen/qwen3-32b
LLM_FALLBACK_MODEL=
LLM_REQUEST_TIMEOUT_S=60
LLM_MAX_RETRIES=3
AUDIT_AI_OFFLINE=1     # forca uso de fixtures determinisicas (sem rede)
```

Dois servicos em cima do client:

- **ReconciliadorSemantico** (`audit_diesel.ai.reconciliador`): batches de
  ate 20 abastecimentos por chamada, candidatos pre-filtrados por obra +
  identificador, output via tool calling (`registrar_sugestoes`) com schema
  JSON estrito validado por pydantic.
- **GeradorParecer** (`audit_diesel.ai.parecer`): markdown estruturado em 4
  blocos (Resultado / Causa mais provavel / Recomendacao / Risco financeiro),
  <= 220 palavras, pt-BR tecnico.

Modo offline usa fixtures que mimetizam um modelo Qwen razoavel (matching
deterministico baseado em normalizacao de identificadores e em substring de
apelido x equipamento). Usado em desenvolvimento e em CI; basta zerar
`AUDIT_AI_OFFLINE` e setar `LLM_API_KEY` para chavear para um provider real.

### Pareceres reais nas 3 NFs auditaveis

Saida completa em `backend/scripts/pareceres_3nfs.txt`. Exemplo (8108 -> 8187):

```
**Resultado**
INCONSISTENTE: diferenca de +0.39% entre saidas Infleet e saida teorica;
36 equipamento(s) sem cadastro no GP.

**Causa mais provavel**
Situacao 3 (alta quantidade de nao-cadastrados). 36 abastecimentos da
janela ocorreram em equipamentos sem cadastro correspondente no GP,
dominando o sinal de inconsistencia (diferenca de 71.7 L / +0.39%).

**Recomendacao ao auditor**
1. Cobre a insercao no GP dos 36 equipamento(s) abastecido(s) sem cadastro
   durante a janela.
2. Solicite a obra a relacao de saidas de comboio nao registradas no
   Infleet entre o descarregamento da NF anterior e a NF 8187.
3. Confirme com o estoquista os valores de tanque e comboio informados no
   checklist da NF 8187 antes de fechar o mes.

**Risco financeiro associado**
R$ 32.924,16 em alertas de alta severidade na janela (custo dos
abastecimentos nao cadastrados e pos-desmobilizacao).
```

## Frontend (Dia 2)

```bash
cd frontend
cp .env.local.example .env.local           # NEXT_PUBLIC_API_URL=http://localhost:8001
pnpm install
pnpm dev                                   # http://localhost:3000
pnpm build                                 # producao
pnpm lint                                  # ESLint estrito
```

Telas:
- `/` — Dashboard com 4 stat-cards (Total abastecido, Custo nao cadastrado,
  NFs no periodo, Equipamentos cadastrados) + tabela das 4 NFs com badges
  de status. "Auditar" abre modal pra escolher a NF anterior; ao confirmar,
  navega para `/auditoria/[id]` em ate ~2s.
- `/auditoria/[id]` — Janela temporal NF anterior -> atual; bloco de
  indicadores §4 com layout fiel a planilha original (duas colunas
  comparando NF anterior vs atual, e bloco com saida teorica / saidas
  registradas / diferenca); lista de alertas filtravel por tipo,
  ordenavel por severidade ou impacto financeiro; sidebar fixa com o
  parecer da IA renderizado em markdown.
- Modal de Reconciliacao — disparado pelo botao "Reconciliar" num alerta
  "Nao cadastrado". Lista sugestoes da IA com badge de confianca
  (verde >=0.85 / ambar 0.65-0.84 / cinza < 0.65). Ao aprovar, fecha o
  modal, faz re-fetch automatico da auditoria via react-query e os
  contadores caem (engine reusa o vinculo aprovado como "cadastro virtual").

## Dia 3: PDF, visao consolidada e DEMO_MODE

### Gerador de PDF

`GET /auditorias/{id}/pdf` retorna `application/pdf` com nome
`auditoria_NF_{nf_atual}_{YYYYMMDD}.pdf`. Layout em A4 retrato, com:

- Bloco de identificacao (obra, fornecedor, data, NF, valores).
- Bloco de indicadores §4 com layout fiel a aba "AUDITORIA DO DIESEL_0"
  da planilha original (duas colunas comparando NF anterior vs atual).
- Bloco de validacao final em destaque (APROVADO / INCONSISTENTE).
- Tabela de alertas agrupada por tipo, severidade em peso (B&W safe).
- Bloco "Parecer Tecnico — IA" com markdown convertido em HTML simples.
- Lista de reconciliacoes aprovadas no ciclo, com auditor, timestamp e
  justificativa.
- Rodape com paginacao + hash sha256 dos indicadores (rastreabilidade).

Templates em `backend/src/audit_diesel/api/templates/`. Render em
`backend/src/audit_diesel/api/pdf.py`. Decisoes em
[`docs/adr/0003-pdf-via-weasyprint.md`](docs/adr/0003-pdf-via-weasyprint.md).

### Tela `/consolidado`

Visao cross-NF com 6 stats cards (Total auditado, Diferenca total
detectada, Total de alertas, Aprovadas, Inconsistentes, Reconciliacoes
pendentes) e tabela com todas as 4 NFs (filtros por status, busca por
NF/obra, ordenacao por qualquer coluna numerica). Botao "Exportar CSV"
chama `/auditorias/consolidado.csv`.

### DEMO_MODE (resiliencia da apresentacao)

Tres modos via env var `DEMO_MODE`:

| Valor    | Comportamento |
| -------- | ------------- |
| `off`    | (default) Sem cache. Chama o provider de LLM normalmente. |
| `record` | Chama o provider e GRAVA cada resposta em `data/demo_cache/`. |
| `true`   | LE do `data/demo_cache/`; cai pro provider em cache miss. |

Cache file naming:
```
data/demo_cache/parecer_NF_{nf_atual}_anterior_{nf_anterior}.json
data/demo_cache/reconciliacao_par_{nf_atual}_anterior_{nf_anterior}.json
```

#### Popular o cache (uma vez antes da demo)

```bash
cd backend
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  AUDIT_AI_OFFLINE=1 DEMO_MODE=record \
  uv run python scripts/popular_cache_demo.py
```

O script:
1. Roda as 3 auditorias da demo (8108→8187, 8187→8278, 8278→8328).
2. Gera parecer + sugestoes de reconciliacao usando o offline provider.
3. Persiste cada resposta em `data/demo_cache/`.
4. Gera os PDFs amostra em `data/pdfs_amostra/`.

Tempo total: ~1.4s. Idempotente (sobrescreve o cache).

#### Rodar a demo em modo replay

```bash
cd backend
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  AUDIT_AI_OFFLINE=1 DEMO_MODE=true \
  uv run uvicorn audit_diesel.api.main:app --port 8000
```

Verifique `curl http://localhost:8000/healthz` retornando
`"demo_mode": true`. O frontend exibira um badge discreto "Modo
demonstracao" no canto inferior direito enquanto este modo estiver
ativo.

### Screenshots para o roteiro

Capturas a serem feitas (a sugestao e zoom 110% no Chrome, viewport
~1440x900) — guarde em `docs/screenshots/`:

1. `01_dashboard.png` — Tela `/` com os 4 stats cards e tabela das NFs.
2. `02_auditoria_indicadores.png` — Tela `/auditoria/{id}` mostrando o
   bloco de indicadores §4 e o parecer da IA na coluna direita.
3. `03_auditoria_alertas.png` — Mesma tela, rolada ate a lista de
   alertas, com um alerta de tipo NAO_CADASTRADO em foco.
4. `04_modal_reconciliacao.png` — Modal de reconciliacao aberto, com
   sugestoes e seus chips de confianca.
5. `05_pdf_pagina_1.png` — Captura do PDF aberto numa nova aba (apenas
   a primeira pagina, mostrando indicadores + validacao).
6. `06_consolidado.png` — Tela `/consolidado` com filtro "todas",
   mostrando os 6 stats cards e a tabela das 4 NFs.

## Testes

```bash
cd backend
uv run pytest          # 83 testes, ~5s
```

## Output de referencia (NF 8108 -> NF 8187)

- Janela: 05/03/2026 10:10 -> 13/03/2026 08:50
- Saida teorica: 18.270,30 L
- Saidas registradas (Infleet): 18.342,00 L
- Diferenca: +71,70 L (+0,39%)
- Equipamentos nao cadastrados: 36
- Validacao final: **INCONSISTENTE**
- Alertas: 38 (36 NAO_CADASTRADO + 1 OUTLIER + 1 DUPLICIDADE)
