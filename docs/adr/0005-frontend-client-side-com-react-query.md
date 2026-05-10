# ADR-0005: Frontend 100% client-side com react-query, sem SSR/SSG

- Status: aceito
- Data: 2026-05-02 (Dia 2)

## Contexto

Next.js 16 incentiva Server Components, Server Actions e SSR por
default. A POC roda inteiramente local, contra um backend FastAPI no
mesmo host, e o publico final acessa via `localhost`. Adotar SSR
introduziria complexidade sem entregar nenhum dos beneficios tradicionais
(SEO, time-to-first-byte para usuarios remotos).

## Alternativas consideradas

1. **Next.js com Server Components consumindo a FastAPI**.
   - Pros: bundle menor no client; SEO (irrelevante aqui).
   - Contras: precisa replicar tipos / logica de autenticacao no server;
     Server Actions exigem boilerplate adicional; debugging fica em duas
     camadas.

2. **SPA puro (Vite + React Router)**.
   - Pros: simples e rapido.
   - Contras: o time ja conhece Next; trocar de stack so para a POC
     atrapalha onboarding futuro.

3. **Next.js com App Router mas tudo `"use client"` + react-query**.
   - Pros: estrutura familiar; react-query lida com cache, retry, stale
     time, prefetch on hover; zustand para estado de UI; types em
     `lib/types.ts` espelham o backend manualmente (modelos pequenos,
     codegen nao compensa).
   - Contras: bundle inicial maior que SSR otimizado.

## Decisao

Adotada a opcao 3.

## Consequencias

- Cada hook `useNFs`, `useAuditoria`, `useConsolidado` e um wrapper
  trivial em torno de `useQuery`. Cache compartilhado por chave.
- `prefetchQuery` no `onMouseEnter` da tabela do dashboard reduz a zero
  a latencia quando o auditor clica em "Auditar".
- Tipos do backend sao replicados em `lib/types.ts`. Quando o schema
  pydantic muda, ajustar manualmente. Para uma POC com ~10 modelos isso
  nao justifica codegen (openapi-typescript-codegen, etc.).
- Toda a navegacao e client-side (`Link`), sem refresh; o badge de
  DEMO_MODE no canto inferior direito persiste em todas as rotas.
