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

> "Hoje, quando voces recebem uma NF de diesel, alguem do escritorio
> abre tres planilhas — o checklist do GLPI, a lista de mobilizados da
> Gestao de Projetos e o relatorio do Infleet — e cruza linha a linha
> para confirmar se o consumo bate com o que entrou no tanque. Esse
> processo, hoje, leva **dias**. E como sao mais de 2.000 abastecimentos
> por mes, e humanamente impossivel auditar tudo. O que vamos mostrar
> agora e um agente que faz exatamente esse cruzamento — em segundos,
> com auditoria rastreavel."

Pontos a transmitir nestes 60 segundos:
- Nao e "IA generica que adivinha". E uma engine deterministica + um
  parecer de IA opcional para sintese.
- A planilha "AUDITORIA DO DIESEL_0" continua sendo a fonte da verdade
  contabil — nos a reproduzimos integralmente para que voces reconhecam.
- Os dados sao reais: as 4 NFs do mes de marco/2026.

### 1:00 — 3:00 | Demo: dashboard

Acoes:
1. Mostrar a tela inicial `/`. Apontar para os **4 stats cards**:
   - "X abastecimentos no periodo"
   - "Y% de custo nao cadastrado" — falar: "Esse e o problema que estamos
     resolvendo: 22 mil reais em diesel sem placa identificada."
   - "Z NFs no periodo"
   - "N equipamentos mobilizados"
2. Apontar para a **tabela de NFs**. Comentar que sao as 4 NFs reais.
3. Click em **"Auditar"** da NF 8187.
4. No dialogo, **selecionar 8108 como NF anterior** (default ja apontado).
5. Click em **"Confirmar auditoria"**. Aguardar 1 a 2 segundos.

> "Repare que o sistema escolhe a NF anterior automaticamente — porque
> a auditoria e sempre entre duas NFs sequenciais da mesma obra. E o
> que o auditor define como janela temporal."

### 3:00 — 6:00 | Demo: auditoria detalhada

Acoes:
1. Apontar para o **bloco de indicadores** (centro da tela).
   > "Esse layout — estoque inicial, descarregamento, saida teorica,
   > diferenca apurada — e exatamente o que voces tem na aba 'AUDITORIA
   > DO DIESEL_0' da planilha. A diferenca e que aqui ele se preenche
   > sozinho a partir das 4 fontes."

2. Apontar para a **diferenca em litros e percentual**.
   > "Quando essa diferenca passa de 2%, a NF entra como inconsistente
   > automaticamente — regra que voces ja usam hoje."

3. Apontar para o **parecer da IA** (coluna direita).
   > "Aqui a IA produz uma sintese tecnica em linguagem natural —
   > pensada para o supervisor que vai assinar o parecer. Nao substitui
   > a auditoria; complementa."
   Ler em voz alta o trecho de **Recomendacao**.

4. Descer ate a **lista de alertas**. Comentar:
   - "Equipamentos nao cadastrados" — abastecimentos que aparecem no
     Infleet mas nao tem nenhum equipamento mobilizado correspondente.
   - "Pos-desmobilizacao" — equipamento ja desmobilizado mas continuou
     abastecendo.
   - "Outliers" — consumo fora do padrao historico do equipamento.
   - "Duplicidade" — possivel mesmo abastecimento contado duas vezes.

5. Click em um alerta de **"Nao cadastrado"**. Click em **"Reconciliar"**.

### 6:00 — 8:00 | Demo: reconciliacao semantica

Acoes:
1. O modal abre com sugestoes da IA, lado a lado com os candidatos.
2. Apontar para a **confianca** (em %) e a **justificativa**.
   > "A IA olha o nome do equipamento no Infleet — que vem com erro de
   > digitacao, abreviacao, espacamento — e propoe o casamento mais
   > provavel com algum mobilizado. Mostra a confianca para que o
   > auditor decida se aprova."
3. **Aprovar** a sugestao de maior confianca.
4. Voltar para a tela de auditoria. Apontar que o numero de
   "equipamentos nao cadastrados" caiu em uma unidade.
   > "Cada aprovacao fica registrada com o auditor, timestamp e
   > justificativa. Tudo rastreavel."

### 8:00 — 9:00 | Demo: PDF + visao consolidada

Acoes:
1. Click em **"Gerar PDF de auditoria"** (botao primario, canto superior
   direito).
2. Abrir PDF na nova aba. Mostrar:
   - O **layout dos indicadores** identico a planilha que eles usam.
   - O **parecer da IA** ja embutido.
   - O **hash de rastreabilidade** no rodape.
   > "Esse PDF e o documento oficial. Pode ser arquivado, impresso, ou
   > anexado ao processo no GLPI."
3. Voltar ao app. Click em **"Consolidado"** no menu lateral.
4. Mostrar a **visao das 4 NFs** com semaforo (status), diferenca % e
   chips de alerta.
