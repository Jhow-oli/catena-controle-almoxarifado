from datetime import date, timedelta

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from database.connection import db
from database.models import Colaborador
from utils.decorators import admin_required


colaboradores_bp = Blueprint(
    "colaboradores",
    __name__,
    url_prefix="/colaboradores"
)


@colaboradores_bp.route("/")
@admin_required
def index():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()

    consulta = Colaborador.query

    if pesquisa:

        consulta = consulta.filter(
            db.or_(
                Colaborador.nome.ilike(
                    f"%{pesquisa}%"
                ),
                Colaborador.funcao.ilike(
                    f"%{pesquisa}%"
                ),
                Colaborador.categoria_cnh.ilike(
                    f"%{pesquisa}%"
                )
            )
        )

    colaboradores = consulta.order_by(
        Colaborador.nome.asc()
    ).all()

    hoje = date.today()

    limite_cnh = hoje + timedelta(
        days=30
    )

    return render_template(
        "colaboradores/index.html",
        colaboradores=colaboradores,
        pesquisa=pesquisa,
        hoje=hoje,
        limite_cnh=limite_cnh
    )


@colaboradores_bp.route(
    "/novo",
    methods=["GET", "POST"]
)
@admin_required
def novo():

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        funcao = request.form.get(
            "funcao",
            ""
        ).strip()

        categoria_cnh = request.form.get(
            "categoria_cnh",
            ""
        ).strip().upper()

        validade_cnh = request.form.get(
            "validade_cnh",
            ""
        ).strip()

        if not nome or not funcao:

            flash(
                "Nome e função são obrigatórios.",
                "danger"
            )

            return render_template(
                "colaboradores/form.html"
            )

        colaborador = Colaborador(
            nome=nome,
            funcao=funcao,
            categoria_cnh=categoria_cnh or None,
            validade_cnh=validade_cnh or None,
            ativo=True
        )

        db.session.add(colaborador)
        db.session.commit()

        flash(
            "Colaborador cadastrado com sucesso!",
            "success"
        )

        return redirect(
            url_for("colaboradores.index")
        )

    return render_template(
        "colaboradores/form.html"
    )


@colaboradores_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
@admin_required
def editar(id):

    colaborador = db.get_or_404(
        Colaborador,
        id
    )

    if request.method == "POST":

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        funcao = request.form.get(
            "funcao",
            ""
        ).strip()

        categoria_cnh = request.form.get(
            "categoria_cnh",
            ""
        ).strip().upper()

        validade_cnh = request.form.get(
            "validade_cnh",
            ""
        ).strip()

        if not nome or not funcao:

            flash(
                "Nome e função são obrigatórios.",
                "danger"
            )

            return render_template(
                "colaboradores/form.html",
                colaborador=colaborador
            )

        colaborador.nome = nome
        colaborador.funcao = funcao
        colaborador.categoria_cnh = (
            categoria_cnh or None
        )
        colaborador.validade_cnh = (
            validade_cnh or None
        )

        db.session.commit()

        flash(
            "Colaborador atualizado com sucesso!",
            "success"
        )

        return redirect(
            url_for("colaboradores.index")
        )

    return render_template(
        "colaboradores/form.html",
        colaborador=colaborador
    )


@colaboradores_bp.route(
    "/desativar/<int:id>",
    methods=["POST"]
)
@admin_required
def desativar(id):

    colaborador = db.get_or_404(
        Colaborador,
        id
    )

    colaborador.ativo = False

    db.session.commit()

    flash(
        "Colaborador desativado.",
        "success"
    )

    return redirect(
        url_for("colaboradores.index")
    )