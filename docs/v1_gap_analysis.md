# Análise crítica da v1 contra o escopo formal

**Autor:** Felipe Martins · **Data:** 2026-05-11 · **Branch:** `main`
**Documentos fonte:**
- `reports/Auditoria_Diesel_Cosampa 042026.pdf` (escopo formal — §1 a §10)
- `reports/Relatorio-Copamsa-Reuniao.docx` (reunião 10/04/2026 — discovery comercial-estratégico)

Este documento responde às Tarefas 1 e 2 do brief da v2: mapear o que a v1 entrega
contra o que o escopo pede, e diagnosticar com honestidade a impressão do
consultor de que "não vi a IA trabalhando".

Toda referência a "v1" abaixo significa o estado do repositório em `main`
no commit `2fb7caa` (fix do guardrail do parecer).

---

## 1. O que a v1 entrega hoje — inventário objetivo

Mapeamento direto do código (não do que está possível ou planejado).

### Backend (`backend/src/audit_diesel/`)

| Componente | Arquivo | Função |
|---|---|---|
| Ingestão de planilhas | `ingestion/checklist.py`, `infleet.py`, `mobilizados.py`, `pipeline.py` | Lê os 3 .xlsx da pasta `datasets/` e popula SQLite. |
| Engine determinístico | `audit/engine.py`, `audit/indicators.py` | Calcula todos os campos da tabela do §5 do escopo (janela, estoque inicial/final teórico, saídas, diferença %, validação final). |
| Alertas determinísticos | `audit/alerts/` (4 arquivos) | `nao_cadastrado`, `pos_desmobilizacao`, `outlier_consumo` (z-score), `duplicidade`. |
| Cliente LLM | `ai/client.py` (289 linhas) | OpenRouter via `openai` SDK. Tem `tools` + `tool_choice`, retry com tenacity, fallback de modelo (qwen → deepseek). Síncrono. **Não tem streaming.** |
| Reconciliador semântico | `ai/reconciliador.py` (409 linhas) | LLM com tool call `registrar_sugestoes`, batches de 20, retorna `{abastecimento_id, mobilizado_id_candidato, confianca, justificativa}`. |
| Gerador de parecer | `ai/parecer.py` + `prompts/parecer.py` | Recebe payload da auditoria, chama LLM, retorna markdown com guardrails (`parecer_guardrails.py`). |
| Cache offline | `ai/cache.py` + `fixtures.py` | Em `AUDIT_AI_OFFLINE=1`, lê parecer e sugestões pré-computadas de JSON. |
| PDF | `api/pdf.py` | Replica layout da planilha original. |
| API | `api/routers/` | `auditorias` (CRUD + PDF), `nfs`, `reconciliacao`, `stats`. |

### Frontend (`frontend/src/`)

| Rota | Arquivo | Conteúdo |
|---|---|---|
| `/` (Dashboard) | `app/page.tsx` + `dashboard/stats-cards.tsx` + `nfs-table.tsx` | Stats agregados (total abastecido, % custo não-cadastrado, etc.) + tabela de NFs com semáforo. |
| `/consolidado` | `app/consolidado/page.tsx` | Visão consolidada por NF com alertas resumidos. |
| `/auditoria/[id]` | `app/auditoria/[id]/page.tsx` | Layout 8/12 + 4/12: indicadores + alertas à esquerda, **parecer da IA em card lateral à direita (`xl:col-span-4`)**. Modal de reconciliação acionado por botão dentro do alerta. |

**Locais onde a IA aparece visualmente para o auditor:**
1. Card lateral "Parecer técnico - IA" — secundário, à direita, abaixo da janela temporal.
2. `ReconciliacaoDialog` — modal acionado por clique no item de um alerta "não cadastrado".

São os únicos dois pontos. Em nenhum lugar da UI a IA produz uma ação visível
**antes** do auditor solicitar.

---

## 2. Tabela de gap contra o escopo

Critério: "entrega hoje" só conta o que está IMPLEMENTADO e VISÍVEL no fluxo
do auditor. Backend sem UI = gap.

