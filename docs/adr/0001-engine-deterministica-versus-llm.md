# ADR-0001: Engine deterministica como espinha dorsal; LLM como camada secundaria

- Status: aceito
- Data: 2026-04-30 (Dia 1)

## Contexto

A POC precisava decidir o quanto de logica de auditoria seria delegada
diretamente para um LLM versus implementada em codigo deterministico. A
auditoria de diesel envolve calculos contabeis sensiveis (estoque inicial,
saida teorica, diferenca apurada) que tem regra clara na planilha
"AUDITORIA DO DIESEL_0" e tolerancia de 2% definida pelo cliente.

## Alternativas consideradas

1. **Tudo via LLM**: passar dados crus + prompt detalhado e deixar o
   modelo calcular indicadores e gerar parecer final.
   - Pros: menos codigo. Suporta facilmente novos tipos de auditoria.
   - Contras: numeros podem variar entre execucoes; alucinacoes
     financeiras inaceitaveis; auditoria nao reproduzivel; custo
     proporcional ao volume de dados.

2. **Tudo deterministico, sem LLM**: implementar todas as 4 checagens
   e o parecer textual em codigo.
   - Pros: rapido, barato, totalmente reproduzivel.
   - Contras: parecer textual ficaria mecanico; reconciliacao semantica
     (nome de equipamento com erro de digitacao -> placa cadastrada)
     requer fuzzy matching frio que da resultado pior que LLM.

3. **Engine deterministica + LLM em pontos especificos**: numeros e
   regras vem de codigo; LLM gera (a) parecer textual, (b) sugestoes de
   reconciliacao para abastecimentos nao cadastrados.
   - Pros: numeros 100% reproduziveis; LLM atua so onde adiciona valor;
     custo baixo (poucos tokens por auditoria); facil de auditar.
   - Contras: dois caminhos de codigo (mais superficie).

## Decisao

Adotada a opcao 3.

## Consequencias

- Os indicadores §4 (`audit/indicators.py`) e os 4 alertas
  (`audit/alerts/*.py`) sao codigo puro, testado por unidade.
- O LLM aparece em dois lugares isolados: `ai/parecer.py` e
  `ai/reconciliador.py`. Ambos podem rodar em modo offline (fixtures
  determinisicas) sem afetar o resto do sistema.
- A auditoria pode ser executada com `gerar_parecer=False` e ainda assim
  produz o numero contabil correto.
- Auditabilidade fica trivial: o hash sha256 dos indicadores
  (gerado no PDF) detecta qualquer alteracao numerica.
