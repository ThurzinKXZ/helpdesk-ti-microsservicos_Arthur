"""Autenticação stateless compartilhada pelos serviços distribuídos."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import tokens

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: int
    perfil: str
    token: str


def usuario_atual(credenciais: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Faça login para continuar.",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        identidade = tokens.ler_identidade(credenciais.credentials)
    except tokens.TokenInvalido:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token inválido ou expirado.",
                            headers={"WWW-Authenticate": "Bearer"})
    return Principal(**identidade, token=credenciais.credentials)


def exigir_perfil(*perfis: str):
    def verificar(usuario: Principal = Depends(usuario_atual)) -> Principal:
        if usuario.perfil not in perfis:
            raise HTTPException(status_code=403, detail="Você não tem permissão para esta ação.")
        return usuario
    return verificar
