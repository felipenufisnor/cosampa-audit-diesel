# ADR-0002: Camada de IA provider-agnostica (OpenAI-compatible)

- Status: aceito
- Data: 2026-05-02 (Dia 2)

## Contexto

A POC precisava do parecer da IA mas o cliente nao tem decisao formada
sobre qual provider usar em producao (Anthropic, OpenAI, Azure, modelo
on-prem via Ollama, etc). Travar o codigo em um SDK especifico criaria
divida de migracao.

## Alternativas consideradas

1. **Anthropic SDK direto**: usar `anthropic.Anthropic()` por toda parte.
   - Pros: tipagem rica, suporte oficial, prompt caching.
   - Contras: amarra a Anthropic. Trocar para OpenAI/local exigiria
     refactor profundo. Cliente perderia poder de barganha de custo.

2. **LangChain / LiteLLM**: framework de abstracao multi-provider.
   - Pros: muitos providers suportados.
   - Contras: dependencia pesada, API menos estavel, debugging mais
     dificil. Para uma POC e overkill.

3. **SDK `openai` apontando para qualquer base_url OpenAI-compatible**.
   - Pros: virtualmente todos os providers expoem essa API
     (OpenRouter, Together, Groq, Fireworks, vLLM, Ollama, Azure).
     Trocar provider e mudar 2 variaveis de ambiente. Nenhuma logica
     de chamada precisa mudar.
   - Contras: prompt caching especifico de cada provider nao e
     transparente; tool calling tem pequenas diferencas de schema.

## Decisao

Adotada a opcao 3. O modulo `ai/provider.py` define `LLMProvider` como
Protocol; `OpenAICompatibleProvider` usa o SDK `openai`; `OfflineProvider`
serve fixtures determinisicas.

## Consequencias

- Trocar de provider = trocar `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
  no `.env`. Sem deploy.
- O modo offline e gratuito e cobre testes, CI e a apresentacao da demo
  sem chave de API real.
- A camada `ChatClient` adiciona retry com backoff e fallback de modelo
  por cima do provider — comportamento que precisa funcionar igual em
  qualquer LLM.
- Custo por auditoria fica visivel: o `ParecerMeta` retorna tokens e
  latencia, exibidos no rodape do parecer.
