from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_login import current_user

from database.connection import db
from database.models import (
    Usuario,
    Colaborador
)

from utils.decorators import admin_required


usuarios_bp = Blueprint(
    "usuarios",
    __name__,
    url_prefix="/usuarios"
)


@usuarios_bp.route("/")
@admin_required
def index():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()

    consulta = Usuario.query

    if pesquisa:

        consulta = consulta.filter(
            db.or_(
                Usuario.nome.ilike(
                    f"%{pesquisa}%"
                ),
                Usuario.usuario.ilike(
                    f"%{pesquisa}%"
                ),
                Usuario.perfil.ilike(
                    f"%{pesquisa}%"
                )
            )
        )

    usuarios = consulta.order_by(
        Usuario.nome.asc()
    ).all()

    return render_template(
        "usuarios/index.html",
        usuarios=usuarios,
        pesquisa=pesquisa
    )


@usuarios_bp.route("/novo", methods=["GET", "POST"])
@admin_required
def novo():

    colaboradores = Colaborador.query.filter_by(
        ativo=True
    ).order_by(
        Colaborador.nome.asc()
    ).all()

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        usuario_nome = request.form.get(
            "usuario",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        senha = request.form.get(
            "senha",
            ""
        )

        perfil = request.form.get(
            "perfil",
            "COLABORADOR"
        ).strip().upper()

        colaborador_id = request.form.get(
            "colaborador_id"
        )

        ativo = request.form.get(
            "ativo",
            "1"
        ) == "1"


        if not nome:

            flash(
                "Informe o nome.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=None,
                colaboradores=colaboradores
            )


        if not usuario_nome:

            flash(
                "Informe o nome de usuário.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=None,
                colaboradores=colaboradores
            )


        if not senha:

            flash(
                "Informe uma senha.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=None,
                colaboradores=colaboradores
            )


        if perfil not in [
            "ADMIN",
            "COLABORADOR"
        ]:

            flash(
                "Perfil inválido.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=None,
                colaboradores=colaboradores
            )


        usuario_existente = Usuario.query.filter_by(
            usuario=usuario_nome
        ).first()

        if usuario_existente:

            flash(
                "Este nome de usuário já está cadastrado.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=None,
                colaboradores=colaboradores
            )

        # VERIFICAR SE O E-MAIL JÁ ESTÁ CADASTRADO
        if email:

            email_existente = Usuario.query.filter(
                db.func.lower(Usuario.email) == email
            ).first()

            if email_existente:

                flash(
                    "Este e-mail já está cadastrado.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    usuario=None,
                    colaboradores=colaboradores
                )


        novo_usuario = Usuario(

            nome=nome,

            usuario=usuario_nome,

            email=email if email else None,

            perfil=perfil,

            ativo=ativo,

            colaborador_id=int(colaborador_id)
                if colaborador_id
                else None

        )


        novo_usuario.definir_senha(
            senha
        )


        db.session.add(
            novo_usuario
        )

        db.session.commit()


        flash(
            "Usuário criado com sucesso!",
            "success"
        )


        return redirect(
            url_for("usuarios.index")
        )


    return render_template(
        "usuarios/form.html",
        usuario=None,
        colaboradores=colaboradores
    )

@usuarios_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar(id):

    usuario = Usuario.query.get_or_404(id)

    colaboradores = Colaborador.query.filter_by(
        ativo=True
    ).order_by(
        Colaborador.nome.asc()
    ).all()

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        usuario_nome = request.form.get(
            "usuario",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        senha = request.form.get(
            "senha",
            ""
        )

        perfil = request.form.get(
            "perfil",
            "COLABORADOR"
        ).strip().upper()

        colaborador_id = request.form.get(
            "colaborador_id"
        )

        ativo = request.form.get(
            "ativo",
            "1"
        ) == "1"


        if not nome:
            flash(
                "Informe o nome.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=usuario,
                colaboradores=colaboradores
            )


        if not usuario_nome:
            flash(
                "Informe o nome de usuário.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=usuario,
                colaboradores=colaboradores
            )


        if perfil not in [
            "ADMIN",
            "COLABORADOR"
        ]:

            flash(
                "Perfil inválido.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=usuario,
                colaboradores=colaboradores
            )


        usuario_existente = Usuario.query.filter(
            Usuario.usuario == usuario_nome,
            Usuario.id != usuario.id
        ).first()


        if usuario_existente:

            flash(
                "Este nome de usuário já está sendo utilizado.",
                "danger"
            )

            return render_template(
                "usuarios/form.html",
                usuario=usuario,
                colaboradores=colaboradores
            )

        # Verificar se o e-mail pertence a outro usuário
        if email:

            email_existente = Usuario.query.filter(
                db.func.lower(Usuario.email) == email,
                Usuario.id != usuario.id
            ).first()

            if email_existente:

                flash(
                    "Este e-mail já está cadastrado para outro usuário.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    usuario=usuario,
                    colaboradores=colaboradores
                )


        usuario.nome = nome

        usuario.usuario = usuario_nome

        usuario.email = email if email else None

        usuario.perfil = perfil

        usuario.ativo = ativo

        usuario.colaborador_id = (
            int(colaborador_id)
            if colaborador_id
            else None
        )


        # Só altera a senha se o campo tiver sido preenchido
        if senha:

            usuario.definir_senha(
                senha
            )


        db.session.commit()


        flash(
            "Usuário atualizado com sucesso!",
            "success"
        )


        return redirect(
            url_for("usuarios.index")
        )


    return render_template(
        "usuarios/form.html",
        usuario=usuario,
        colaboradores=colaboradores
    )

@usuarios_bp.route("/alternar-status/<int:id>", methods=["POST"])
@admin_required
def alternar_status(id):

    usuario = Usuario.query.get_or_404(id)

    # Impede desativar o próprio usuário logado
    if usuario.id == current_user.id:
        flash(
            "Você não pode desativar o próprio usuário.",
            "danger"
        )

        return redirect(
            url_for("usuarios.index")
        )

    usuario.ativo = not usuario.ativo

    db.session.commit()

    if usuario.ativo:

        flash(
            f"Usuário {usuario.nome} ativado com sucesso!",
            "success"
        )

    else:

        flash(
            f"Usuário {usuario.nome} desativado com sucesso!",
            "success"
        )

    return redirect(
        url_for("usuarios.index")
    )