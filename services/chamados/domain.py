"""Regras de chamados. Integração com Usuários e Inventário somente por HTTP."""
from collections import Counter
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.chamados.modelos import Chamado, Comentario
from app.chamados.esquemas import ChamadoCriar, ComentarioCriar
from app.notificacoes.modelos import Notificacao
from services.common.http_client import get_servico, usuarios_url, inventario_url

HORAS_SLA = {"critica": 4, "alta": 8, "media": 24, "baixa": 72}
TRANSICOES = {"aberto": {"em_atendimento"}, "em_atendimento": {"resolvido"},
              "resolvido": {"fechado", "em_atendimento"}, "fechado": set()}
EQUIPE = ("tecnico", "admin")


def salvar(db: Session, chamado: Chamado) -> Chamado:
    db.add(chamado); db.commit(); db.refresh(chamado); return chamado


def obter(db: Session, chamado_id: int, usuario) -> Chamado:
    chamado = db.get(Chamado, chamado_id)
    if chamado is None or not (usuario.perfil in EQUIPE or chamado.solicitante_id == usuario.id):
        raise HTTPException(status_code=404, detail=f"Chamado {chamado_id} não encontrado.")
    return chamado


def notificar(db: Session, tipo: str, destinatario: int, mensagem: str):
    aviso = Notificacao(tipo=tipo, destinatario_id=destinatario, mensagem=mensagem, criada_em=datetime.now())
    db.add(aviso); db.commit(); db.refresh(aviso)


def abrir(db: Session, dados: ChamadoCriar, usuario):
    if dados.ativo_id is not None:
        get_servico(inventario_url(f"/ativos/{dados.ativo_id}"), usuario.token, "Inventário")
    agora = datetime.now()
    chamado = Chamado(**dados.model_dump(), solicitante_id=usuario.id, status="aberto",
                      criado_em=agora, prazo_sla=agora + timedelta(hours=HORAS_SLA[dados.prioridade]))
    chamado = salvar(db, chamado)
    notificar(db, "ChamadoAberto", usuario.id,
              f"Seu chamado #{chamado.id} foi aberto. Prazo: {chamado.prazo_sla:%d/%m %H:%M}.")
    return chamado


def listar(db: Session, usuario, status=None, tecnico_id=None):
    q = select(Chamado).order_by(Chamado.id)
    if usuario.perfil not in EQUIPE: q = q.where(Chamado.solicitante_id == usuario.id)
    if status: q = q.where(Chamado.status == status)
    if tecnico_id: q = q.where(Chamado.tecnico_id == tecnico_id)
    return list(db.scalars(q))


def atribuir(db: Session, chamado_id: int, tecnico_id: int, usuario):
    if usuario.perfil not in EQUIPE:
        raise HTTPException(status_code=403, detail="Só técnicos e administradores atribuem chamados.")
    chamado = obter(db, chamado_id, usuario)
    if chamado.status in ("resolvido", "fechado"):
        raise HTTPException(status_code=422, detail="Não é possível atribuir um chamado resolvido ou fechado.")
    tecnico = get_servico(usuarios_url(f"/usuarios/{tecnico_id}"), usuario.token, "Usuários")
    if tecnico.get("perfil") != "tecnico":
        raise HTTPException(status_code=422, detail=f"Usuário {tecnico_id} não é técnico.")
    chamado.tecnico_id = tecnico_id
    if chamado.status == "aberto": chamado.status = "em_atendimento"
    chamado = salvar(db, chamado)
    notificar(db, "ChamadoAtribuido", tecnico_id, f"O chamado #{chamado.id} foi atribuído a você.")
    return chamado


def mudar_status(db: Session, chamado_id: int, novo_status: str, usuario):
    chamado = obter(db, chamado_id, usuario)
    pode_solicitante = chamado.status == "resolvido" and novo_status in ("fechado", "em_atendimento")
    if not (usuario.perfil in EQUIPE or pode_solicitante):
        raise HTTPException(status_code=403, detail="Você não pode mudar o status deste chamado.")
    if novo_status not in TRANSICOES[chamado.status]:
        raise HTTPException(status_code=422, detail=f"Não é possível ir de '{chamado.status}' para '{novo_status}'.")
    if novo_status == "em_atendimento" and chamado.tecnico_id is None:
        raise HTTPException(status_code=422, detail="Atribua um técnico antes de iniciar o atendimento.")
    chamado.status = novo_status
    chamado = salvar(db, chamado)
    if novo_status == "resolvido":
        notificar(db, "ChamadoResolvido", chamado.solicitante_id,
                  f"Seu chamado #{chamado.id} foi resolvido. Confirme se está tudo certo.")
    return chamado


def comentar(db: Session, chamado_id: int, dados: ComentarioCriar, usuario):
    chamado = obter(db, chamado_id, usuario)
    if chamado.status == "fechado":
        raise HTTPException(status_code=422, detail="Chamados fechados não recebem comentários.")
    comentario = Comentario(chamado_id=chamado.id, autor_id=usuario.id,
                            texto=dados.texto, criado_em=datetime.now())
    db.add(comentario); db.commit(); db.refresh(comentario); return comentario


def painel(db: Session, usuario):
    chamados = listar(db, usuario)
    agora = datetime.now()
    atrasados = sum(1 for c in chamados if c.status in ("aberto", "em_atendimento") and c.prazo_sla < agora)
    return {"total": len(chamados), "por_status": dict(Counter(c.status for c in chamados)), "atrasados": atrasados}
