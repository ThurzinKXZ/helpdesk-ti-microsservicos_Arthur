"""Cliente HTTP resiliente para comunicação entre microsserviços."""
import os
import httpx
from fastapi import HTTPException

TIMEOUT = httpx.Timeout(2.5, connect=1.0)


def get_servico(url: str, token: str, recurso: str):
    try:
        resposta = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
        raise HTTPException(status_code=503,
                            detail=f"Serviço {recurso} indisponível no momento. Tente novamente em instantes.") from exc
    if resposta.status_code == 404:
        raise HTTPException(status_code=404, detail=f"{recurso} não encontrado.")
    if resposta.status_code in (401, 403):
        raise HTTPException(status_code=resposta.status_code, detail="Acesso não autorizado ao serviço dependente.")
    if resposta.status_code >= 500:
        raise HTTPException(status_code=503, detail=f"Falha no serviço {recurso}.")
    if not resposta.is_success:
        raise HTTPException(status_code=422, detail=f"Não foi possível validar {recurso}.")
    return resposta.json()


def usuarios_url(path: str) -> str:
    return os.getenv("USUARIOS_URL", "http://usuarios:8000") + path


def inventario_url(path: str) -> str:
    return os.getenv("INVENTARIO_URL", "http://inventario:8000") + path
