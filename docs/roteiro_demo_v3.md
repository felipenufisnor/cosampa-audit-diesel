# Roteiro da Demo v3 - POC Auditoria de Diesel

> Apresentacao para o consorcio **CLC/Rocha/Cosampa (ARCO Metropolitano JP)**.
> Duracao alvo: **10 minutos**, com 5 a 10 minutos de Q&A em seguida.
> Foco da v3: mostrar a plataforma como um conjunto de **agentes e IA
> copilotos** que reduzem o trabalho manual do engenheiro auditor: priorizam
> risco, executam a auditoria, explicam o raciocinio, consultam dados e
> encaminham investigacoes.
> Demo roda **inteiramente local** - backend FastAPI + frontend Next.js,
> com cache de IA para estabilidade da apresentacao.

---

## Setup pre-apresentacao (5 min antes)

1. **Pre-popular caches** (uma unica vez, com chave de LLM real quando houver):
   ```bash
   cd backend
   AUDIT_AI_OFFLINE=0 LLM_API_KEY=sk-or-v1-... \
     uv run python scripts/popular_cache_v2.py
   ```
   Isso grava `data/cache/stream_*.json`, `data/cache/assistente_*.json`
   e `data/cache/padroes_global.json`. Sem chave, o fluxo cai no fallback
   deterministico/cacheado, suficiente para uma demo sem dependencia de rede.

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
   curl http://localhost:8000/padroes | jq '.padroes | length'
   uv run python scripts/seed_assistente_demo_cache.py
   AUDIT_DIESEL_API_URL=http://localhost:8000 uv run python scripts/smoke_assistente_runtime.py
   ```

3. **Reiniciar frontend apontando para o mesmo porto** (janela 2):
   ```bash
   pids=$(lsof -tiTCP:3000 -sTCP:LISTEN); test -z "$pids" || kill $pids
   cd frontend
   NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
   ```
   Acesse `http://localhost:3000`. Feche o onboarding antes da apresentacao,
   a menos que voce queira usa-lo como abertura.

4. **Limpar `localStorage` do navegador apresentador** se quiser que o tour
   reapareca:
   ```js
   localStorage.removeItem("audit_diesel.onboarding.v2.seen")
   ```

5. **Disposicao da tela**: navegador maximizado, zoom 100%, sidebar visivel,
   terminal escondido, rota inicial em `/`.

---

## Roteiro narrado (10 minutos)

### 0:00 a 1:00 - Abertura: da planilha ao agente auditor

Comece no **Dashboard** (`/`).

> "A auditoria de diesel hoje exige que o engenheiro cruze planilhas,
> cadastro do GP, registros do Infleet, checklist, chamados e evidencias
> operacionais. A POC transforma esse processo em uma esteira de agentes.
>
> O primeiro agente e deterministico: ele calcula os indicadores do escopo,
> compara NF anterior e NF atual, valida a diferenca de saidas e dispara
> alertas tecnicos. Em cima dele entram os agentes de IA: um prioriza
> padroes, outro narra a auditoria em tempo real, outro conversa com o
> auditor usando ferramentas de consulta, e outro reconcilia cadastros
> divergentes.
>
> O ponto principal nao e trocar o engenheiro pela IA. E dar ao engenheiro
> um copiloto que faz a triagem pesada, aponta onde olhar e deixa trilha
> tecnica para decisao e responsabilizacao."

Aponte rapidamente para os cards do dashboard e para a tabela de NFs.

> "A demo principal usa dados reais da obra-piloto: NF anterior 8108 e NF
> atual 8187. O resultado dessa janela e inconsistente: diferenca de +0,39%,
> 36 equipamentos sem cadastro no GP e R$ 32.924,16 em alertas de alta
> severidade."

### 1:00 a 2:15 - Padroes proativos: IA antes do clique

Na sidebar, clique em **Padroes detectados** ou va para `/padroes`.

> "Aqui entra o agente de padroes proativos. Antes de eu abrir uma auditoria
> formal, ele ja leu o historico de abastecimentos, auditorias e cadastro
> GP, levantou candidatos por heuristicas estatisticas e pediu para a IA
> priorizar e explicar o que merece atencao.
>
> Esse desenho e importante: o LLM nao inventa padroes. A evidencia nasce
> em Python, a partir do banco, e a IA entra para selecionar, resumir e
> transformar o sinal tecnico em uma pauta de investigacao."

Aponte para cards como **OSB8826 +329%** e **04T639 pos-desmobilizacao** se
estiverem visiveis.

