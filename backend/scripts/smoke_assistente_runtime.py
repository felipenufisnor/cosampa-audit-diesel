"""Smoke test local do runtime do Assistente.

Valida contrato do /healthz, perguntas sugeridas, SSE de auditoria e uma
pergunta do Assistente contra a API em execucao.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


BASE_URL = os.environ.get("AUDIT_DIESEL_API_URL", "http://localhost:8000").rstrip("/")
REQUIRED_HEALTH_FIELDS = {
    "assistant_status",
    "assistant_reason",
    "assistant_can_answer_free_text",
    "assistant_has_cached_answers",
}


def _request(path: str, *, body: dict[str, Any] | None = None, timeout: float = 8.0):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _json(path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
    return json.loads(_request(path, body=body))


def _first_sse(path: str, body: dict[str, Any], timeout: float = 10.0) -> str:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        linhas: list[str] = []
        while True:
            linha = resp.readline().decode("utf-8")
            if not linha:
                break
            linhas.append(linha)
            if linha in {"\n", "\r\n"}:
                break
        return "".join(linhas).strip()


def _auditoria_nf_8187() -> int:
    nfs = json.loads(_request("/nfs"))
    for item in nfs:
        if item.get("nota_fiscal") == "8187" and item.get("ultima_auditoria_id"):
            return int(item["ultima_auditoria_id"])
    created = _json(
        "/auditorias",
        body={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    )
    return int(created["auditoria"]["id"])


def main() -> int:
    try:
        health = _json("/healthz")
        missing = REQUIRED_HEALTH_FIELDS - set(health)
        if missing:
            raise RuntimeError(
                "backend desatualizado: /healthz sem campos "
                + ", ".join(sorted(missing))
            )
        print(
            "health ok:",
            health["assistant_status"],
            f"free_text={health['assistant_can_answer_free_text']}",
            f"cache={health['assistant_has_cached_answers']}",
        )

        auditoria_id = _auditoria_nf_8187()
        perguntas = _json(f"/auditorias/{auditoria_id}/perguntas-sugeridas")
        if "perguntas" not in perguntas:
            raise RuntimeError("resposta de perguntas-sugeridas sem campo perguntas")
        print(f"perguntas ok: auditoria={auditoria_id} qtd={len(perguntas['perguntas'])}")

        first_stream = _first_sse(
            "/auditorias/stream",
            {"nf_anterior": "8187", "nf_atual": "8278"},
        )
        if "data:" not in first_stream:
            raise RuntimeError("stream de auditoria nao emitiu evento SSE")
        print("stream ok:", first_stream.splitlines()[0][:100])

        pergunta = (
            perguntas["perguntas"][0]["pergunta"]
            if perguntas["perguntas"]
            else "Qual o principal risco desta auditoria?"
        )
        first_answer = _first_sse(
            f"/auditorias/{auditoria_id}/perguntar",
            {"pergunta": pergunta},
        )
        if "data:" not in first_answer:
            raise RuntimeError("assistente nao emitiu evento SSE")
        print("assistente ok:", first_answer.splitlines()[0][:100])
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"SMOKE FALHOU: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
