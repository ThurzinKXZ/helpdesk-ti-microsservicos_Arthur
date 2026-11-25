"""Microsserviço de chamados e notificações, com persistência exclusiva."""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, FastAPI, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.chamados.esquemas import (Atribuicao, ChamadoCriar, ChamadoSaida, ComentarioCriar,
                                  ComentarioSaida, MudancaStatus, Painel, Status)
from app.chamados.modelos import Chamado, Comentario
from app.config import DOCS_ATIVA
from app.database import Base, SessionLocal, engine, get_db
from app.notificacoes.esquemas import NotificacaoSaida
from app.notificacoes.modelos import Notificacao
from app.seguranca_http import CabecalhosDeSeguranca
from services.common.security import usuario_atual, Principal
from services.chamados import domain

router = APIRouter(tags=["Chamados"])

@router.post("/chamados", response_model=ChamadoSaida, status_code=201)
def abrir_chamado(dados: ChamadoCriar, usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return domain.abrir(db, dados, usuario)

@router.get("/chamados", response_model=list[ChamadoSaida])
def listar_chamados(status: Status | None = None, tecnico_id: int | None = None,
                    usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return domain.listar(db, usuario, status, tecnico_id)

@router.get("/chamados/painel", response_model=Painel)
def painel(usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return domain.painel(db, usuario)

@router.get("/chamados/{chamado_id}", response_model=ChamadoSaida)
def obter_chamado(chamado_id: int, usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return domain.obter(db, chamado_id, usuario)

@router.patch("/chamados/{chamado_id}/atribuir", response_model=ChamadoSaida)
def atribuir_chamado(chamado_id: int, dados: Atribuicao, usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return domain.atribuir(db, chamado_id, dados.tecnico_id, usuario)

@router.patch("/chamados/{chamado_id}/status", response_model=ChamadoSaida)
def mudar_status(chamado_id: int, dados: MudancaStatus, usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return domain.mudar_status(db, chamado_id, dados.status, usuario)

@router.post("/chamados/{chamado_id}/comentarios", response_model=ComentarioSaida, status_code=201)
def comentar(chamado_id: int, dados: ComentarioCriar, usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return domain.comentar(db, chamado_id, dados, usuario)

@router.get("/notificacoes", response_model=list[NotificacaoSaida])
def minhas_notificacoes(usuario: Principal = Depends(usuario_atual), db: Session = Depends(get_db)):
    return list(db.scalars(select(Notificacao).where(Notificacao.destinatario_id == usuario.id).order_by(Notificacao.id)))

from sqlalchemy import select

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    # Dados iniciais independentes: os IDs referenciam usuários/ativos via contrato HTTP,
    # sem criar chaves estrangeiras ou compartilhar tabelas entre bancos.
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with SessionLocal() as db:
            if not list(db.scalars(select(Chamado))):
                agora = datetime.now()
                exemplos = [
                    Chamado(titulo="Computador não liga", descricao="Apertei o botão e nada acontece.",
                            prioridade="alta", status="em_atendimento", solicitante_id=2, tecnico_id=4,
                            ativo_id=1, criado_em=agora, prazo_sla=agora + timedelta(hours=8)),
                    Chamado(titulo="Impressora atolando papel", descricao="Atola a cada 3 folhas.",
                            prioridade="media", status="aberto", solicitante_id=3, tecnico_id=None,
                            ativo_id=2, criado_em=agora, prazo_sla=agora + timedelta(hours=24)),
                    Chamado(titulo="Acesso ao sistema de RH", descricao="Preciso de acesso para a nova estagiária.",
                            prioridade="baixa", status="aberto", solicitante_id=3, tecnico_id=None,
                            ativo_id=None, criado_em=agora, prazo_sla=agora + timedelta(hours=72)),
                ]
                db.add_all(exemplos)
                db.add(Notificacao(tipo="ChamadoAberto", destinatario_id=2,
                                   mensagem="Seu chamado #1 foi aberto.", criada_em=agora))
                db.commit()
    yield

app = FastAPI(title="HelpDesk · Serviço de Chamados", version="3.0.0", lifespan=lifespan,
              docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None)
app.add_middleware(CabecalhosDeSeguranca)
app.include_router(router)

@app.get("/saude", tags=["Saúde"])
def saude():
    return {"servico": "chamados", "status": "ok"}

@app.exception_handler(IntegrityError)
def conflito(request, erro):
    return JSONResponse(status_code=409, content={"detail": "O registro conflita com outro já existente."})