> "Por exemplo: OSB8826 aparece com aumento forte de consumo, e 04T639
> aparece com 18 abastecimentos totalizando 1.656 litros mesmo com sinal
> de desmobilizacao no GP. Para o engenheiro, isso muda o comeco do dia:
> ele nao abre uma lista cega de NFs; ele abre uma fila priorizada por risco."

Clique em **Investigar NF 8187** quando o card permitir, ou volte ao
Dashboard para auditar a NF 8187.

### 2:15 a 4:15 - Auditar NF 8187 com reasoning stream

No **Dashboard**, clique em **Auditar** na NF **8187**. No dialog, escolha
NF anterior **8108** e clique em **Auditar com narracao**.

A tela `/auditoria/run` abre. Espere a sequencia inteira.

> "Agora estamos vendo o agente auditor trabalhar. Cada etapa aqui e real:
> ele delimita a janela temporal entre as duas NFs, calcula estoque inicial,
> estoque final teorico, saida teorica, saidas registradas no Infleet,
> diferenca em litros e percentual, e depois roda os quatro detectores:
> nao cadastrado, pos-desmobilizacao, outlier e duplicidade.
>
> A camada de IA nao substitui essas regras. Ela explica o que a regra
> encontrou, narra o raciocinio e prepara o auditor para tomar decisao.
> Este e o momento em que a IA deixa de ser um parecer escondido no fim
> da tela e passa a ser visivel durante a analise."

Quando aparecer o resultado final e a transicao para `/auditoria/[id]`:

> "Ao terminar, a auditoria fica persistida: indicadores, alertas,
> parecer tecnico, fluxo de reconciliacao e PDF. O engenheiro assistiu a
> auditoria acontecer e agora entra na investigacao com contexto."

### 4:15 a 6:45 - Tres exemplos reais auditados

Na tela `/auditoria/[id]`, role ate a lista de alertas da NF 8187. Use filtros
ou busca visual conforme necessario.

#### Exemplo 1 - 13.T881 / CALDEIRA US ASF-01: risco financeiro em cadastro ausente

Aponte para o alerta **Equipamento nao cadastrado no GP** do veiculo
**13.T881**.

> "Primeiro exemplo real: 13.T881, apelido CALDEIRA US ASF-01. Na NF 8187,
> houve um abastecimento de 1.196 litros em 12/03/2026, com custo de
> R$ 6.888,96, mas sem cadastro correspondente no GP."

**Analise desse exemplo:**

> "A leitura superficial seria: e so uma placa ausente. Mas para auditoria
> tecnica isso nao basta. Um item sem cadastro com quase sete mil reais de
> impacto precisa ser tratado diferente de uma divergencia pequena de
> nomenclatura.
>
> Aqui a IA ajuda o engenheiro a separar falha cadastral de risco financeiro.
> Ela pode consultar historico do veiculo, procurar padroes de reincidencia,
> sugerir reconciliacao semantica e montar a pergunta correta para a obra:
> este equipamento existe, estava mobilizado, e por que nao estava no GP na
> data do abastecimento?"

#### Exemplo 2 - 69.T888 / PC-02: outlier nao e acusacao, e priorizacao

Aponte para o alerta **Consumo atipico para o veiculo** do **69.T888**.

> "Segundo exemplo real: 69.T888, apelido PC-02. O sistema encontrou um
> abastecimento de 186 litros em 07/03/2026. A media historica desse veiculo
> e 80,3 litros, com 38 observacoes, e o z-score ficou em 3,33. O custo do
> evento foi R$ 1.071,36."

**Analise desse exemplo:**

> "Este e um ponto bom para explicar o papel correto da IA. O agente nao
> diz 'houve fraude'. Ele diz: este comportamento saiu do padrao historico
> e merece uma pergunta operacional.
>
> A investigacao pode concluir que houve mobilizacao temporaria, mudanca de
> frente de obra, abastecimento acumulado ou erro de lancamento. O valor da
> IA e encurtar o caminho: ela mostra a anomalia, traz o baseline, compara
> com outras NFs e ajuda o auditor a pedir a evidencia certa."

#### Exemplo 3 - IAL6I53 / CB-37 JP: duplicidade simples, ganho rapido

Aponte para o alerta **Multiplos abastecimentos no mesmo dia** do **IAL6I53**.

> "Terceiro exemplo real: IAL6I53, apelido CB-37 JP. Na NF 8187 aparecem
> dois abastecimentos identicos de 75 litros no dia 11/03/2026 as 09:17.
> Somados, sao 150 litros e R$ 864,00."

**Analise desse exemplo:**