| Oportunidade do escopo | O que a v1 entrega hoje | Gap | Severidade |
|---|---|---|---|
| **§8.1 Integração e coleta automatizada** (substituir 4 sistemas → pipeline) | Ingestão estática dos 3 `.xlsx` reais (Infleet, GP, Checklist) para SQLite. Não há CTA Smart, não há Metabase, não há leitura via API de nenhum sistema. Não há IA envolvida na ingestão. | Não atende. POC trabalha com snapshots em disco, não com integração viva. Sem pipeline. Sem orquestração. Sem IA classificando documentos heterogêneos como o Bruno descreve no Convexus. | **Média** — esperado para uma POC com dados snapshot, mas é o gap mais visível para o discurso "consolidação automática" da §8.1 e do desafio #1. |
| **§8.2 Higienização de cadastros** (agente que reconhece "ABC-1234", "ABC1234", "Ativo-7291" como mesmo equipamento) | `ai/reconciliador.py` faz exatamente isso, com LLM + tool use, validação pydantic, batches de 20, justificativa por sugestão. Tecnicamente é o componente mais maduro da v1. | A capacidade existe, mas só dispara: (a) sob demanda no clique do botão "Reconciliar" dentro de um alerta de não-cadastrado, (b) em modal escondido (`ReconciliacaoDialog`). Não há fluxo proativo — auditor precisa procurar. Não há tela dedicada para revisar sugestões em lote. Não há histórico de match aprovado servindo como aprendizado. | **Alta** (de visibilidade, não de implementação) — é a dor #1 explicitada pela Francisca ("um setor utiliza o nome técnico, outro o nome comercial, outro o nome resumido… isso dá um nó nas nossas análises") e a v1 entrega a capacidade mas não a expõe como protagonista. |
| **§8.3 Detecção de anomalias** (séries temporais, horários atípicos, variações bruscas, períodos sem registro, consumo cross-obra) | `audit/alerts/outlier_consumo.py` calcula z-score por veículo. `duplicidade.py` flagga abastecimentos duplicados. Tudo determinístico, por auditoria isolada. | Não há análise cross-NF, cross-obra, cross-período. Não há detecção de "horários atípicos", "períodos sem registro", "veículo em obras diferentes no mesmo dia" — todos exemplos literais do §8.3. Não há proatividade: o sistema espera o auditor clicar em uma NF para mostrar anomalias. Não há narrativa sobre o porquê de uma anomalia. | **Alta** — endereço direto da Feature C. O escopo pede "alertas proativos antes mesmo de o auditor iniciar a análise formal" e a v1 só age reativamente. |
| **§8.4 Assistente de investigação** (sugere causa provável, acessa documentos GLPI, guia o auditor pelas etapas) | Nada. A v1 não tem chat, não tem tool use exposto ao auditor, não tem acesso a GLPI, não tem qualquer fluxo de "investigação assistida". Quando o auditor vê uma inconsistência, ele sai do sistema para investigar manualmente. | Gap total. É a oportunidade do escopo com maior distância entre o pedido e o entregue. | **Crítica** — endereço direto da Feature B. Também cobre o Desafio #5 ("investigação manual e descentralizada"). |
| **§8.5 Dashboard + PDF** (visão por obra, indicadores de risco, priorização automática, PDF de conclusão) | Dashboard com stats agregados + tabela com semáforo. PDF replicando layout da planilha. | A v1 entrega bem o "dashboard + PDF" do ponto de vista de relatório. Falta a parte de "priorização automática por risco" — a tabela hoje lista NFs sem rankear pelo grau de suspeição. Não há comparação cross-obra (POC trabalha 1 obra só). | **Baixa-Média** — o que está implementado funciona; o gap é o ranking inteligente. |
| **Desafio #1 — Fragmentação de fontes** | Ingestão local de 3 dos 4 sistemas. CTA Smart ausente. | Sem pipeline real e sem integração ao vivo. | **Média** — mesma análise do §8.1. |
| **Desafio #3 — Preenchimento incorreto do checklist** | Validações estruturais no `ingestion/normalizers.py`, mas nenhuma validação em tempo real no momento do preenchimento — só depois que a planilha é importada. | A v1 não está no fluxo de preenchimento. O escopo pede "alertas em tempo real no momento do preenchimento, cruzando com histórico" — isso exigiria integração com o Metabase/formulário, fora da POC. | **Média** — fora do escopo razoável de uma POC, mas vale registrar como roadmap. |
| **Desafio #5 — Investigação manual e descentralizada** | Nada. | Idêntico ao §8.4. | **Crítica** — Feature B + tela de Investigações (preview) endereçam. |
| **Desafio #6 — Volume de obras simultâneas** | Dashboard cobre as NFs da obra-piloto (Arco JP). Não há visão multi-obra. Não há priorização cross-obra. | A POC opera em escopo de 1 obra, então não há como provar a visão multi-obra. Falta também o ranking automático de risco mesmo dentro de uma obra. | **Média** — feature dependente da Feature C (padrões cross-NF) e de dados de mais obras. |

