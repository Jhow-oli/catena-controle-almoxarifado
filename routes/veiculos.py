from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from database.connection import db
from database.models import Veiculo
from utils.decorators import admin_required


veiculos_bp = Blueprint(
    "veiculos",
    __name__,
    url_prefix="/veiculos"
)


@veiculos_bp.route("/")
@admin_required
def index():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()

    consulta = Veiculo.query

    if pesquisa:

        consulta = consulta.filter(
            db.or_(
                Veiculo.marca.ilike(
                    f"%{pesquisa}%"
                ),
                Veiculo.modelo.ilike(
                    f"%{pesquisa}%"
                ),
                Veiculo.placa.ilike(
                    f"%{pesquisa}%"
                ),
                Veiculo.tipo.ilike(
                    f"%{pesquisa}%"
                )
            )
        )

    veiculos = consulta.order_by(
        Veiculo.marca.asc(),
        Veiculo.modelo.asc()
    ).all()

    return render_template(
        "veiculos/index.html",
        veiculos=veiculos,
        pesquisa=pesquisa
    )


@veiculos_bp.route(
    "/novo",
    methods=["GET", "POST"]
)
@admin_required
def novo():

    if request.method == "POST":

        marca = request.form.get(
            "marca",
            ""
        ).strip()

        modelo = request.form.get(
            "modelo",
            ""
        ).strip()

        placa = request.form.get(
            "placa",
            ""
        ).strip().upper()

        ano = request.form.get(
            "ano",
            ""
        ).strip()

        tipo = request.form.get(
            "tipo",
            ""
        ).strip()

        if not marca or not modelo or not placa:

            flash(
                "Marca, modelo e placa são obrigatórios.",
                "danger"
            )

            return render_template(
                "veiculos/form.html"
            )

        veiculo_existente = Veiculo.query.filter_by(
            placa=placa
        ).first()

        if veiculo_existente:

            flash(
                "Esta placa já está cadastrada.",
                "danger"
            )

            return render_template(
                "veiculos/form.html"
            )

        veiculo = Veiculo(
            marca=marca,
            modelo=modelo,
            placa=placa,
            ano=int(ano) if ano else None,
            tipo=tipo,
            ativo=True
        )

        db.session.add(veiculo)
        db.session.commit()

        flash(
            "Veículo cadastrado com sucesso!",
            "success"
        )

        return redirect(
            url_for("veiculos.index")
        )

    return render_template(
        "veiculos/form.html"
    )


@veiculos_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
@admin_required
def editar(id):

    veiculo = db.get_or_404(
        Veiculo,
        id
    )

    if request.method == "POST":

        marca = request.form.get(
            "marca",
            ""
        ).strip()

        modelo = request.form.get(
            "modelo",
            ""
        ).strip()

        placa = request.form.get(
            "placa",
            ""
        ).strip().upper()

        ano = request.form.get(
            "ano",
            ""
        ).strip()

        tipo = request.form.get(
            "tipo",
            ""
        ).strip()

        if not marca or not modelo or not placa:

            flash(
                "Marca, modelo e placa são obrigatórios.",
                "danger"
            )

            return render_template(
                "veiculos/form.html",
                veiculo=veiculo
            )

        outro_veiculo = Veiculo.query.filter(
            Veiculo.placa == placa,
            Veiculo.id != veiculo.id
        ).first()

        if outro_veiculo:

            flash(
                "Esta placa já está sendo utilizada por outro veículo.",
                "danger"
            )

            return render_template(
                "veiculos/form.html",
                veiculo=veiculo
            )

        veiculo.marca = marca
        veiculo.modelo = modelo
        veiculo.placa = placa
        veiculo.ano = int(ano) if ano else None
        veiculo.tipo = tipo

        db.session.commit()

        flash(
            "Veículo atualizado com sucesso!",
            "success"
        )

        return redirect(
            url_for("veiculos.index")
        )

    return render_template(
        "veiculos/form.html",
        veiculo=veiculo
    )


@veiculos_bp.route(
    "/desativar/<int:id>",
    methods=["POST"]
)
@admin_required
def desativar(id):

    veiculo = db.get_or_404(
        Veiculo,
        id
    )

    veiculo.ativo = False

    db.session.commit()

    flash(
        "Veículo desativado.",
        "success"
    )

    return redirect(
        url_for("veiculos.index")
    )