> "Esse caso tem severidade menor, mas e muito valioso operacionalmente.
> Parece uma duplicidade de lancamento: mesmo veiculo, mesmo horario, mesmo
> volume. Para o engenheiro, e uma correcao rapida que reduz ruido do
> fechamento e evita que a equipe gaste energia em item simples.
>
> O assistente pode transformar isso em acao: registrar a hipotese,
> consultar os abastecimentos vinculados, pedir confirmacao ao gestor da
> obra e deixar a evidencia pronta para o PDF ou para uma investigacao."

Feche a sequencia reforcando o conjunto:

> "Esses tres exemplos mostram a diferenca entre alerta e investigacao.
> O alerta aponta o fato. O agente ajuda a interpretar materialidade,
> contexto e proxima acao."

### 6:45 a 8:00 - Assistente de investigacao: IA que conversa e consulta

Ainda na auditoria da NF 8187, clique em **Assistente** no header.

> "Agora entro no assistente de investigacao. Ele nao e um chat generico:
> ele esta preso ao contexto desta auditoria e usa ferramentas para consultar
> o banco. As ferramentas incluem cadastro do GP, historico de veiculo,
> agregados por obra e comparacao entre NFs."

Clique no chip **"Qual o impacto financeiro dos alertas desta auditoria?"**.

> "Repare que a resposta vem com consulta. O assistente nao precisa decorar
> os dados nem improvisar. Ele chama uma tool, recebe os registros e responde
> com base no que existe na auditoria."

Em seguida, use uma pergunta livre ou chip relacionado a padrao suspeito.
Sugestao de pergunta:

```text
Analise os casos 13.T881, 69.T888 e IAL6I53 e me diga qual deve ser priorizado primeiro pelo engenheiro auditor.
```

> "E aqui aparece o ganho para o engenheiro: a IA nao so resume, ela ajuda
> a decidir ordem de trabalho. Um caso pode ser alto impacto financeiro,
> outro pode ser anomalia operacional, outro pode ser correcao rapida. O
> auditor continua decidindo, mas decide com uma triagem pronta."

Se houver tempo, abra rapidamente um alerta de **Nao cadastrado** e o modal
de **Reconciliar**.

> "O reconciliador semantico fecha outro problema classico: GP e Infleet
> nem sempre usam o mesmo identificador. A IA sugere candidatos, retorna
> confianca e justificativa, e o auditor aprova ou rejeita. A aprovacao vira
> aprendizado operacional para a reauditoria."

### 8:00 a 9:15 - Previews futuros: investigacoes e rede

Na sidebar, clique em **Investigacoes** (`/investigacoes`).

> "Agora saimos da parte produtiva da POC e entramos nos previews da fase 2.
> Esta tela e mock, com dados ilustrativos, mas mostra o workflow que vem
> depois da auditoria: investigacoes formalizadas, responsaveis, prazo,
> evidencias, timeline e analise automatica."

Mostre o kanban, arraste um card se fizer sentido e abra o drawer.

> "Na implementacao real, isso se conecta com GLPI e e-mail: o sistema
> abre tratativa, aciona gestor de obra, anexa checklist fisico, guarda
> resposta e ajuda a classificar a conclusao. O engenheiro deixa de tratar
> cada achado em conversas soltas e passa a trabalhar em um fluxo rastreavel."

Na sidebar, clique em **Analise de rede** (`/rede`).

> "O segundo preview e a analise de rede. Aqui a fase 2 amplia a auditoria
> para multiobra: obras, veiculos, fornecedores e operadores viram um grafo.
> O objetivo e encontrar relacoes que nao aparecem quando olhamos uma NF
> isolada: veiculo em duas obras, operador associado a varios outliers,
> fornecedor concentrando inconsistencias."

Faca hover em um cluster e clique em um no para isolar conexoes.

> "Em producao, esse grafo seria calculado automaticamente a partir do
> banco, com algoritmos de comunidade e scoring de risco. Tambem entram
> integracoes com CTA Smart e Metabase, alem de validacao em tempo real
> no momento de preenchimento do checklist."

### 9:15 a 10:00 - Fechamento executivo

Volte ao **Dashboard** ou deixe a tela de rede aberta.

> "Resumo da v3: a POC deixou de ser uma tela que mostra resultado e passou
> a representar uma esteira de agentes para auditoria.
>
> O agente deterministico garante calculo e rastreabilidade. O agente de
> padroes prioriza risco antes do clique. O agente narrador mostra a
> auditoria acontecendo. O assistente consulta dados e guia a investigacao.
> O reconciliador resolve divergencias de cadastro com aprovacao humana.
>
> A fase 2 leva isso para escala: integracao com GLPI, e-mail, CTA Smart e
> Metabase; investigacoes formais; analise de documentos; rede multiobra;
> e validacoes em tempo real. A decisao continua com o engenheiro, mas a
> preparacao, triagem e documentacao passam a ser assistidas por IA.
>
> Aberto a perguntas."

