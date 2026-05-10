# Roteiro da Demo — POC Auditoria de Diesel

> Apresentacao para o consorcio **CLC/Rocha/Cosampa (ARCO Metropolitano JP)**.
> Duracao alvo: **10 minutos**, com 5 a 10 minutos de Q&A em seguida.
> Publico: equipe de auditoria, planejamento e diretoria do consorcio.
> Demo roda **inteiramente local** — backend FastAPI + frontend Next.js.

---

## Setup pre-apresentacao (5 min antes)

1. **Ativar DEMO_MODE no backend.** No terminal do backend:
   ```bash
   cd backend
   export DEMO_MODE=true
   export AUDIT_AI_OFFLINE=1   # garante zero chamadas de rede
   ```
   Confirme que `data/demo_cache/` tem 6 arquivos JSON. Caso contrario, rode
   primeiro `DEMO_MODE=record uv run python scripts/popular_cache_demo.py`.

2. **Subir backend** (janela 1):
   ```bash
   DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
     uv run uvicorn audit_diesel.api.main:app --port 8000
   ```
   Verifique `curl http://localhost:8000/healthz` mostrando `"demo_mode": true`.

3. **Subir frontend** (janela 2):
   ```bash
   cd frontend
   pnpm build && pnpm start
   ```
   Build de producao deixa a tela mais responsiva que `pnpm dev`.

4. **Browser** (Chrome): abrir `http://localhost:3000`, zoom em **110%** para
   melhor leitura no projetor. Verificar que o badge "Modo demonstracao"
   aparece no canto inferior direito.

5. **Backup visual**: ter este roteiro aberto numa segunda janela. Manter o
   terminal do backend visivel em uma terceira janela como "monitor" — em
   caso de pergunta sobre logs, basta apontar.

6. **Higiene**: fechar Slack, e-mail, qualquer notificacao do SO. Modo nao
   perturbe ativo. Verificar bateria do notebook.

---

## Cronograma (10 min)

### 0:00 — 1:00 | Abertura ancorada

> "Hoje, quando vocês recebem uma NF de diesel, alguém do escritório
> abre três planilhas — o checklist do GLPI, a lista de mobilizados da
> Gestão de Projetos e o relatório do Infleet — e cruza linha a linha
> para confirmar se o consumo bate com o que entrou no tanque. Esse
> processo, hoje, leva **dias**. E como são mais de 2.000 abastecimentos
> por mês, é humanamente impossível auditar tudo. O que vamos mostrar
> agora é um agente que faz exatamente esse cruzamento — em segundos,
> com auditoria rastreável."

Pontos a transmitir nestes 60 segundos:
- Não é "IA genérica que adivinha". É uma engine determinística + um
  parecer de IA opcional para síntese.
- A planilha "AUDITORIA DO DIESEL_0" continua sendo a fonte da verdade
  contábil — nós a reproduzimos integralmente para que vocês reconheçam.
- Os dados são reais: as 4 NFs do mês de março/2026.

### 1:00 — 3:00 | Demo: dashboard

Ações:
1. Mostrar a tela inicial `/`. Apontar para os **4 stats cards**:
   - "X abastecimentos no período"
   - "Y% de custo não cadastrado" — falar: "Esse é o problema que estamos
     resolvendo: 22 mil reais em diesel sem placa identificada."
   - "Z NFs no período"
   - "N equipamentos mobilizados"
2. Apontar para a **tabela de NFs**. Comentar que são as 4 NFs reais.
3. Click em **"Auditar"** da NF 8187.
4. No diálogo, **selecionar 8108 como NF anterior** (default já apontado).
5. Click em **"Confirmar auditoria"**. Aguardar 1 a 2 segundos.

> "Repare que o sistema escolhe a NF anterior automaticamente — porque
> a auditoria é sempre entre duas NFs sequenciais da mesma obra. É o
> que o auditor define como janela temporal."

### 3:00 — 6:00 | Demo: auditoria detalhada

Ações:
1. Apontar para o **bloco de indicadores** (centro da tela).
   > "Esse layout — estoque inicial, descarregamento, saída teórica,
   > diferença apurada — é exatamente o que vocês têm na aba 'AUDITORIA
   > DO DIESEL_0' da planilha. A diferença é que aqui ele se preenche
   > sozinho a partir das 4 fontes."

2. Apontar para a **diferença em litros e percentual**.
   > "Quando essa diferença passa de 2%, a NF entra como inconsistente
   > automaticamente — regra que vocês já usam hoje."

3. Apontar para o **parecer da IA** (coluna direita).
   > "Aqui a IA produz uma síntese técnica em linguagem natural —
   > pensada para o supervisor que vai assinar o parecer. Não substitui
   > a auditoria; complementa."
   Ler em voz alta o trecho de **Recomendação**.

4. Descer até a **lista de alertas**. Comentar:
   - "Equipamentos não cadastrados" — abastecimentos que aparecem no
     Infleet mas não têm nenhum equipamento mobilizado correspondente.
   - "Pós-desmobilização" — equipamento já desmobilizado mas continuou
     abastecendo.
   - "Outliers" — consumo fora do padrão histórico do equipamento.
   - "Duplicidade" — possível mesmo abastecimento contado duas vezes.

5. Click em um alerta de **"Não cadastrado"**. Click em **"Reconciliar"**.

### 6:00 — 8:00 | Demo: reconciliação semântica

Ações:
1. O modal abre com sugestões da IA, lado a lado com os candidatos.
2. Apontar para a **confiança** (em %) e a **justificativa**.
   > "A IA olha o nome do equipamento no Infleet — que vem com erro de
   > digitação, abreviação, espaçamento — e propõe o casamento mais
   > provável com algum mobilizado. Mostra a confiança para que o
   > auditor decida se aprova."
