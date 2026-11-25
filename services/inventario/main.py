"""Microsserviço independente de inventário, com banco de dados próprio."""
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import DOCS_ATIVA
from app.database import Base, engine, get_db, SessionLocal
from app.erros import NaoEncontrado, RegraDeNegocio
from app.inventario import servico
from app.inventario.esquemas import AtivoCriar, AtivoSaida
from app.inventario.modelos import Ativo
from app.seguranca_http import CabecalhosDeSeguranca
from services.common.security import usuario_atual, exigir_perfil, Principal

router = APIRouter(prefix="/ativos", tags=["Inventário"])

@router.post("", response_model=AtivoSaida, status_code=201,
             dependencies=[Depends(exigir_perfil("tecnico", "admin"))])
def criar_ativo(dados: AtivoCriar, db: Session = Depends(get_db)):
    return servico.criar(db, dados)

@router.get("", response_model=list[AtivoSaida])
def listar_ativos(setor: str | None = Query(None, max_length=80),
                  usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.listar(db, setor)

@router.get("/{ativo_id}", response_model=AtivoSaida)
def obter_ativo(ativo_id: int, usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.obter(db, ativo_id)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with SessionLocal() as db:
            if not servico.listar(db):
                exemplos = [
                    ("PAT-0001", "computador", "Desktop Dell OptiPlex", "Financeiro"),
                    ("PAT-0002", "impressora", "Impressora HP LaserJet", "RH"),
                    ("PAT-0003", "notebook", "Notebook Lenovo ThinkPad", "TI"),
                ]
                for patrimonio, tipo, descricao, setor in exemplos:
                    servico.criar(db, AtivoCriar(patrimonio=patrimonio, tipo=tipo, descricao=descricao, setor=setor))
    yield

app = FastAPI(title="HelpDesk · Serviço de Inventário", version="3.0.0", lifespan=lifespan,
              docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None)
app.add_middleware(CabecalhosDeSeguranca)
app.include_router(router)

@app.get("/saude", tags=["Saúde"])
def saude():
    return {"servico": "inventario", "status": "ok"}

@app.exception_handler(NaoEncontrado)
def nao_encontrado(request, erro):
    return JSONResponse(status_code=404, content={"detail": str(erro)})

@app.exception_handler(RegraDeNegocio)
def regra(request, erro):
    return JSONResponse(status_code=422, content={"detail": str(erro)})

@app.exception_handler(IntegrityError)
def conflito(request, erro):
    return JSONResponse(status_code=409, content={"detail": "O registro conflita com outro já existente."})