---

## Recursos atuais versus previews

| Area | Status na demo | Como falar |
|---|---|---|
| Ingestao de planilhas, indicadores e alertas | Real | "Engine deterministico com dados reais da obra-piloto." |
| Reasoning stream | Real/cacheado para estabilidade | "A auditoria e executada de verdade; a narracao pode usar cache para demo." |
| Padroes proativos | Real/cacheado para estabilidade | "Heuristicas geram evidencias; IA prioriza e narra." |
| Assistente com tool calling | Real, com modo degradado por cache | "Consulta banco por ferramentas, restrito ao contexto da auditoria." |
| Reconciliador semantico | Real | "Sugere match, auditor aprova, auditoria e recalculada." |
| PDF e consolidado | Real | "Entregavel oficial e visao cross-NF ja disponiveis." |
| Investigacoes | Preview/mock | "Fluxo planejado para fase 2, dados ilustrativos." |
| Analise de rede | Preview/mock | "Visual navegavel da fase 2, grafo ainda estatico." |
| GLPI, e-mail, CTA Smart, Metabase, multiobra | Futuro | "Integracoes e escala produtiva da fase 2." |
| Validacao em tempo real do checklist | Futuro | "Depende de integracao com o fluxo de preenchimento." |

---

## Guia rapido dos tres exemplos

| Exemplo | Onde mostrar | Numero-chave | Frase curta |
|---|---|---|---|
| 13.T881 / CALDEIRA US ASF-01 | Alerta `NAO_CADASTRADO` na NF 8187 | 1.196 L, R$ 6.888,96 | "Cadastro ausente com impacto financeiro relevante." |
| 69.T888 / PC-02 | Alerta `OUTLIER` na NF 8187 | 186 L, z-score 3,33, media 80,3 L | "Anomalia nao e acusacao; e priorizacao tecnica." |
| IAL6I53 / CB-37 JP | Alerta `DUPLICIDADE` na NF 8187 | 2 x 75 L as 09:17, R$ 864,00 | "Correcao simples, ganho operacional rapido." |

---

## Checagens pre-demo

- [ ] Backend respondendo `/healthz` com `assistant_status`
- [ ] `uv run python scripts/smoke_assistente_runtime.py` passa
- [ ] `/padroes` retornando >=3 padroes
- [ ] `/auditorias/run?ant=8108&atual=8187` reproduz o streaming sem erro
- [ ] Dashboard lista a NF 8187 e permite escolher NF anterior 8108
- [ ] `/auditoria/[id]` mostra indicadores, alertas e parecer
- [ ] Alertas da NF 8187 incluem exemplos 13.T881, 69.T888 e IAL6I53
- [ ] Drawer do Assistente abre na NF 8187 com chips ou input livre ativo
- [ ] Modal de Reconciliacao abre em pelo menos um alerta `NAO_CADASTRADO`
- [ ] `/consolidado` carrega a visao cross-NF
- [ ] `/investigacoes` mostra os cards no kanban com marca de preview
- [ ] `/rede` mostra o grafo com clusters destacados
- [ ] Tour de onboarding ja foi visto e nao reaparece
- [ ] Logo COSAMPA no header, logo Tarea no footer
- [ ] Zoom 100%, modo claro, sidebar visivel

## Plano B se algo travar

| Falha | Acao |
|---|---|
| Reasoning stream nao avanca | F5 e use o botao "Auditar (rapido)" no dialog - mesmo destino sem narracao |
| Provider de IA indisponivel | Rodar com cache ou `AUDIT_AI_OFFLINE=1`; explique que o modo demo evita dependencia de rede |
| Drawer do Assistente mostra backend desatualizado | Reiniciar backend em `:8000`, depois reiniciar frontend para recarregar `NEXT_PUBLIC_API_URL` |
| Drawer do Assistente sem chips | Rodar `cd backend && uv run python scripts/seed_assistente_demo_cache.py` |
| Padroes nao aparecem | Rodar `uv run audit-diesel analisar-padroes` num terminal lateral |
| Exemplo especifico dificil de achar na lista | Use a fala dos 3 exemplos como narrativa e mostre o consolidado/parecer da NF 8187 |
| PDF demora ou falha por dependencia nativa | Pule o PDF e mencione os PDFs amostra em `backend/data/pdfs_amostra/` |
| Grafo nao renderiza | F5 - rota e estatica, hot reload e rapido |
| Internet caiu | Use modo offline/cacheado; a demo principal continua local |
