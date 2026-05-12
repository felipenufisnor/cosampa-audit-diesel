# audit-diesel — POC de auditoria automatizada de diesel

POC para o consórcio **CLC / Rocha / Cosampa (ARCO Metropolitano JP)**. Demonstra
como agentes determinísticos cruzam quatro sistemas (GLPI, Gestão de Projetos,
Infleet, Auditoria Diesel) e identificam inconsistências de abastecimento que
hoje são tratadas em planilhas Excel.

## Status atual

- **Etapa 1 (concluído)**: ingestão + engine determinista + CLI.
- **Etapa 2 (concluído)**: camada de IA provider-agnóstica (OpenAI-compatible) +
  FastAPI + frontend Next.js com dashboard e tela de auditoria.
- **Etapa 3 (concluído)**: gerador de PDF (WeasyPrint+Jinja2), tela `/consolidado`
  cross-NF, modo `DEMO_MODE` com cache em disco para resiliência da
  apresentação, polimento visual e roteiro de demo em `docs/roteiro_demo.md`.

Decisões arquiteturais ficam registradas em [`docs/adr/`](docs/adr/).

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

Frontend:
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
    |   +-- audit.db                   # gerado pela ingestão (gitignored)
    |-- src/audit_diesel/
    |   |-- config.py
    |   |-- models.py
    |   |-- ingestion/                 # normalizers, infleet, mobilizados, checklist, pipeline
    |   |-- audit/
    |   |   |-- indicators.py          # formulas §4 do escopo
    |   |   |-- alerts/                # 4 checagens determinísticas
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

# 4) Mesma auditoria, mas em JSON (consumo programático, p.ex. pelo front):
uv run audit-diesel auditar --nf-anterior 8108 --nf-atual 8187 --json > out.json

# 5) Estatísticas globais do banco:
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

Regra de validação final (§4.4): `APROVADO` se `abs(diferenca_pct) < 2%` **e**
nenhum equipamento não cadastrado; senão `INCONSISTENTE`.

> TODO de validação com cliente: o escopo §4.1 cita "Quantidade Descarregada"
> como sinônimo da quantidade da NF; usamos `quantidade_nf_litros`. Confirmar
> se há cenários em que `volume_conferido` deve substituir esse campo.

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

## API HTTP

```bash
cd backend
AUDIT_AI_OFFLINE=0 DEMO_MODE=off uv run uvicorn audit_diesel.api.main:app --port 8001
# Docs: http://localhost:8001/docs
```

Endpoints principais (todos documentados via OpenAPI):

| Metodo + path                          | Resumo |
|----------------------------------------|--------|
| `GET  /healthz`                        | Status do DB e do provider de LLM |
| `GET  /stats`                          | Números agregados do dashboard |
| `GET  /nfs`                            | Listagem de NFs com última auditoria |
| `GET  /nfs/{nota_fiscal}`              | Detalhe + histórico |
| `POST /auditorias`                     | Roda engine + parecer da IA |
| `GET  /auditorias/{id}`                | Recupera auditoria persistida |
| `POST /reconciliacao/sugerir`          | Pede sugestões de match para não cadastrados |
| `POST /reconciliacao/aprovar`          | Vincula abastecimento a mobilizado e re-roda a auditoria |
| `GET  /auditorias/{id}/pdf`            | Gera PDF oficial da auditoria (WeasyPrint) |
| `GET  /auditorias/consolidado`         | Resumo cross-NF com agregados + alertas resumidos |
| `GET  /auditorias/consolidado.csv`     | Mesmo conteúdo em CSV (BOM UTF-8 para Excel) |

Curl de referência executado contra o backend em modo offline está em
`backend/scripts/manual_test.http`.

## Camada de IA

Provider-agnóstica: o código fala dialeto **OpenAI Chat Completions**, com
`base_url` e `api_key` configuráveis. Compatibilidade futura com LangChain /
Vercel AI SDK / LiteLLM é natural porque todos seguem essa interface.

Configuracao via `.env` (modelos exemplares):

```
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=...
LLM_MODEL=qwen/qwen3-32b
LLM_FALLBACK_MODEL=deepseek/deepseek-chat
LLM_REQUEST_TIMEOUT_S=60
LLM_MAX_RETRIES=3
AUDIT_AI_OFFLINE=0     # tenta provider real quando LLM_API_KEY estiver preenchida
DEMO_MODE=off          # modo demonstracao e opt-in
```

Sem `LLM_API_KEY`, o backend sinaliza `assistant_status=missing_key` e o
Assistente desabilita perguntas livres. Se houver cache local por janela de NF,
as perguntas sugeridas continuam funcionando como modo degradado. Para forcar
zero rede, use `AUDIT_AI_OFFLINE=1`.

### Runbook: IA real com OpenRouter

