# ADR-0001: Engine determinística como espinha dorsal; LLM como camada secundária

- Status: aceito
- Data: 2026-04-30 (Dia 1)

## Contexto

A POC precisava decidir o quanto de lógica de auditoria seria delegada
diretamente para um LLM versus implementada em código determinístico. A
auditoria de diesel envolve cálculos contábeis sensíveis (estoque inicial,
saída teórica, diferença apurada) que têm regra clara na planilha
"AUDITORIA DO DIESEL_0" e tolerância de 2% definida pelo cliente.

## Alternativas consideradas

1. **Tudo via LLM**: passar dados crus + prompt detalhado e deixar o
   modelo calcular indicadores e gerar parecer final.
   - Pros: menos código. Suporta facilmente novos tipos de auditoria.
   - Contras: números podem variar entre execuções; alucinações
     financeiras inaceitáveis; auditoria não reproduzível; custo
     proporcional ao volume de dados.

2. **Tudo determinístico, sem LLM**: implementar todas as 4 checagens
   e o parecer textual em código.
   - Pros: rápido, barato, totalmente reproduzível.
   - Contras: parecer textual ficaria mecânico; reconciliação semântica
     (nome de equipamento com erro de digitação -> placa cadastrada)
     requer fuzzy matching frio que dá resultado pior que LLM.

3. **Engine determinística + LLM em pontos específicos**: números e
   regras vêm de código; LLM gera (a) parecer textual, (b) sugestões de
   reconciliação para abastecimentos não cadastrados.
   - Pros: números 100% reproduzíveis; LLM atua só onde adiciona valor;
     custo baixo (poucos tokens por auditoria); fácil de auditar.
   - Contras: dois caminhos de código (mais superfície).

## Decisão

Adotada a opção 3.

## Consequências

- Os indicadores §4 (`audit/indicators.py`) e os 4 alertas
  (`audit/alerts/*.py`) são código puro, testado por unidade.
- O LLM aparece em dois lugares isolados: `ai/parecer.py` e
  `ai/reconciliador.py`. Ambos podem rodar em modo offline (fixtures
  determinísticas) sem afetar o resto do sistema.
- A auditoria pode ser executada com `gerar_parecer=False` e ainda assim
  produz o número contábil correto.
- Auditabilidade fica trivial: o hash sha256 dos indicadores
  (gerado no PDF) detecta qualquer alteração numérica.
