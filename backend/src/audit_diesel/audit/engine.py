"""AuditEngine: orquestra leitura de NFs, calculos do §4 e disparo dos alertas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from sqlmodel import Session, select

from audit_diesel.config import TOLERANCIA_PERCENTUAL
from audit_diesel.models import (
    Abastecimento,
    Alerta,
    Auditoria,
    Checklist,
    Mobilizado,
    ReconciliacaoAprovada,
)

from .alert_dedup import deduplicar_nao_cadastrados
from .alerts import ALERTAS_PADRAO
from .alerts.base import AlertResult, AuditContext
from .indicators import calcular_indicadores

# Prefixo usado em `Auditoria.nf_anterior` quando o auditor define manualmente
# o ponto de corte (data + estoque inicial) em vez de selecionar uma NF
# anterior do conjunto. Permite ao frontend distinguir os dois fluxos sem
# precisar de coluna nova.
PONTO_CORTE_PREFIX = "CORTE:"


@dataclass
class PontoCorteManual:
    """Fronteira inferior da janela de auditoria definida pelo auditor.

    Usado quando nao ha NF anterior disponivel (tipicamente para a primeira
    NF do conjunto). Substitui o Checklist anterior por valores informados
    manualmente.
    """

    data_inicio: datetime
    estoque_tanque_inicial_litros: float
    estoque_comboio_inicial_litros: float
    motivo: str

    @property
    def label(self) -> str:
        """Identificador legivel salvo em `Auditoria.nf_anterior`."""
        return f"{PONTO_CORTE_PREFIX}{self.data_inicio.strftime('%Y-%m-%dT%H:%M')}"


class ChecklistNaoEncontrado(Exception):
    """Levantada quando uma das NFs solicitadas nao existe no banco."""


class ParTemporalInvalido(Exception):
    """Levantada quando a NF anterior nao precede temporalmente a NF atual."""


@dataclass
class AuditoriaCompleta:
    """Resultado retornado pelo engine: registro persistido + alertas detalhados."""

    auditoria: Auditoria
    alertas: list[Alerta]

    def __post_init__(self) -> None:
        self.alertas = deduplicar_nao_cadastrados(self.alertas)

    def to_dict(self) -> dict[str, Any]:
        """Serializa para dict (consumido pela CLI no modo --json)."""
        return {
            "auditoria": {
                "id": self.auditoria.id,
                "nf_anterior": self.auditoria.nf_anterior,
                "nf_atual": self.auditoria.nf_atual,
                "nome_obra": self.auditoria.nome_obra,
                "criada_em": self.auditoria.criada_em.isoformat(),
                "estoque_inicial_anterior": self.auditoria.estoque_inicial_anterior,
                "quantidade_descarregada_anterior": self.auditoria.quantidade_descarregada_anterior,
                "estoque_final_teorico_anterior": self.auditoria.estoque_final_teorico_anterior,
                "saidas_registradas_litros": self.auditoria.saidas_registradas_litros,
                "saidas_registradas_custo": self.auditoria.saidas_registradas_custo,
                "estoque_inicial_atual": self.auditoria.estoque_inicial_atual,
                "saida_teorica_litros": self.auditoria.saida_teorica_litros,
                "diferenca_litros": self.auditoria.diferenca_litros,
                "diferenca_percentual": self.auditoria.diferenca_percentual,
                "qtd_equipamentos_nao_cadastrados": self.auditoria.qtd_equipamentos_nao_cadastrados,
                "validacao_final": self.auditoria.validacao_final,
                "parecer_ia": self.auditoria.parecer_ia,
            },
            "alertas": [
                {
                    "id": a.id,
                    "tipo": a.tipo,
                    "severidade": a.severidade,
                    "titulo": a.titulo,
                    "descricao": a.descricao,
                    "abastecimento_id": a.abastecimento_id,
                    "impacto_financeiro": a.impacto_financeiro,
                    "payload": json.loads(a.payload_json),
                }
                for a in self.alertas
            ],
        }


class AuditEngine:
    """Engine deterministica de auditoria de diesel entre duas NFs sequenciais."""

    def __init__(self, session: Session) -> None:
        self.session = session
        # Mantem os atributos disponiveis apos o commit para que o caller
        # possa serializar/imprimir sem precisar reabrir a sessao.
        self.session.expire_on_commit = False

    def auditar(self, nf_anterior: str, nf_atual: str) -> AuditoriaCompleta:
        """Executa o pipeline completo de auditoria entre duas NFs.

        1. Busca os dois Checklists.
        2. Define janela [datetime_fim_descarga_anterior, datetime_fim_descarga_atual).
        3. Filtra abastecimentos na janela.
        4. Calcula indicadores §4.
        5. Roda os 4 alertas.
        6. Aplica regra de validação §4.4.
        7. Persiste e retorna.
        """
        ck_ant, ck_atu = self.validar_par_temporal(nf_anterior, nf_atual)
        return self._executar_pipeline(ck_ant, ck_atu, nf_anterior_label=nf_anterior)

    def auditar_com_ponto_corte(
        self, ponto_corte: PontoCorteManual, nf_atual: str
    ) -> AuditoriaCompleta:
        """Variante de `auditar` para quando nao ha NF anterior disponivel.

        O auditor informa data/hora do corte e os estoques iniciais de tanque
        e comboio nesse instante. Construimos um Checklist sintetico (apenas
        em memoria) com `quantidade_nf_litros=0`, fazendo
        `estoque_final_teorico_anterior = estoque_inicial_anterior` no calculo
        do §4. O resto do pipeline (alertas, persistencia) e identico.
        """
        ck_atu = self._carregar_checklist(nf_atual)
        if ponto_corte.data_inicio >= ck_atu.datetime_fim_descarga:
            raise ParTemporalInvalido(
                "Ponto de corte deve ser anterior ao fim de descarga da NF atual "
                f"(corte: {ponto_corte.data_inicio:%d/%m/%Y %H:%M}; "
                f"NF {ck_atu.nota_fiscal}: {ck_atu.datetime_fim_descarga:%d/%m/%Y %H:%M})."
            )
        ck_ant = Checklist(
            numero_chamado=ponto_corte.label,
            nota_fiscal=ponto_corte.label,
            nome_obra=ck_atu.nome_obra,
            cnpj_fornecedor="",
            data_recebimento=ponto_corte.data_inicio,
            hora_inicio_descarga=time(0, 0),
            hora_final_descarga=ponto_corte.data_inicio.time(),
            datetime_fim_descarga=ponto_corte.data_inicio,
            quantidade_nf_litros=0.0,
            volume_conferido_litros=0.0,
            estoque_antes_tanque_litros=ponto_corte.estoque_tanque_inicial_litros,
            estoque_antes_comboio_litros=ponto_corte.estoque_comboio_inicial_litros,
            preco_unitario=ck_atu.preco_unitario,
            valor_total_nf=0.0,
        )
        return self._executar_pipeline(ck_ant, ck_atu, nf_anterior_label=ponto_corte.label)

    def _executar_pipeline(
        self,
        ck_ant: Checklist,
        ck_atu: Checklist,
        *,
        nf_anterior_label: str,
    ) -> AuditoriaCompleta:
        inicio = ck_ant.datetime_fim_descarga
        fim = ck_atu.datetime_fim_descarga

        abastecimentos = self.session.exec(
            select(Abastecimento)
            .where(Abastecimento.data >= inicio)
            .where(Abastecimento.data < fim)
            .order_by(Abastecimento.data)
        ).all()

        mobilizados = list(self.session.exec(select(Mobilizado)).all())

        indicadores = calcular_indicadores(ck_ant, ck_atu, list(abastecimentos))

        # Aprovações de reconciliação funcionam como "cadastro virtual": para os
        # abastecimentos cobertos por uma aprovação, sintetizamos um Mobilizado
        # já indexado pelo veiculo_normalizado do próprio abastecimento, fazendo
        # o NaoCadastradoAlert não disparar mais para eles.
        aprovacoes = self.session.exec(select(ReconciliacaoAprovada)).all()
        ab_index = {a.id: a for a in abastecimentos}
        for ap in aprovacoes:
            ab = ab_index.get(ap.abastecimento_id)
            if ab is None:
                continue
            mob = self.session.get(Mobilizado, ap.mobilizado_id)
            if mob is None:
                continue
            sintetico = Mobilizado(
                id=mob.id,
                codigo_projeto=mob.codigo_projeto,
                nome_obra=mob.nome_obra,
                tipo_equipamento=mob.tipo_equipamento,
                equipamento=mob.equipamento,
                marca=mob.marca,
                modelo=mob.modelo,
                placa_ativo_raw=mob.placa_ativo_raw,
                placa_ativo_normalizada=ab.veiculo_normalizado,
                situacao=mob.situacao,
                data_mobilizacao=mob.data_mobilizacao,
                data_desmobilizacao=mob.data_desmobilizacao,
                capacidade_litros=mob.capacidade_litros,
                ano=mob.ano,
            )
            mobilizados.append(sintetico)

        contexto = AuditContext(
            nf_anterior=ck_ant,
            nf_atual=ck_atu,
            abastecimentos_janela=list(abastecimentos),
            mobilizados=mobilizados,
            session=self.session,
        )

        resultados: list[AlertResult] = []
        for alerta_impl in ALERTAS_PADRAO:
            resultados.extend(alerta_impl.detectar(contexto))

        qtd_nao_cadastrados = sum(1 for r in resultados if r.tipo == "NAO_CADASTRADO")
        validacao = (
            "APROVADO"
            if abs(indicadores.diferenca_percentual) < TOLERANCIA_PERCENTUAL
            and qtd_nao_cadastrados == 0
            else "INCONSISTENTE"
        )

        auditoria = Auditoria(
            nf_anterior=nf_anterior_label,
            nf_atual=ck_atu.nota_fiscal,
            nome_obra=ck_atu.nome_obra,
            criada_em=datetime.now(),
            estoque_inicial_anterior=indicadores.estoque_inicial_anterior,
            quantidade_descarregada_anterior=indicadores.quantidade_descarregada_anterior,
            estoque_final_teorico_anterior=indicadores.estoque_final_teorico_anterior,
            saidas_registradas_litros=indicadores.saidas_registradas_litros,
            saidas_registradas_custo=indicadores.saidas_registradas_custo,
            estoque_inicial_atual=indicadores.estoque_inicial_atual,
            saida_teorica_litros=indicadores.saida_teorica_litros,
            diferenca_litros=indicadores.diferenca_litros,
            diferenca_percentual=indicadores.diferenca_percentual,
            qtd_equipamentos_nao_cadastrados=qtd_nao_cadastrados,
            validacao_final=validacao,
        )
        self.session.add(auditoria)
        self.session.commit()
        self.session.refresh(auditoria)

        alertas: list[Alerta] = []
        for r in resultados:
            alerta = Alerta(
                auditoria_id=auditoria.id or 0,
                tipo=r.tipo,
                severidade=r.severidade,
                abastecimento_id=r.abastecimento_id,
                titulo=r.titulo,
                descricao=r.descricao,
                payload_json=json.dumps(r.payload, ensure_ascii=False, default=str),
                impacto_financeiro=r.impacto_financeiro,
            )
            self.session.add(alerta)
            alertas.append(alerta)
        self.session.commit()
        for a in alertas:
            self.session.refresh(a)

        return AuditoriaCompleta(auditoria=auditoria, alertas=alertas)

    def validar_par_temporal(self, nf_anterior: str, nf_atual: str) -> tuple[Checklist, Checklist]:
        """Carrega e valida que a janela da NF anterior termina antes da atual."""
        ck_ant = self._carregar_checklist(nf_anterior)
        ck_atu = self._carregar_checklist(nf_atual)
        if ck_ant.datetime_fim_descarga >= ck_atu.datetime_fim_descarga:
            raise ParTemporalInvalido(
                "NF anterior deve ter fim de descarga anterior ao da NF atual "
                f"(NF {ck_ant.nota_fiscal}: {ck_ant.datetime_fim_descarga:%d/%m/%Y %H:%M}; "
                f"NF {ck_atu.nota_fiscal}: {ck_atu.datetime_fim_descarga:%d/%m/%Y %H:%M})."
            )
        return ck_ant, ck_atu

    def _carregar_checklist(self, nf: str) -> Checklist:
        ck = self.session.exec(
            select(Checklist).where(Checklist.nota_fiscal == str(nf))
        ).first()
        if ck is None:
            raise ChecklistNaoEncontrado(f"NF {nf!r} não encontrada no Checklist.")
        return ck
