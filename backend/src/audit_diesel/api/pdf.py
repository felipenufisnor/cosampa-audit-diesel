"""Geracao do PDF de auditoria via Jinja2 + WeasyPrint.

Decisao: Jinja2 monta um HTML autonomo (com `<style>` inline) para evitar
hot-paths dependentes de I/O extra dentro do WeasyPrint. O CSS contem as
regras `@page` que controlam margens, header rodando e rodape com paginacao
+ hash de integridade. Toda a tipografia usa fontes DejaVu (instaladas por
padrao em distros Linux usadas para servir o PDF) com fallback para Georgia
no macOS de desenvolvimento; em todos os ambientes testados o resultado
visual fica equivalente.

`render_auditoria_pdf` recebe os SQLModel ja carregados pelo router e
devolve `bytes` do PDF, deixando a parte HTTP (Content-Disposition, nome
do arquivo) para o caller. Isso permite reuso pelo script de smoke-test
que grava amostras em `data/pdfs_amostra/` sem precisar do FastAPI.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from audit_diesel.models import Alerta, Auditoria, Checklist, ReconciliacaoAprovada

log = structlog.get_logger("audit_diesel.api.pdf")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
CSS_PATH = TEMPLATES_DIR / "_styles.css"

TIPO_LABELS = {
    "NAO_CADASTRADO": "Equipamentos nao cadastrados",
    "POS_DESMOB": "Abastecimentos pos-desmobilizacao",
    "OUTLIER": "Outliers de consumo",
    "DUPLICIDADE": "Possiveis duplicidades",
}


@dataclass
class ReconciliacaoView:
    """Linha de reconciliacao ja resolvida com o nome do mobilizado."""

    abastecimento_id: int
    mobilizado_id: int
    mobilizado_label: str
    auditor: str
    confianca: float | None
    justificativa: str | None
    criada_em: datetime


def _format_brl(v: float | None) -> str:
    if v is None:
        return "—"
    n = f"{v:,.2f}"
    # converte 1,234.56 -> 1.234,56 (estilo BR)
    return "R$ " + n.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_litros(v: float | None) -> str:
    if v is None:
        return "—"
    n = f"{v:,.2f}"
    return n.replace(",", "X").replace(".", ",").replace("X", ".") + " L"


def _format_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v * 100:,.2f}".replace(".", ",") + " %"


def _format_data(d: Any) -> str:
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _format_datahora(d: Any) -> str:
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y %H:%M")
    return str(d)


def _markdown_basico(md: str) -> str:
    """Conversao minima markdown -> HTML para o parecer.

    Mantemos a regra simples: o parecer da IA usa quase sempre headings
    (#, ##), listas (-) e enfase (**). Importar uma lib so para isso
    aumentaria o footprint do projeto sem ganho real para a POC.
    """
    if not md:
        return ""
    text = md.strip()
    # escapa < e > primeiro
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # headings (ordem importa: ### antes de ##)
    text = re.sub(r"^###\s+(.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)

    # bold/italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)

    lines = text.split("\n")
    out: list[str] = []
    in_ul = False
    in_ol = False
    para_buf: list[str] = []

    def flush_para() -> None:
        nonlocal para_buf
        if para_buf:
            out.append("<p>" + " ".join(para_buf).strip() + "</p>")
            para_buf = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_para()
            close_lists()
            continue
        # Heading ja virou tag em HTML
        if line.startswith("<h"):
            flush_para()
            close_lists()
            out.append(line)
            continue
        m_ul = re.match(r"^[-*]\s+(.+)$", line)
        m_ol = re.match(r"^\d+\.\s+(.+)$", line)
        if m_ul:
            flush_para()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{m_ul.group(1)}</li>")
            continue
        if m_ol:
            flush_para()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{m_ol.group(1)}</li>")
            continue
        close_lists()
        para_buf.append(line)

    flush_para()
    close_lists()
    return "\n".join(out)


def _hash_indicadores(auditoria: Auditoria) -> str:
    """SHA256 dos indicadores numericos. Garantia de rastreabilidade do PDF."""
    payload = {
        "auditoria_id": auditoria.id,
        "nf_anterior": auditoria.nf_anterior,
        "nf_atual": auditoria.nf_atual,
        "estoque_inicial_anterior": round(auditoria.estoque_inicial_anterior, 4),
        "quantidade_descarregada_anterior": round(
            auditoria.quantidade_descarregada_anterior, 4
        ),
        "estoque_final_teorico_anterior": round(
            auditoria.estoque_final_teorico_anterior, 4
        ),
        "saidas_registradas_litros": round(auditoria.saidas_registradas_litros, 4),
        "saidas_registradas_custo": round(auditoria.saidas_registradas_custo, 2),
        "estoque_inicial_atual": round(auditoria.estoque_inicial_atual, 4),
        "saida_teorica_litros": round(auditoria.saida_teorica_litros, 4),
        "diferenca_litros": round(auditoria.diferenca_litros, 4),
        "diferenca_percentual": round(auditoria.diferenca_percentual, 6),
        "qtd_equipamentos_nao_cadastrados": auditoria.qtd_equipamentos_nao_cadastrados,
        "validacao_final": auditoria.validacao_final,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]  # 16 chars sao suficientes para o footer


def _agrupar_alertas(alertas: list[Alerta]) -> dict[str, list[Alerta]]:
    """Agrupa alertas por tipo preservando ordem de severidade interna."""
    sev_order = {"alta": 0, "media": 1, "baixa": 2}
    grupos: dict[str, list[Alerta]] = {}
    for a in alertas:
        grupos.setdefault(a.tipo, []).append(a)
    for tipo, lst in grupos.items():
        lst.sort(key=lambda x: sev_order.get(x.severidade, 99))
    return grupos


def _filename_for(auditoria: Auditoria, gerado_em: datetime) -> str:
    return (
        f"auditoria_NF_{auditoria.nf_atual}_"
        f"{gerado_em.strftime('%Y%m%d')}.pdf"
    )


def render_auditoria_pdf(
    *,
    auditoria: Auditoria,
    checklist: Checklist,
    alertas: list[Alerta],
    reconciliacoes: list[ReconciliacaoView],
    parecer_meta: dict[str, Any] | None = None,
    tolerancia_pct: float = 0.02,
) -> tuple[bytes, str]:
    """Renderiza o PDF e devolve (bytes, filename)."""
    from weasyprint import HTML  # import lazy: WeasyPrint puxa libs nativas

    gerado_em = datetime.now()
    integrity_hash = _hash_indicadores(auditoria)
    css = CSS_PATH.read_text(encoding="utf-8")

    parecer_html = _markdown_basico(auditoria.parecer_ia or "")
    alertas_por_tipo = _agrupar_alertas(alertas)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        fmt_brl=_format_brl,
        fmt_litros=_format_litros,
        fmt_pct=_format_pct,
        fmt_data=_format_data,
        fmt_datahora=_format_datahora,
        tipo_labels=TIPO_LABELS,
    )

    template = env.get_template("auditoria_pdf.html.j2")
    html_str = template.render(
        auditoria=auditoria,
        checklist=checklist,
        alertas_por_tipo=alertas_por_tipo,
        parecer_html=parecer_html,
        parecer_meta=parecer_meta,
        reconciliacoes=reconciliacoes,
        gerado_em=gerado_em,
        gerado_em_str=gerado_em.strftime("%d/%m/%Y %H:%M"),
        integrity_hash=integrity_hash,
        inline_css=css,
        tolerancia_pct=tolerancia_pct,
    )

    pdf_bytes = HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf()
    filename = _filename_for(auditoria, gerado_em)
    log.info(
        "pdf.rendered",
        auditoria_id=auditoria.id,
        bytes=len(pdf_bytes),
        filename=filename,
    )
    return pdf_bytes, filename


def montar_reconciliacoes_view(
    items: list[ReconciliacaoAprovada],
    mobilizados_index: dict[int, str],
) -> list[ReconciliacaoView]:
    """Aplica labels de mobilizado para enriquecer a listagem do PDF."""
    return [
        ReconciliacaoView(
            abastecimento_id=r.abastecimento_id,
            mobilizado_id=r.mobilizado_id,
            mobilizado_label=mobilizados_index.get(r.mobilizado_id, "—"),
            auditor=r.auditor,
            confianca=r.confianca,
            justificativa=r.justificativa,
            criada_em=r.criada_em,
        )
        for r in items
    ]
