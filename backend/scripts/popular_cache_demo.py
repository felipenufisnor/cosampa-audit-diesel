"""Popula `data/demo_cache/` com as respostas das 3 auditorias da demo.

Rode com:
    DEMO_MODE=record uv run python scripts/popular_cache_demo.py

O script:
  1. Forca AUDIT_AI_OFFLINE=1 (usa as fixtures determinisicas do offline
     provider; nao gasta tokens nem depende de internet).
  2. Para cada par (8108->8187, 8187->8278, 8278->8328):
     a. Roda a auditoria via AuditEngine + GeradorParecer (gera parecer e
        grava em parecer_NF_{nf_atual}_anterior_{nf_anterior}.json).
     b. Roda o ReconciliadorSemantico (grava sugestoes em
        reconciliacao_par_{nf_atual}_anterior_{nf_anterior}.json).
  3. Renderiza o PDF de cada auditoria em `data/pdfs_amostra/`.

Apos rodar uma vez, o backend pode subir com DEMO_MODE=true e respondera
a partir do cache, sem chamar nenhum provider externo.

Idempotente: pode ser rodado quantas vezes quiser (sobrescreve o cache).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Settings sao construidas no momento do import dos modulos da app, entao
# definimos as flags ANTES de importar qualquer coisa de audit_diesel.
os.environ.setdefault("AUDIT_AI_OFFLINE", "1")
os.environ.setdefault("DEMO_MODE", "record")

# Garante que o pacote local seja importavel quando rodado direto:
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqlmodel import Session, select  # noqa: E402

from audit_diesel.ai.client import ChatClient  # noqa: E402
from audit_diesel.ai.parecer import GeradorParecer  # noqa: E402
from audit_diesel.ai.reconciliador import ReconciliadorSemantico  # noqa: E402
from audit_diesel.api import pdf as pdf_render  # noqa: E402
from audit_diesel.api.deps import _engine  # noqa: E402
from audit_diesel.audit.engine import AuditEngine  # noqa: E402
from audit_diesel.config import TOLERANCIA_PERCENTUAL, get_settings  # noqa: E402
from audit_diesel.models import (  # noqa: E402
    Alerta,
    Auditoria,
    Checklist,
    Mobilizado,
    ReconciliacaoAprovada,
)

PARES_DEMO: list[tuple[str, str]] = [
    ("8108", "8187"),
    ("8187", "8278"),
    ("8278", "8328"),
]


def _print(*args: object) -> None:
    print(" ".join(str(a) for a in args), flush=True)


def main() -> int:
    settings = get_settings()
    cache_dir = settings.demo_cache_path
    cache_dir.mkdir(parents=True, exist_ok=True)
    _print(f"[demo-cache] modo:   {settings.demo_mode}")
    _print(f"[demo-cache] dir:    {cache_dir}")
    _print(f"[demo-cache] offline AI: {settings.audit_ai_offline}")
    _print(f"[demo-cache] pares:  {PARES_DEMO}")

    pdfs_dir = ROOT / "data" / "pdfs_amostra"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    engine = _engine()
    chat = ChatClient(settings=settings)

    t_start = time.perf_counter()
    sucesso = 0
    erros: list[str] = []

    for nf_anterior, nf_atual in PARES_DEMO:
        _print(f"\n--- {nf_anterior} -> {nf_atual} ---")
        try:
            with Session(engine) as session:
                # 1) Auditoria + parecer.
                audit_engine = AuditEngine(session)
                resultado = audit_engine.auditar(nf_anterior, nf_atual)
                _print(
                    f"[audit] id={resultado.auditoria.id}"
                    f" valid={resultado.auditoria.validacao_final}"
                    f" alertas={len(resultado.alertas)}"
                )

                gerador = GeradorParecer(client=chat)
                par = gerador.gerar(resultado.to_dict())
                resultado.auditoria.parecer_ia = par.markdown
                session.add(resultado.auditoria)
                session.commit()
                session.refresh(resultado.auditoria)
                _print(
                    f"[parecer] words={len(par.markdown.split())}"
                    f" provider={par.provider}"
                )

                # 2) Reconciliacao (so faz sentido se ha alertas NAO_CADASTRADO).
                rec = ReconciliadorSemantico(session=session, client=chat)
                sugestoes = rec.sugerir_para_auditoria(int(resultado.auditoria.id or 0))
                _print(f"[reconc] sugestoes={len(sugestoes)}")

                # 3) PDF de amostra.
                checklist = session.exec(
                    select(Checklist).where(
                        Checklist.nota_fiscal == resultado.auditoria.nf_atual
                    )
                ).first()
                if checklist is None:
                    raise RuntimeError(
                        f"Checklist da NF {resultado.auditoria.nf_atual} nao "
                        "encontrado para o PDF."
                    )
                alertas = list(
                    session.exec(
                        select(Alerta).where(
                            Alerta.auditoria_id == resultado.auditoria.id
                        )
                    ).all()
                )
                # Reconciliacoes ja aprovadas relativas a esse par (se houver).
                aprovacoes = list(
                    session.exec(
                        select(ReconciliacaoAprovada).order_by(
                            ReconciliacaoAprovada.criada_em
                        )
                    ).all()
                )
                mobilizados_index = {
                    int(m.id or 0): f"{m.placa_ativo_raw} - {m.equipamento or ''}".strip(" -")
                    for m in session.exec(select(Mobilizado)).all()
                    if m.id is not None
                }
                view = pdf_render.montar_reconciliacoes_view(
                    aprovacoes, mobilizados_index
                )
                pdf_bytes, filename = pdf_render.render_auditoria_pdf(
                    auditoria=resultado.auditoria,
                    checklist=checklist,
                    alertas=alertas,
                    reconciliacoes=view,
                    parecer_meta={
                        "provider": par.provider,
                        "modelo": par.modelo,
                        "offline": par.offline,
                    },
                    tolerancia_pct=TOLERANCIA_PERCENTUAL,
                )
                pdf_path = pdfs_dir / filename
                pdf_path.write_bytes(pdf_bytes)
                _print(f"[pdf] {pdf_path.name} ({len(pdf_bytes)} bytes)")

            sucesso += 1
        except Exception as exc:  # noqa: BLE001
            erros.append(f"{nf_anterior}->{nf_atual}: {exc}")
            _print(f"[erro] {exc}")

    elapsed = time.perf_counter() - t_start
    _print("\n=========================================")
    _print(f"Pares processados: {sucesso}/{len(PARES_DEMO)}")
    _print(f"Tempo total: {elapsed:.2f}s")
    if cache_dir.exists():
        files = sorted(cache_dir.glob("*.json"))
        _print(f"Arquivos no demo_cache ({len(files)}):")
        for f in files:
            _print(f"  - {f.name} ({f.stat().st_size} bytes)")
    _print(f"PDFs amostra em: {pdfs_dir}")
    if erros:
        _print("\nERROS:")
        for e in erros:
            _print(f"  ! {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