5. Aplicar filtro **"Inconsistentes"** — restam menos linhas.
6. Click em uma linha — leva direto para a auditoria daquela NF.

### 9:00 — 10:00 | Fechamento e roadmap

> "O que voces viram hoje e o **MVP**. Em 3 dias entregamos a engine
> deterministica, a camada de IA, o frontend de auditoria, o PDF e a
> visao consolidada. O que vem agora:"

- **30 dias**: integracao direta com GLPI e Infleet via API (eliminar
  exportacao manual de xlsx).
- **60 dias**: workflow de aprovacao multi-nivel (auditor -> supervisor
  -> contabilidade) e exportacao para o ERP.
- **90 dias**: piloto em duas obras adicionais. Auditoria continua, sem
  esperar a NF: o sistema avisa em tempo real quando um abastecimento
  fora do padrao ocorre.

> "A pergunta que fica e: **quais NFs do trimestre passado voces
> gostariam de auditar primeiro com essa ferramenta?**"

---

## Plano de contingencia

| Cenario                          | Acao                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------- |
| API Anthropic offline            | DEMO_MODE=true ja cobre. O cache local responde. **Nao mencione** o problema.         |
| Backend caiu                     | Janela 1 tem o uvicorn; ctrl+c e re-rode o comando. SQLite ja tem todos os dados.     |
| Frontend caiu                    | Janela 2; idem. `pnpm start` em modo producao restart < 3s.                           |
| Nao carrega a NF clicada         | Volte e clique em outra NF. Sao 4. Pior caso, abra o PDF ja gerado em data/pdfs_amostra/. |
| Pergunta sobre dado especifico   | Use a CLI no terminal: `uv run audit-diesel auditar --nf-anterior X --nf-atual Y --json`. |
| Internet caiu                    | Modo offline ja garante a demo. Aproveite para reforcar: "veja, nem precisa de internet". |

---

## Perguntas frequentes esperadas (e respostas curtas)

**1. Como voces escolheram a tolerancia de 2%?**
> Veio da propria planilha de voces — usamos a mesma regra: |diferenca| < 2%
> aprova, acima reprova. Pode ser ajustada em uma linha de configuracao.

**2. O sistema substitui o auditor?**
> Nao. Ele acelera a parte braçal — cruzar 4 fontes, identificar
> divergencias, calcular indicadores. A decisao final e sempre do auditor;
> ele que aprova ou recusa cada reconciliacao.

**3. O parecer da IA e auditavel?**
> Sim. Cada parecer guarda provider, modelo, latencia, tokens. O texto
> entra no PDF junto com o hash dos indicadores. Se um numero mudar, o
> hash muda.

**4. Quanto custa a IA por auditoria?**
> Em modo provider-agnostico: cerca de 3.000 tokens por parecer. Com
> Qwen-32B no OpenRouter, isso da menos de R$ 0,02 por auditoria. Com
> Claude Opus, na faixa de R$ 0,30. Pode ser trocado a qualquer momento.

**5. E se o LLM errar a sugestao de reconciliacao?**
> Cada sugestao tem confianca. O auditor decide se aprova. Sugestoes
> recusadas tambem ficam registradas e melhoram a heuristica futura.

**6. Como voces lidam com NF cancelada?**
> Hoje a NF cancelada precisa ser removida na fonte (GLPI). O sistema
> reprocessa na proxima ingestao. Em V2 podemos absorver eventos de
> cancelamento via webhook.

**7. Quantos meses de historico aguentam?**
> O SQLite local aguenta facil 5 anos de dados de uma obra do tamanho
> da ARCO. Se for escalar para todo o consorcio, recomendamos PostgreSQL.

**8. Tem versao mobile?**
> A interface ja e responsiva. Para uso pesado em campo (foto de
> abastecimento), recomendamos um app dedicado em V2.

**9. Quanto tempo para implementar de verdade?**
> O MVP voces estao vendo. Para entrar em producao com integracao real
> com GLPI/Infleet, estimamos 4 a 6 semanas, dependendo da disponibilidade
> de credenciais e ambiente de homologacao.

**10. E LGPD?**
> Os dados nao tem informacao pessoal — sao placas, NFs, valores. O CNPJ
> do fornecedor e dado publico. O sistema roda on-premise; nada sai do
> ambiente de voces.

---

## Checklist 60 segundos antes de comecar

- [ ] DEMO_MODE=true exportado
- [ ] Backend rodando, /healthz responde com `demo_mode: true`
- [ ] Frontend em `pnpm start` (producao), nao `pnpm dev`
- [ ] Chrome em zoom 110%, tela cheia, modo presenter
- [ ] Notificacoes silenciadas
- [ ] Bateria > 50% ou tomada conectada
- [ ] Roteiro aberto na segunda tela
- [ ] Respiracao calma, primeira frase memorizada
