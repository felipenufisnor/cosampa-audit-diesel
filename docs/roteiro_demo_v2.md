# Roteiro da Demo v2 — POC Auditoria de Diesel

> Apresentacao para o consorcio **CLC/Rocha/Cosampa (ARCO Metropolitano JP)**.
> Duracao alvo: **10 minutos**, com 5 a 10 minutos de Q&A em seguida.
> Foco da v2: responder o feedback "nao vi a IA trabalhando" mostrando IA
> protagonista em 3 momentos do fluxo + 2 previews de fase 2.
> Demo roda **inteiramente local** — backend FastAPI + frontend Next.js,
> com `AUDIT_AI_OFFLINE=1` para zero dependencia de rede.

---

## Setup pre-apresentacao (5 min antes)

1. **Pre-popular caches** (uma unica vez, com chave de LLM real):
   ```bash
   cd backend
   AUDIT_AI_OFFLINE=0 LLM_API_KEY=sk-or-v1-... \
     uv run python scripts/popular_cache_v2.py
   ```
   Isso grava `data/cache/stream_*.json`, `data/cache/assistente_*.json`
   e `data/cache/padroes_global.json`. Pode rodar tambem sem chave (cai
   no fallback determinisitico das tres features).

2. **Reiniciar backend no porto oficial** (janela 1):
   ```bash
   pids=$(lsof -tiTCP:8000 -sTCP:LISTEN); test -z "$pids" || kill $pids
   cd backend
   AUDIT_AI_OFFLINE=0 DEMO_MODE=off \
     DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
     uv run uvicorn audit_diesel.api.main:app --port 8000
   ```
   Verifique:
   ```bash
   curl http://localhost:8000/healthz | jq '{assistant_status, assistant_can_answer_free_text, assistant_has_cached_answers}'
   # esperado: assistant_status presente (available, missing_key, offline_fixture etc.)
   curl http://localhost:8000/padroes | jq '.padroes | length'
   # esperado: 3 a 5
   uv run python scripts/seed_assistente_demo_cache.py
   AUDIT_DIESEL_API_URL=http://localhost:8000 uv run python scripts/smoke_assistente_runtime.py
   ```

3. **Reiniciar frontend apontando para o mesmo porto** (janela 2):
   ```bash
   pids=$(lsof -tiTCP:3000 -sTCP:LISTEN); test -z "$pids" || kill $pids
   cd frontend
   NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
   ```
   Acesse `http://localhost:3000`. Na PRIMEIRA carga aparece o tour de
   onboarding — feche-o agora para evitar que apareca no meio da demo.

4. **Limpar `localStorage` do navegador apresentador** se quiser que o
   tour reapareca como parte do roteiro:
   ```js
   localStorage.removeItem("audit_diesel.onboarding.v2.seen")
   ```
   (Ou clique em "Refazer tour" no rodape do app.)

5. **Disposicao da tela**: navegador maximizado, zoom 100%, sidebar
   visivel, terminal escondido.

---

## Roteiro narrado (10 minutos)

### 0:00 a 1:00 - Abertura ancorada

> "A POC de auditoria de diesel ja entregava ponta-a-ponta na v1:
> ingestao das tres planilhas reais, engine deterministica calculando os
> 4 indicadores do escopo da Cosampa, 4 tipos de alerta, reconciliacao
> semantica e parecer tecnico, mais o PDF replicando a planilha original.
> 
> O feedback do consultor depois da primeira avaliacao foi direto: 'nao
> vi a IA trabalhando'. A v2 ataca esse ponto por tres angulos
> complementares - e em 10 minutos voces vao ver os tres."

(Slide ou tela cheia com os 3 angulos: **Padroes proativos** /
**Reasoning stream** / **Assistente de investigacao**.)

### 1:00 a 2:00 - Dashboard com Padroes detectados (Feature C — "uau" antes do clique)

Va para `/`. Pare na secao **Padroes detectados** logo abaixo do header.

> "Antes mesmo de eu abrir uma NF, o sistema ja analisou todo o historico
> e me entregou ate 5 padroes priorizados. Esses cards nao sao gerados
> pelo LLM no momento do clique - sao computados em Python por 7
> heuristicas estatisticas (aumento de consumo vs baseline, veiculos
> desmobilizados que seguem abastecendo, fornecedores com inconsistencias
> recorrentes...) e em seguida narrados pelo LLM, com uma camada de
> guardrail que descarta qualquer padrao sem evidencia nos dados."

Aponte para o card **OSB8826 +329%**:

> "Aqui o sistema viu que o consumo desse veiculo subiu 600 litros na
> semana atual contra uma media historica de 140. E aqui embaixo, o
> veiculo 04T639 - 18 abastecimentos totalizando 1656 litros DEPOIS da
> data de desmobilizacao no GP. Esse e' exatamente o tipo de coisa que
> antes so era pego ao abrir auditoria por auditoria."

### 2:00 a 4:00 - Auditar uma NF com Reasoning Stream (Feature A — "ver a IA trabalhando" literalmente)

Va para o **Dashboard**, role ate a tabela de NFs, clique em **Auditar**
na NF 8187. No dialog escolha NF anterior **8108**, clique em
**Auditar com narracao**.

A tela `/auditoria/run` abre e começa a narrar. Espere a sequencia
inteira (8-15 segundos).