Use `backend/.env.openrouter.example` como base e copie para `backend/.env`.
Nunca commite chaves; se uma chave aparecer em chat, print ou log, rotacione
antes de usar em ambiente real.

Modo padrao com IA real, recomendado para desenvolvimento integrado e
calibracao Qwen/DeepSeek:

```bash
AUDIT_AI_OFFLINE=0 DEMO_MODE=off \
LLM_PROVIDER=openrouter \
LLM_BASE_URL=https://openrouter.ai/api/v1 \
LLM_API_KEY=<rotated_openrouter_key> \
LLM_MODEL=qwen/qwen3-32b \
LLM_FALLBACK_MODEL=deepseek/deepseek-chat \
  uv run uvicorn audit_diesel.api.main:app --port 8000
```

Modo demo/offline, recomendado para apresentação e CI:

```bash
AUDIT_AI_OFFLINE=1 DEMO_MODE=true \
  uv run uvicorn audit_diesel.api.main:app --port 8000
```

Confirme o estado em `GET /healthz`:

- `assistant_status=available`: provider real respondeu ao probe e perguntas
  livres estao habilitadas.
- `assistant_status=degraded_cache`: provider falhou, mas ha respostas
  pre-carregadas para uso parcial.
- `assistant_status=missing_key`: `LLM_API_KEY` nao foi configurada para
  provider remoto.
- `assistant_status=offline_fixture`: sem rede por configuracao
  (`AUDIT_AI_OFFLINE=1`).
- `assistant_status=provider_error`: provider configurado, mas indisponivel e
  sem cache local.
- `model`: modelo primário ativo; `fallback_model`: fallback configurado.

Smoke test do assistente real:

```bash
curl -s http://localhost:8000/healthz | jq '{
  assistant_status,
  assistant_reason,
  assistant_can_answer_free_text,
  assistant_has_cached_answers
}'

curl -N -X POST http://localhost:8000/auditorias/1/perguntar \
  -H 'Content-Type: application/json' \
  -d '{"pergunta":"Qual o principal risco desta auditoria?"}'
```

Smoke/calibração real:

```bash
cd backend
AUDIT_AI_OFFLINE=0 DEMO_MODE=off LLM_API_KEY=<rotated_openrouter_key> \
  uv run python scripts/calibrar_llm_real.py
```

O relatório sai em `backend/data/llm_calibration/` (gitignored), com latência,
tokens, validação dos guardrails e contagem de sugestões sem match.

Dois serviços em cima do client:

- **ReconciliadorSemantico** (`audit_diesel.ai.reconciliador`): batches de
  até 20 abastecimentos por chamada, candidatos pré-filtrados por obra +
  identificador, output via tool calling (`registrar_sugestoes`) com schema
  JSON estrito validado por pydantic.
- **GeradorParecer** (`audit_diesel.ai.parecer`): markdown estruturado em 4
  blocos (Resultado / Causa mais provável / Recomendação / Risco financeiro),
  <= 220 palavras, pt-BR técnico.

Modo offline usa fixtures que mimetizam um modelo Qwen razoável (matching
determinístico baseado em normalização de identificadores e em substring de
apelido x equipamento). Usado em desenvolvimento e em CI; basta zerar
`AUDIT_AI_OFFLINE` e setar `LLM_API_KEY` para chavear para um provider real.

### Pareceres reais nas 3 NFs auditáveis

Saída completa em `backend/scripts/pareceres_3nfs.txt`. Exemplo (8108 -> 8187):

```
**Resultado**
INCONSISTENTE: diferença de +0.39% entre saídas Infleet e saída teórica;
36 equipamento(s) sem cadastro no GP.

**Causa mais provável**
Situação 3 (alta quantidade de não cadastrados). 36 abastecimentos da
janela ocorreram em equipamentos sem cadastro correspondente no GP,
dominando o sinal de inconsistência (diferença de 71.7 L / +0.39%).

**Recomendação ao auditor**
1. Cobre a inserção no GP dos 36 equipamento(s) abastecido(s) sem cadastro
   durante a janela.
2. Solicite à obra a relação de saídas de comboio não registradas no
   Infleet entre o descarregamento da NF anterior e a NF 8187.
3. Confirme com o estoquista os valores de tanque e comboio informados no
   checklist da NF 8187 antes de fechar o mês.

**Risco financeiro associado**
R$ 32.924,16 em alertas de alta severidade na janela (custo dos
abastecimentos não cadastrados e pós-desmobilização).
```

## Frontend

```bash
cd frontend
cp .env.local.example .env.local           # NEXT_PUBLIC_API_URL=http://localhost:8001
pnpm install
pnpm dev                                   # http://localhost:3000
pnpm build                                 # producao
pnpm lint                                  # ESLint estrito
```

