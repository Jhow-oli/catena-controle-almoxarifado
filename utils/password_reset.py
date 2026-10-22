import hashlib

from flask import current_app
from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired
)


TEMPO_EXPIRACAO = 1800  # 30 minutos


def _serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="catena-recuperacao-senha-v1"
    )


def _assinatura_senha(usuario):
    return hashlib.sha256(
        usuario.senha_hash.encode("utf-8")
    ).hexdigest()


def gerar_token_recuperacao(usuario):
    return _serializer().dumps({
        "usuario_id": usuario.id,
        "senha": _assinatura_senha(usuario)
    })


def validar_token_recuperacao(token):
    from database.models import Usuario

    try:
        dados = _serializer().loads(
            token,
            max_age=TEMPO_EXPIRACAO
        )
    except (BadSignature, SignatureExpired):
        return None

    if not isinstance(dados, dict):
        return None

    usuario_id = dados.get("usuario_id")

    if not isinstance(usuario_id, int):
        return None

    usuario = Usuario.query.get(usuario_id)

    if not usuario or not usuario.ativo:
        return None

    if dados.get("senha") != _assinatura_senha(usuario):
        return None

    return usuario