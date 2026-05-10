# ADR-0003: PDF via WeasyPrint + Jinja2 ao inves de Puppeteer/ReportLab

- Status: aceito
- Data: 2026-05-09 (Dia 3)

## Contexto

O entregavel oficial da auditoria e um PDF parecido com o relatorio que
hoje sai da planilha do cliente. Tabelas financeiras (linhas zebradas
sutis, alinhamento de numero a direita, tipografia consistente) e
acentuacao em portugues precisam funcionar sem retoque manual.

## Alternativas consideradas

1. **Puppeteer / Playwright (Chromium headless)**.
   - Pros: render fiel ao Chrome; suporte total a CSS.
   - Contras: dependencia gigante (Chromium ~200MB); custo de RAM por
     processo; complexidade de gerenciar pool de browsers num backend
     Python; portabilidade fragil em Linux containerizado.

2. **ReportLab (puro Python)**.
   - Pros: zero dependencia nativa; super estavel.
   - Contras: API procedural baixa (canvas + Story + Flowables);
     escrever um relatorio com tabela espelhando a planilha do cliente
     exige codigo extenso; CSS nao se aplica.

3. **WeasyPrint (HTML/CSS -> PDF, baseado em pango/cairo)**.
   - Pros: HTML+CSS como linguagem do template; Jinja2 cuida de logica;
     suporte rico a regras `@page`, `string-set`, contadores e fontes
     embutidas; rapida para 1-3 paginas; tipografia DejaVu disponivel
     nas distros alvo.
   - Contras: depende de libs nativas (libpango, libcairo, libgdk-pixbuf,
     libffi). No macOS exige `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
     em frente do comando.

## Decisao

Adotada a opcao 3. Templates Jinja2 em
`backend/src/audit_diesel/api/templates/`; modulo `api/pdf.py`
parametriza, monta o HTML autonomo (CSS inline) e chama
`weasyprint.HTML(...).write_pdf()`.

## Consequencias

- Relatorio com aparencia de documento oficial em < 1s para 1 pagina A4.
- Hash sha256 dos indicadores entra no rodape via `string-set` do CSS,
  garantindo rastreabilidade visual.
- Em macOS, todos os scripts/tarefas que disparam o WeasyPrint precisam
  do `DYLD_FALLBACK_LIBRARY_PATH`. Documentado no README.
- Em Linux/container, a dependencia se resolve via `apt install libpango-1.0-0
  libcairo2 libgdk-pixbuf-2.0-0`.
- Conversor markdown -> HTML simples implementado em `pdf.py`
  (regex-based) para evitar trazer mais uma dependencia so para o
  parecer.
