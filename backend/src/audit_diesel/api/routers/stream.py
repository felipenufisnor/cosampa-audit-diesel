"""POST /auditorias/stream - Server-Sent Events da Feature A (Reasoning Stream).

Recebe `{nf_anterior, nf_atual}` e retorna um `text/event-stream` com a
sequencia narrada da auditoria. O cliente consome via `EventSource` ou
`fetch` + ReadableStream e renderiza cada evento conforme chega.

A persistencia da Auditoria + Alertas + parecer acontece dentro do
orquestrador `ai.streaming.stream_auditoria` exatamente como na rota
sincrona `POST /auditorias`, garantindo que o registro final apareca em
`GET /auditorias/{id}` apos o `final_result`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from audit_diesel.ai.client import ChatClient
from audit_diesel.ai.streaming import stream_auditoria

from ..deps import get_chat_client, get_session

router = APIRouter(tags=["auditorias"])


class StreamAuditoriaRequest(BaseModel):
    """Payload de POST /auditorias/stream."""

    nf_anterior: str
    nf_atual: str


@router.post("/auditorias/stream")
def post_auditorias_stream(
    body: StreamAuditoriaRequest,
    session: Session = Depends(get_session),
    chat: ChatClient = Depends(get_chat_client),
) -> StreamingResponse:
    """Inicia auditoria com narracao em tempo real via SSE."""
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # desativa buffering de proxy/nginx
    }
    return StreamingResponse(
        stream_auditoria(
            session=session,
            nf_anterior=body.nf_anterior,
            nf_atual=body.nf_atual,
            chat=chat,
        ),
        media_type="text/event-stream",
        headers=headers,
    )
