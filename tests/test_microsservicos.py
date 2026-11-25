"""Testes das fronteiras de segurança e comunicação da arquitetura distribuída."""
import httpx
import pytest
from fastapi import HTTPException

from app.auth import tokens
from app.chamados.modelos import Chamado, Comentario
from services.common import http_client


def test_token_distribuido_valida_identidade_e_perfil():
    token, _ = tokens.criar(42, "tecnico")
    assert tokens.ler_identidade(token) == {"id": 42, "perfil": "tecnico"}


def test_token_distribuido_rejeita_assinatura_invalida():
    with pytest.raises(tokens.TokenInvalido):
        tokens.ler_identidade("token.falso.invalido")


def test_chamados_nao_cria_chaves_estrangeiras_para_outros_servicos():
    assert len(Chamado.__table__.foreign_keys) == 0
    # Comentário só referencia o chamado, que pertence ao mesmo serviço/banco.
    assert {fk.target_fullname for fk in Comentario.__table__.foreign_keys} == {"chamados.id"}


def test_cliente_http_repasse_token_e_timeout(monkeypatch):
    capturado = {}

    def fake_get(url, headers, timeout):
        capturado.update(url=url, headers=headers, timeout=timeout)
        return httpx.Response(200, json={"id": 9, "perfil": "tecnico"})

    monkeypatch.setattr(http_client.httpx, "get", fake_get)
    resultado = http_client.get_servico("http://usuarios:8000/usuarios/9", "jwt-assinado", "Usuários")
    assert resultado["perfil"] == "tecnico"
    assert capturado["headers"]["Authorization"] == "Bearer jwt-assinado"
    assert capturado["timeout"].read > 0


def test_cliente_http_retorna_503_quando_servico_cai(monkeypatch):
    def indisponivel(*args, **kwargs):
        raise httpx.ConnectError("serviço fora do ar")

    monkeypatch.setattr(http_client.httpx, "get", indisponivel)
    with pytest.raises(HTTPException) as erro:
        http_client.get_servico("http://inventario:8000/ativos/1", "token", "Inventário")
    assert erro.value.status_code == 503
    assert "Inventário indisponível" in erro.value.detail