### Resumo das severidades

- **Crítica (2):** §8.4 Assistente de Investigação · Desafio #5 Investigação descentralizada
- **Alta (2):** §8.2 Higienização (de visibilidade) · §8.3 Detecção de anomalias proativa
- **Média (4):** §8.1 Integração · Desafio #1 Fragmentação · Desafio #3 Preenchimento · Desafio #6 Multi-obra
- **Baixa-Média (1):** §8.5 Dashboard/PDF

Dois gaps críticos. Os dois apontam para a mesma raiz: a IA não tem **lugar
próprio no fluxo do auditor**. Ela é convidada ocasionalmente, não é
protagonista.

---

## 3. Diagnóstico do feedback "não vi a IA trabalhando"

O brief apresenta 5 hipóteses. Avaliação honesta de cada uma:

### (a) "A v1 tem pouca IA de fato" — **PARCIALMENTE VERDADEIRO**

A v1 faz exatamente 2 chamadas LLM por auditoria: `reconciliador` (uma vez por
batch) e `parecer` (uma vez no fim). Comparado ao discurso "para cada atividade
humana, um agente de IA" (fala do Bruno na reunião), 2 chamadas é pouco.

**Mas** — e isso é importante — as duas chamadas que existem são **bem
implementadas**: reconciliador usa tool calling, valida com pydantic, faz
batching; parecer tem guardrails e fallback determinístico. Não é IA de
fachada. É IA séria, mas em quantidade pequena.

**Refutação parcial:** o problema não é "pouca IA", é "IA pouco distribuída
pelo fluxo". Se as duas chamadas existentes aparecessem em 4-5 momentos
distintos da experiência, o efeito perceptivo seria diferente.

### (b) "A IA está presente mas escondida" — **CONFIRMADO**

Olhando `frontend/src/app/auditoria/[id]/page.tsx`:
- O parecer da IA fica em `xl:col-span-4`, **à direita**, em um card lateral.
- A reconciliação fica em um **modal acionado por clique**, dentro de um
  alerta, atrás de um botão "Reconciliar". O auditor pode ler a auditoria
  inteira sem nunca abrir esse modal.

Em uma demo de 10 minutos, se o consultor olha primeiro para o lado esquerdo
(indicadores + alertas — o conteúdo principal), ele pode literalmente passar
60-90 segundos sem registrar que há um card de IA à direita. Se ele não clica
em "Reconciliar", nunca vê a reconciliação acontecer.

**Confirmação clara.** A IA não está hierarquicamente posicionada como
protagonista da tela.

### (c) "A IA está presente mas o output é raso" — **CONFIRMADO**

O parecer hoje é um markdown de ~10-15 linhas com cabeçalho, indicadores
principais e veredito. **Não mostra raciocínio.** Não diz "considerei X, mas
descartei porque Y". Não cita o que foi anômalo. Não relaciona NFs anteriores.

A reconciliação retorna `{abastecimento_id, mobilizado_id_candidato, confianca,
justificativa}` — onde `justificativa` tem max_length=500 e na prática vem com
1-2 frases. Não mostra que o LLM considerou marca, modelo, capacidade do
tanque, etc.

