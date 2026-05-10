# ADR-0004: DEMO_MODE com cache em disco para resiliencia da apresentacao

- Status: aceito
- Data: 2026-05-09 (Dia 3)

## Contexto

A apresentacao da POC e o ponto onde o consorcio decide se segue com a
solucao. Tres riscos colocam o show em perigo no dia:

1. Internet do cliente cai ou a API do provider de LLM esta lenta.
2. Resposta do LLM e nao deterministica — pode variar palavras, vir
   menor, vir mais agressiva, dependendo do humor do modelo.
3. Custo de tokens por chamada acumula durante ensaios.

## Alternativas consideradas

1. **Confiar na API ao vivo durante a demo**.
   - Pros: mais "vivo".
   - Contras: variabilidade da resposta, latencia imprevisivel, risco
     de queda. Inaceitavel para uma apresentacao decisiva.

2. **Mockar tudo via fixtures hardcoded**.
   - Pros: total controle.
   - Contras: o sistema vira teatro; perde credibilidade quando o
     cliente perceber que e tudo placeholder.

3. **Snapshot de respostas reais em disco, ativado por flag**.
   - Pros: respostas determinisicas, instantaneas (< 200ms), idempotentes;
     a logica do sistema e a mesma de producao; basta desligar a flag
     para voltar ao modo "ao vivo"; e auditavel (JSON legivel).
   - Contras: precisa popular o cache antes da demo; cache pode ficar
     desatualizado se o codigo do prompt mudar.

## Decisao

Adotada a opcao 3. Implementacao em `audit_diesel/ai/cache.py`:

- `DEMO_MODE=record`: chama o provider normalmente e grava cada resposta
  em `data/demo_cache/`.
- `DEMO_MODE=true`: le do cache; cai pro provider apenas em cache miss.
- `DEMO_MODE=off` (default): sem cache, comportamento normal.

Os arquivos do cache sao indexados por par de NFs
(`parecer_NF_{nf_atual}_anterior_{nf_anterior}.json`,
`reconciliacao_par_{nf_atual}_anterior_{nf_anterior}.json`), nao por
auditoria_id — isso resolve o detalhe pratico de que o id muda quando
a auditoria e recriada apos uma reconciliacao aprovada.

## Consequencias

- Apresentacao roda mesmo com WiFi desligado — cache + SQLite local
  cobrem tudo.
- O `GET /healthz` expoe `demo_mode: bool` para o frontend exibir um
  badge discreto, evitando duvida do cliente sobre se esta vendo
  resposta "real" ou cacheada.
- Script `scripts/popular_cache_demo.py` e idempotente: roda quando
  quiser, sobrescreve o cache, regenera os PDFs amostra. Tempo total
  de execucao: ~1.4s usando o offline provider.
- Recomendacao operacional: rodar o script de novo sempre que mexer
  em prompts ou em logica de alertas.