3. **Aprovar** a sugestão de maior confiança.
4. Voltar para a tela de auditoria. Apontar que o número de
   "equipamentos não cadastrados" caiu em uma unidade.
   > "Cada aprovação fica registrada com o auditor, timestamp e
   > justificativa. Tudo rastreável."

### 8:00 — 9:00 | Demo: PDF + visão consolidada

Ações:
1. Click em **"Gerar PDF de auditoria"** (botão primário, canto superior
   direito).
2. Abrir PDF na nova aba. Mostrar:
   - O **layout dos indicadores** idêntico à planilha que eles usam.
   - O **parecer da IA** já embutido.
   - O **hash de rastreabilidade** no rodapé.
   > "Esse PDF é o documento oficial. Pode ser arquivado, impresso, ou
   > anexado ao processo no GLPI."
3. Voltar ao app. Click em **"Consolidado"** no menu lateral.
4. Mostrar a **visão das 4 NFs** com semáforo (status), diferença % e
   chips de alerta.
5. Aplicar filtro **"Inconsistentes"** — restam menos linhas.
6. Click em uma linha — leva direto para a auditoria daquela NF.

### 9:00 — 10:00 | Fechamento e roadmap

> "O que vocês viram hoje é o **MVP**. Em 3 dias entregamos a engine
> determinística, a camada de IA, o frontend de auditoria, o PDF e a
> visão consolidada. O que vem agora:"

- **30 dias**: integração direta com GLPI e Infleet via API (eliminar
  exportação manual de xlsx).
- **60 dias**: workflow de aprovação multinível (auditor -> supervisor
  -> contabilidade) e exportação para o ERP.
- **90 dias**: piloto em duas obras adicionais. Auditoria continua, sem
  esperar a NF: o sistema avisa em tempo real quando um abastecimento
  fora do padrão ocorre.

> "A pergunta que fica é: **quais NFs do trimestre passado vocês
> gostariam de auditar primeiro com essa ferramenta?**"

---

## Plano de contingência

| Cenário                          | Ação                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------- |
| API Anthropic offline            | DEMO_MODE=true já cobre. O cache local responde. **Não mencione** o problema.         |
| Backend caiu                     | Janela 1 tem o uvicorn; ctrl+c e re-rode o comando. SQLite já tem todos os dados.     |
| Frontend caiu                    | Janela 2; idem. `pnpm start` em modo produção reinicia < 3s.                          |
| Não carrega a NF clicada         | Volte e clique em outra NF. São 4. Pior caso, abra o PDF já gerado em data/pdfs_amostra/. |
| Pergunta sobre dado específico   | Use a CLI no terminal: `uv run audit-diesel auditar --nf-anterior X --nf-atual Y --json`. |
| Internet caiu                    | Modo offline já garante a demo. Aproveite para reforçar: "veja, nem precisa de internet". |

---

## Perguntas frequentes esperadas (e respostas curtas)

**1. Como vocês escolheram a tolerância de 2%?**
> Veio da própria planilha de vocês — usamos a mesma regra: |diferença| < 2%
> aprova, acima reprova. Pode ser ajustada em uma linha de configuração.

**2. O sistema substitui o auditor?**
> Não. Ele acelera a parte braçal — cruzar 4 fontes, identificar
> divergências, calcular indicadores. A decisão final é sempre do auditor;
> ele que aprova ou recusa cada reconciliação.

**3. O parecer da IA é auditável?**
> Sim. Cada parecer guarda provider, modelo, latência, tokens. O texto
> entra no PDF junto com o hash dos indicadores. Se um número mudar, o
> hash muda.

**4. Quanto custa a IA por auditoria?**
> Em modo provider-agnóstico: cerca de 3.000 tokens por parecer. Com
> Qwen-32B no OpenRouter, isso dá menos de R$ 0,02 por auditoria. Com
> Claude Opus, na faixa de R$ 0,30. Pode ser trocado a qualquer momento.

**5. E se o LLM errar a sugestão de reconciliação?**
> Cada sugestão tem confiança. O auditor decide se aprova. Sugestões
> recusadas também ficam registradas e melhoram a heurística futura.

**6. Como vocês lidam com NF cancelada?**
> Hoje a NF cancelada precisa ser removida na fonte (GLPI). O sistema
> reprocessa na próxima ingestão. Em V2 podemos absorver eventos de
> cancelamento via webhook.

**7. Quantos meses de histórico aguentam?**
> O SQLite local aguenta fácil 5 anos de dados de uma obra do tamanho
> da ARCO. Se for escalar para todo o consórcio, recomendamos PostgreSQL.

**8. Tem versão mobile?**
> A interface já é responsiva. Para uso pesado em campo (foto de
> abastecimento), recomendamos um app dedicado em V2.

**9. Quanto tempo para implementar de verdade?**
> O MVP vocês estão vendo. Para entrar em produção com integração real
> com GLPI/Infleet, estimamos 4 a 6 semanas, dependendo da disponibilidade
> de credenciais e ambiente de homologação.

**10. E LGPD?**
> Os dados não têm informação pessoal — são placas, NFs, valores. O CNPJ
> do fornecedor é dado público. O sistema roda on-premise; nada sai do
> ambiente de vocês.

---

## Checklist 60 segundos antes de começar

- [ ] DEMO_MODE=true exportado
- [ ] Backend rodando, /healthz responde com `demo_mode: true`
- [ ] Frontend em `pnpm start` (producao), nao `pnpm dev`
- [ ] Chrome em zoom 110%, tela cheia, modo presenter
- [ ] Notificacoes silenciadas
- [ ] Bateria > 50% ou tomada conectada
- [ ] Roteiro aberto na segunda tela
- [ ] Respiracao calma, primeira frase memorizada