**Confirmação clara.** O output é correto mas o "como a IA chegou lá" está
escondido — é justamente o que faz o auditor falar "uau, ela pensou nisso".

### (d) "A IA não tem efeito CAUSAL visível" — **CONFIRMADO**

Em nenhum momento o auditor vê o sistema **agindo por iniciativa própria**.
Tudo o que a IA faz é em resposta a um clique:
- Auditar uma NF → o parecer aparece junto, mas fica encerrado no card.
- Reconciliar um alerta → o modal abre, ele revisa, fecha.

Não há "a IA detectou um padrão e te avisou". Não há "a IA fez uma checagem
adicional que você não pediu". Não há "a IA leu 3 auditorias passadas e
encontrou correlação".

**Confirmação clara.** Toda IA da v1 é reativa, nenhuma é proativa. Esse é o
ângulo que mais sustenta o feedback do consultor.

### (e) "Falta um momento de impacto único" — **CONFIRMADO**

Não existe na v1 um único momento onde o cliente reage com "isso aqui é
impressionante". O melhor candidato seria o parecer, mas ele aparece já
encerrado em um card, sem produção visível. O segundo candidato seria a
reconciliação, mas ela exige que o auditor clique em um botão dentro de um
modal — atrito demais.

**Confirmação clara.** A v1 não foi desenhada com um pico de impacto. É
funcional do começo ao fim, com curva plana.

### Síntese do diagnóstico

A inferência prévia do brief (combinação de **b + c + e**) está correta, mas
faltou o **d**, que é o mais decisivo: **a v1 trata IA como geradora de texto
auxiliar, não como protagonista do fluxo de auditoria**.

O consultor não viu a IA trabalhando porque, na v1, a IA literalmente não
trabalha em frente a ele. Ela trabalha em duas chamadas backend rápidas, cujos
resultados aparecem **já prontos** em locais secundários da tela. Não há
"durante" — só "depois".

Plano direto que esse diagnóstico endossa:

| Feature da v2 | Eixo do diagnóstico que ataca |
|---|---|
| **A — Reasoning Stream** | b + c + d + e. Resolve a falta de "durante": auditor vê o sistema executando passo a passo, com trechos de raciocínio do LLM em streaming real onde fizer sentido. É o pico de impacto. |
| **B — Assistente de investigação** | a + c + d. Resolve a falta do §8.4. Distribui a IA em mais momentos do fluxo. Tool calling visível dá causalidade ("a IA está consultando o histórico de 13.T881…"). |
| **C — Padrões proativos cross-NF** | d + e. Resolve a falta de proatividade. Auditor abre o dashboard e já encontra padrões detectados — a IA chega antes dele. Endereça §8.3 + Desafio #6. |

As 3 features se complementam por ângulos diferentes do mesmo problema. A
Feature A é a mais teatral (o pico). A Feature C é a mais estratégica (a IA
chega antes). A Feature B é a mais profunda (a IA conversa).

---

## 4. Observações finais para a Tarefa 3

Ao especificar as 3 features novas, três princípios derivam direto desta
análise:

1. **Reuso do que já existe.** O `ai/client.py` atual já tem tool use, retry e
   fallback qwen→deepseek. Estender para streaming async é evolução, não
   reescrita. O `ai/reconciliador.py` já tem o padrão de tool calling
   validado por pydantic — Feature B deve seguir o mesmo padrão para as 4
   tools de consulta.
2. **Visibilidade é o entregável.** O risco maior da v2 é repetir o erro da
   v1: implementar IA poderosa em local secundário. Cada uma das 3 features
   precisa de um ponto de presença visual hierárquico claro: Reasoning Stream
   ocupa tela inteira, Padrões ocupa topo do dashboard, Assistente é drawer
   lateral sempre acessível.
3. **Honestidade da Feature C.** O escopo §8.3 lista exemplos concretos
   (horários atípicos, períodos sem registro, consumo cross-obra). A Feature
   C deve gerar padrões baseados em evidência real desses critérios. Se o
   dataset não tem evidência para 5 padrões, retornar menos. Padrão inventado
   pelo LLM sem suporte nos dados é pior que ausência de padrão.