Telas:
- `/` — Dashboard com 4 stat-cards (Total abastecido, Custo não cadastrado,
  NFs no período, Equipamentos cadastrados) + tabela das 4 NFs com badges
  de status. "Auditar" abre modal pra escolher a NF anterior; ao confirmar,
  navega para `/auditoria/[id]` em até ~2s.
- `/auditoria/[id]` — Janela temporal NF anterior -> atual; bloco de
  indicadores §4 com layout fiel à planilha original (duas colunas
  comparando NF anterior vs atual, e bloco com saída teórica / saídas
  registradas / diferença); lista de alertas filtrável por tipo,
  ordenável por severidade ou impacto financeiro; sidebar fixa com o
  parecer da IA renderizado em markdown.
- Modal de Reconciliação — disparado pelo botão "Reconciliar" num alerta
  "Não cadastrado". Lista sugestões da IA com badge de confiança
  (verde >=0.85 / ambar 0.65-0.84 / cinza < 0.65). Ao aprovar, fecha o
  modal, faz re-fetch automático da auditoria via react-query e os
  contadores caem (engine reusa o vínculo aprovado como "cadastro virtual").

## PDF, visão consolidada e DEMO_MODE

### Gerador de PDF

`GET /auditorias/{id}/pdf` retorna `application/pdf` com nome
`auditoria_NF_{nf_atual}_{YYYYMMDD}.pdf`. Layout em A4 retrato, com:

- Bloco de identificação (obra, fornecedor, data, NF, valores).
- Bloco de indicadores §4 com layout fiel à aba "AUDITORIA DO DIESEL_0"
  da planilha original (duas colunas comparando NF anterior vs atual).
- Bloco de validação final em destaque (APROVADO / INCONSISTENTE).
- Tabela de alertas agrupada por tipo, severidade em peso (B&W safe).
- Bloco "Parecer Técnico — IA" com markdown convertido em HTML simples.
- Lista de reconciliações aprovadas no ciclo, com auditor, timestamp e
  justificativa.
- Rodapé com paginação + hash sha256 dos indicadores (rastreabilidade).

Templates em `backend/src/audit_diesel/api/templates/`. Render em
`backend/src/audit_diesel/api/pdf.py`. Decisões em
[`docs/adr/0003-pdf-via-weasyprint.md`](docs/adr/0003-pdf-via-weasyprint.md).

### Tela `/consolidado`

Visão cross-NF com 6 stats cards (Total auditado, Diferença total
detectada, Total de alertas, Aprovadas, Inconsistentes, Reconciliações
pendentes) e tabela com todas as 4 NFs (filtros por status, busca por
NF/obra, ordenação por qualquer coluna numérica). Botão "Exportar CSV"
chama `/auditorias/consolidado.csv`.

### DEMO_MODE (resiliência da apresentação)

Três modos via env var `DEMO_MODE`:

| Valor    | Comportamento |
| -------- | ------------- |
| `off`    | (default) Sem cache. Chama o provider configurado; sem chave, usa fixtures offline. |
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
2. Gera parecer + sugestões de reconciliação usando o offline provider.
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
`"demo_mode": true`. O frontend exibirá um badge discreto "Modo
demonstração" no canto inferior direito enquanto este modo estiver
ativo.

### Screenshots para o roteiro

Capturas a serem feitas (a sugestão é zoom 110% no Chrome, viewport
~1440x900) — guarde em `docs/screenshots/`:

1. `01_dashboard.png` — Tela `/` com os 4 stats cards e tabela das NFs.
2. `02_auditoria_indicadores.png` — Tela `/auditoria/{id}` mostrando o
   bloco de indicadores §4 e o parecer da IA na coluna direita.
3. `03_auditoria_alertas.png` — Mesma tela, rolada até a lista de
   alertas, com um alerta de tipo NAO_CADASTRADO em foco.
4. `04_modal_reconciliacao.png` — Modal de reconciliação aberto, com
   sugestões e seus chips de confiança.
5. `05_pdf_pagina_1.png` — Captura do PDF aberto numa nova aba (apenas
   a primeira página, mostrando indicadores + validação).
6. `06_consolidado.png` — Tela `/consolidado` com filtro "todas",
   mostrando os 6 stats cards e a tabela das 4 NFs.

## Testes

```bash
cd backend
uv run pytest          # 83 testes, ~5s
```

## Output de referência (NF 8108 -> NF 8187)

- Janela: 05/03/2026 10:10 -> 13/03/2026 08:50
- Saída teórica: 18.270,30 L
- Saídas registradas (Infleet): 18.342,00 L
- Diferença: +71,70 L (+0,39%)
- Equipamentos não cadastrados: 36
- Validação final: **INCONSISTENTE**
- Alertas: 38 (36 NAO_CADASTRADO + 1 OUTLIER + 1 DUPLICIDADE)
