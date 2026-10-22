from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_login import (
    login_user,
    logout_user,
    login_required
)

from extensions import limiter, csrf

from database.connection import db
from database.models import Usuario

from utils.email_service import enviar_email
from utils.password_reset import gerar_token_recuperacao

auth_bp = Blueprint(
    "auth",
    __name__
)


@auth_bp.route("/")
def index():

    return redirect(
        url_for("auth.login")
    )


@auth_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        usuario_digitado = request.form.get(
            "usuario",
            ""
        ).strip()

        senha_digitada = request.form.get(
            "senha",
            ""
        )

        usuario = Usuario.query.filter_by(
            usuario=usuario_digitado
        ).first()

        if (
            usuario
            and usuario.ativo
            and usuario.verificar_senha(
                senha_digitada
            )
        ):

            usuario.ultimo_acesso = datetime.utcnow()

            db.session.commit()

            login_user(usuario)

            return redirect(
                url_for("dashboard.index")
            )

        flash(
            "Usuário ou senha inválidos.",
            "danger"
        )

    return render_template(
        "login.html"
    )


@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("auth.login")
    )

@auth_bp.route("/esqueci-senha", methods=["GET", "POST"])
@limiter.limit("3 per 15 minutes", methods=["POST"])
def esqueci_senha():

    if request.method == "POST":
        csrf.protect()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        usuario = Usuario.query.filter(
            db.func.lower(Usuario.email) == email,
            Usuario.ativo.is_(True)
        ).first() if email else None

        if usuario:

            token = gerar_token_recuperacao(usuario)

            link = url_for(
                "auth.redefinir_senha",
                token=token,
                _external=True
            )

            assunto = "Recuperação de senha - Catena Engenharia"

            corpo = f"""
Olá, {usuario.nome}!

Recebemos uma solicitação para redefinir sua senha
no sistema de Controle de Almoxarifado.

Acesse o link abaixo:

{link}

O link é válido por 30 minutos.

Se você não solicitou a recuperação,
ignore esta mensagem.

Catena Engenharia
"""

            try:
                enviar_email(
                    usuario.email,
                    assunto,
                    corpo
                )

            except Exception:
                from flask import current_app

                current_app.logger.exception(
                    "Falha no envio do e-mail de recuperação"
                )

        flash(
            "Se o e-mail estiver cadastrado, "
            "você receberá as instruções "
            "para recuperar sua senha.",
            "success"
        )

        return redirect(
            url_for("auth.esqueci_senha")
        )

    return render_template(
        "esqueci_senha.html"
    )

@auth_bp.route(
    "/redefinir-senha/<token>",
    methods=["GET", "POST"]
)
def redefinir_senha(token):

    from utils.password_reset import validar_token_recuperacao

    usuario = validar_token_recuperacao(token)

    if usuario is None:

        flash(
            "Este link de recuperação é inválido "
            "ou expirou. Solicite um novo link.",
            "danger"
        )

        return redirect(
            url_for("auth.esqueci_senha")
        )

    if request.method == "POST":
        csrf.protect()

        senha = request.form.get(
            "senha",
            ""
        )

        confirmar_senha = request.form.get(
            "confirmar_senha",
            ""
        )

        if len(senha) < 12:

            flash(
                "A nova senha deve ter pelo menos 12 caracteres.",
                "danger"
            )

        elif senha != confirmar_senha:

            flash(
                "As senhas informadas não coincidem.",
                "danger"
            )

        else:

            usuario.definir_senha(senha)

            db.session.commit()

            flash(
                "Senha redefinida com sucesso! "
                "Faça login com sua nova senha.",
                "success"
            )

            return redirect(
                url_for("auth.login")
            )

    return render_template(
        "redefinir_senha.html",
        token=token
    )