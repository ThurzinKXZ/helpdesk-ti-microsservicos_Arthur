"""API Gateway: ponto único de entrada HTTP para a interface e os microsserviços."""
import os
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, Response, JSONResponse

from app.seguranca_http import CabecalhosDeSeguranca

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"
SERVICOS = {
    "auth": os.getenv("USUARIOS_URL", "http://usuarios:8000"),
    "usuarios": os.getenv("USUARIOS_URL", "http://usuarios:8000"),
    "ativos": os.getenv("INVENTARIO_URL", "http://inventario:8000"),
    "chamados": os.getenv("CHAMADOS_URL", "http://chamados:8000"),
    "notificacoes": os.getenv("CHAMADOS_URL", "http://chamados:8000"),
    "docs": os.getenv("USUARIOS_URL", "http://usuarios:8000"),
    "openapi.json": os.getenv("USUARIOS_URL", "http://usuarios:8000"),
}

app = FastAPI(title="HelpDesk TI · API Gateway", version="3.0.0", docs_url=None, redoc_url=None)
app.add_middleware(CabecalhosDeSeguranca)

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")

@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse(WEB / "app.js", media_type="text/javascript")

@app.get("/estilo.css", include_in_schema=False)
def css():
    return FileResponse(WEB / "estilo.css", media_type="text/css")

@app.get("/saude", tags=["Gateway"])
async def saude():
    resultado = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(1.5, connect=0.8)) as client:
        for nome, base in (("usuarios", SERVICOS["usuarios"]),
                           ("inventario", SERVICOS["ativos"]),
                           ("chamados", SERVICOS["chamados"])):
            try:
                r = await client.get(base + "/saude")
                resultado[nome] = "online" if r.is_success else "indisponível"
            except httpx.RequestError:
                resultado[nome] = "indisponível"
    return {"gateway": "online", "servicos": resultado}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], include_in_schema=False)
async def encaminhar(path: str, request: Request):
    prefixo = path.split("/", 1)[0]
    base = SERVICOS.get(prefixo)
    if not base:
        raise HTTPException(status_code=404, detail="Rota não encontrada no API Gateway.")
    url = f"{base}/{path}"
    if request.url.query:
        url += "?" + request.url.query
    headers = {k: v for k, v in request.headers.items()
               if k.lower() in {"authorization", "content-type", "accept", "user-agent", "x-request-id"}}
    corpo = await request.body()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=1.5)) as client:
            upstream = await client.request(request.method, url, content=corpo, headers=headers)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=503, detail="Tempo limite ao acessar o serviço solicitado.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Serviço solicitado indisponível no momento.") from exc
    resposta_headers = {k: v for k, v in upstream.headers.items()
                        if k.lower() not in {"content-length", "transfer-encoding", "connection", "keep-alive"}}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=resposta_headers)
