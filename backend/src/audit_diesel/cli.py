"""CLI principal: ingest, listar-nfs, auditar, stats."""

from __future__ import annotations

import json
import sys
from typing import NoReturn

import click
from rich.box import SIMPLE_HEAVY
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from sqlmodel import Session, select

from audit_diesel.audit.engine import AuditEngine, ChecklistNaoEncontrado
from audit_diesel.config import DB_PATH, RAW_DIR
from audit_diesel.ingestion.pipeline import build_engine, ingerir
from audit_diesel.models import Abastecimento, Checklist

console = Console()

_SEVERIDADE_COR = {
    "alta": "red",
    "media": "yellow",
    "baixa": "blue",
}


@click.group()
def app() -> None:
    """audit-diesel: auditoria automatizada de notas fiscais de diesel."""


@app.command("ingest")
@click.option("--force", is_flag=True, help="Dropa as tabelas antes de ingerir.")
def cmd_ingest(force: bool) -> None:
    """Le os xlsx em data/raw/ e popula o SQLite."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Ingerindo dados...", total=None)
        result = ingerir(force=force)
        progress.update(task, completed=1)

    table = Table(title="Ingestao concluida", box=SIMPLE_HEAVY)
    table.add_column("Entidade", style="bold")
    table.add_column("Registros", justify="right")
    table.add_row("Abastecimentos (Infleet)", str(result.abastecimentos))
    table.add_row("Mobilizados (GP)", str(result.mobilizados))
    table.add_row("Checklists (GLPI)", str(result.checklists))
    console.print(table)


@app.command("listar-nfs")
def cmd_listar_nfs() -> None:
    """Lista todas as NFs disponiveis no Checklist."""
    engine = build_engine()
    with Session(engine) as session:
        checklists = session.exec(select(Checklist).order_by(Checklist.data_recebimento)).all()
    table = Table(title="Notas fiscais cadastradas", box=SIMPLE_HEAVY)
    table.add_column("NF", style="bold")
    table.add_column("Chamado")
    table.add_column("Data recebimento")
    table.add_column("Hora final descarga")
    table.add_column("Quantidade (L)", justify="right")
    table.add_column("Valor total (R$)", justify="right")
    table.add_column("Obra")
    for c in checklists:
        table.add_row(
            c.nota_fiscal,
            c.numero_chamado,
            c.data_recebimento.strftime("%d/%m/%Y"),
            c.hora_final_descarga.strftime("%H:%M"),
            f"{c.quantidade_nf_litros:,.2f}",
            f"{c.valor_total_nf:,.2f}",
            c.nome_obra,
        )
    console.print(table)


@app.command("auditar")
@click.option("--nf-anterior", required=True, help="Numero da NF anterior.")
@click.option("--nf-atual", required=True, help="Numero da NF atual.")
@click.option("--json", "as_json", is_flag=True, help="Imprime JSON estruturado em stdout.")
def cmd_auditar(nf_anterior: str, nf_atual: str, as_json: bool) -> None:
    """Roda a auditoria entre as duas NFs e imprime indicadores + alertas."""
    engine = build_engine()
    with Session(engine) as session:
        engine_audit = AuditEngine(session)
        try:
            resultado = engine_audit.auditar(str(nf_anterior), str(nf_atual))
        except ChecklistNaoEncontrado as e:
            console.print(f"[red]Erro:[/red] {e}")
            _exit(2)

    if as_json:
        click.echo(json.dumps(resultado.to_dict(), ensure_ascii=False, indent=2, default=str))
        return

    a = resultado.auditoria
    cor_validacao = "green" if a.validacao_final == "APROVADO" else "red"
    header = (
        f"Auditoria NF {a.nf_anterior} -> NF {a.nf_atual}  |  "
        f"Obra: {a.nome_obra}"
    )
    console.print(Panel(header, style=cor_validacao))

    table = Table(title="Indicadores §4 do escopo", box=SIMPLE_HEAVY)
    table.add_column("Métrica", style="bold")
    table.add_column("Valor", justify="right")

    def linha(nome: str, valor: float, unidade: str = "L") -> None:
        if unidade == "%":
            table.add_row(nome, f"{valor * 100:+.2f}%")
        elif unidade == "R$":
            table.add_row(nome, f"R$ {valor:,.2f}")
        else:
            table.add_row(nome, f"{valor:,.2f} {unidade}")

    linha("Estoque inicial (NF anterior)", a.estoque_inicial_anterior)
    linha("Quantidade descarregada (NF anterior)", a.quantidade_descarregada_anterior)
    linha("Estoque final teórico (NF anterior)", a.estoque_final_teorico_anterior)
    linha("Estoque inicial (NF atual)", a.estoque_inicial_atual)
    linha("Saída teórica", a.saida_teorica_litros)
    linha("Saídas registradas (Infleet)", a.saidas_registradas_litros)
    linha("Saídas registradas - custo", a.saidas_registradas_custo, "R$")
    linha("Diferença", a.diferenca_litros)
    linha("Diferença percentual", a.diferenca_percentual, "%")
    table.add_row("Equipamentos não cadastrados", str(a.qtd_equipamentos_nao_cadastrados))
    table.add_row("Validacao final", f"[{cor_validacao}]{a.validacao_final}[/{cor_validacao}]")
    console.print(table)

    if not resultado.alertas:
        console.print(Panel("Nenhum alerta detectado.", style="green"))
        return

    console.print(f"\n[bold]Alertas detectados ({len(resultado.alertas)}):[/bold]")
    for alerta in resultado.alertas:
        cor = _SEVERIDADE_COR.get(alerta.severidade, "white")
        impacto = (
            f"\nImpacto financeiro: R$ {alerta.impacto_financeiro:,.2f}"
            if alerta.impacto_financeiro
            else ""
        )
        console.print(
            Panel(
                f"[bold]{alerta.titulo}[/bold]\n{alerta.descricao}{impacto}",
                title=f"[{cor}]{alerta.tipo} ({alerta.severidade})[/{cor}]",
                border_style=cor,
            )
        )


@app.command("stats")
def cmd_stats() -> None:
    """Estatísticas globais do banco."""
    engine = build_engine()
    with Session(engine) as session:
        abast = session.exec(select(Abastecimento)).all()
    total = len(abast)
    if total == 0:
        console.print("[yellow]Banco vazio. Rode `audit-diesel ingest` primeiro.[/yellow]")
        return
    total_litros = sum(a.quantidade_litros for a in abast)
    total_custo = sum(a.custo_total for a in abast)
    n_inconsist = sum(1 for a in abast if a.inconsistencias_infleet)
    pct_inconsist = n_inconsist / total

    engine2 = build_engine()
    with Session(engine2) as session:
        from audit_diesel.models import Mobilizado as M  # noqa: PLC0415
        cadastrados = {m.placa_ativo_normalizada for m in session.exec(select(M)).all()}
    n_nao_cadastrados = sum(1 for a in abast if a.veiculo_normalizado not in cadastrados)
    pct_nao_cadastrados = n_nao_cadastrados / total

    table = Table(title="Estatísticas globais", box=SIMPLE_HEAVY)
    table.add_column("Métrica", style="bold")
    table.add_column("Valor", justify="right")
    table.add_row("Total de abastecimentos", f"{total:,}")
    table.add_row("Total de litros", f"{total_litros:,.2f} L")
    table.add_row("Total de custo", f"R$ {total_custo:,.2f}")
    table.add_row("Abastec. com inconsistência Infleet", f"{n_inconsist} ({pct_inconsist:.1%})")
    table.add_row("Abastec. sem cadastro no GP", f"{n_nao_cadastrados} ({pct_nao_cadastrados:.1%})")
    console.print(table)
    console.print(f"[dim]Banco: {DB_PATH}  |  Origem: {RAW_DIR}[/dim]")


def _exit(code: int) -> NoReturn:
    sys.exit(code)


def main() -> None:
    """Entry point para o script `audit-diesel`."""
    app()


if __name__ == "__main__":
    main()