> "Cada uma dessas etapas e' real - o engine deterministico roda
> exatamente o pipeline §4 do escopo da Cosampa. A diferenca e' que agora
> o auditor VE acontecendo. E nestes blocos cinza, com texto fluindo em
> tempo real, sao chamadas LLM em streaming de verdade ao OpenRouter -
> o modelo Qwen3-32b narrando porque essas 36 placas sem cadastro merecem
> atencao, ou compondo o parecer tecnico final."

Espere o `final_result` e a transicao automatica para
`/auditoria/<id>`.

> "Quando termina, ja estamos na auditoria persistida, com indicadores,
> alertas e parecer no mesmo lugar que a v1 entrega - mas o auditor
> acabou de ASSISTIR a analise sendo feita."

### 4:00 a 6:00 - Assistente de Investigacao (Feature B — IA conversa, IA consulta)

Ainda na tela de auditoria. Clique no botao **Assistente** no header. O
drawer abre a direita.

> "Aqui o Assistente esta restrito ao contexto desta NF. Ele tem 4
> ferramentas para consultar o banco - cadastro do GP, historico de
> veiculo, agregados por obra, comparacao entre NFs - no formato OpenAI
> tool calling padrao. Vou usar uma das perguntas sugeridas no rodape."

Clique no chip **"Qual o impacto financeiro dos alertas desta
auditoria?"**.

> "Repare na linha cinza entre as mensagens - aqui o sistema esta dizendo
> que esta CONSULTANDO uma tool, e em seguida dizendo o que recebeu. E
> sao informacoes reais do banco, nao alucinacao."

Espere a resposta. Clique no segundo chip **"Existe algum padrao
suspeito nesta auditoria?"**.

> "O Assistente pode comparar com outras NFs, cruzar com os padroes
> detectados do dashboard, e o historico persiste por auditoria - se eu
> voltar amanha, a investigacao continua de onde parei."

### 6:00 a 7:00 - PDF + consolidado (mantem o que a v1 ja fazia)

Feche o drawer. Clique em **Gerar PDF**.

> "O entregavel final continua sendo o PDF replicando o layout da
> planilha original. A v2 mantem 100% do que a v1 ja entregava - o
> consolidado por obra, o semaforo de NFs, o fluxo de aprovacao."

Va rapidamente para `/consolidado` e mostre a visao consolidada.

### 7:00 a 9:00 - Previews da fase 2 (Investigacoes + Rede)

Na sidebar, clique em **Investigacoes** (secao Preview).

> "Estas duas telas mostram o que a fase 2 entrega. Sao 100% mock - dados
> ilustrativos com marca d'agua 'PREVIEW' no fundo - mas dao para visualizar
> o workflow formal de tratativa. Kanban com 4 colunas, drag-and-drop
> entre estados, drawer com timeline da investigacao, evidencias anexadas
> e analise automatica sobre os documentos. A entrega real inclui
> integracao com GLPI, e-mail automatizado para gestores de obra e
> analise de documentos fisicos."

Mostre um card sendo arrastado de "Abertas" para "Em analise". Abra um
para mostrar o drawer.

Na sidebar, clique em **Analise de rede**.

> "E este e' o segundo preview - grafo de relacionamentos entre obras,
> veiculos, fornecedores e operadores. Tres clusters suspeitos
> pre-detectados, e repare que eles batem com o que vimos no dashboard de
> padroes - 04T639 conectando duas obras, OSB8826 dentro do cluster do
> operador 207. Em produçao, esse grafo se constroi automaticamente a
> partir do banco e detecta os clusters via algoritmos de comunidade tipo
> Louvain ou Leiden."

Faca hover em um cluster para destacar a regiao. Clique em um no para
isolar conexoes.

### 9:00 a 10:00 - Roadmap e fechamento

> "Resumindo o que a v2 entrega: tres pontos de presença da IA no fluxo,
> mais dois previews navegaveis. O roadmap da fase 2 cobre integracao
> via API com Metabase/CTA Smart, expansao multi-obra, workflow formal
> de tratativa com GLPI e analise de rede em tempo real. A POC mostra que
> a base tecnica esta resolvida - o que falta e' contratar a
> implementacao em escala.
> 
> Aberto a perguntas."

---

## Checagens pre-demo

- [ ] Backend respondendo `/healthz` com `assistant_status`
- [ ] `uv run python scripts/smoke_assistente_runtime.py` passa
- [ ] `/padroes` retornando >=3 padroes
- [ ] `/auditorias/run?ant=8108&atual=8187` reproduz o streaming sem erro
- [ ] Drawer do Assistente abre na NF 8187 com chips ou input livre ativo
- [ ] Tour de onboarding ja foi visto e nao reaparece
- [ ] `/investigacoes` mostra os 10 cards no kanban
- [ ] `/rede` mostra o grafo com 3 clusters destacados
- [ ] Logo COSAMPA no header, logo Tarea no footer
- [ ] Zoom 100%, modo claro, sidebar visivel

## Plano B se algo travar

| Falha | Acao |
|---|---|
| Reasoning stream nao avanca | F5 e use o botao "Auditar (rapido)" no dialog - mesmo destino sem narracao |
| Drawer do Assistente mostra backend desatualizado | Reiniciar backend em `:8000`, depois reiniciar frontend para recarregar `NEXT_PUBLIC_API_URL` |
| Drawer do Assistente sem chips | Rodar `cd backend && uv run python scripts/seed_assistente_demo_cache.py` |
| Padroes nao aparecem | Rodar `uv run audit-diesel analisar-padroes` num terminal lateral |
| Grafo nao renderiza | F5 - rota e' estatica, hot reload e' rapido |
| Internet caiu | Tudo offline ja, sem efeito |
