import io

import qrcode

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    current_app
)

from database.connection import db
from database.models import Material

from utils.decorators import admin_required

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


materiais_bp = Blueprint(
    "materiais",
    __name__,
    url_prefix="/materiais"
)


@materiais_bp.route("/")
@admin_required
def index():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()

    consulta = Material.query

    if pesquisa:

        consulta = consulta.filter(
            db.or_(
                Material.codigo.ilike(
                    f"%{pesquisa}%"
                ),
                Material.nome.ilike(
                    f"%{pesquisa}%"
                ),
                Material.localizacao.ilike(
                    f"%{pesquisa}%"
                )
            )
        )

    materiais = consulta.order_by(
        Material.nome.asc()
    ).all()

    return render_template(
        "materiais/index.html",
        materiais=materiais,
        pesquisa=pesquisa
    )


@materiais_bp.route("/novo", methods=["GET", "POST"])
@admin_required
def novo():

    if request.method == "POST":

        codigo = request.form.get(
            "codigo",
            ""
        ).strip()

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        unidade = request.form.get(
            "unidade",
            "UN"
        ).strip()

        quantidade = request.form.get(
            "quantidade",
            "0"
        )

        estoque_minimo = request.form.get(
            "estoque_minimo",
            "0"
        )

        localizacao = request.form.get(
            "localizacao",
            ""
        ).strip()

        if not codigo or not nome:

            flash(
                "Código e nome são obrigatórios.",
                "danger"
            )

            return render_template(
                "materiais/form.html"
            )

        material_existente = Material.query.filter_by(
            codigo=codigo
        ).first()

        if material_existente:

            flash(
                "Já existe um material com este código.",
                "danger"
            )

            return render_template(
                "materiais/form.html"
            )

        material = Material(
            codigo=codigo,
            nome=nome,
            descricao=descricao,
            unidade=unidade,
            quantidade=quantidade,
            estoque_minimo=estoque_minimo,
            localizacao=localizacao,
            ativo=True
        )

        db.session.add(material)
        db.session.commit()

        flash(
            "Material cadastrado com sucesso!",
            "success"
        )

        return redirect(
            url_for("materiais.index")
        )

    return render_template(
        "materiais/form.html"
    )


@materiais_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar(id):

    material = db.get_or_404(
        Material,
        id
    )

    if request.method == "POST":

        codigo = request.form.get(
            "codigo",
            ""
        ).strip()

        nome = request.form.get(
            "nome",
            ""
        ).strip()

        if not codigo or not nome:

            flash(
                "Código e nome são obrigatórios.",
                "danger"
            )

            return render_template(
                "materiais/form.html",
                material=material
            )

        outro_material = Material.query.filter(
            Material.codigo == codigo,
            Material.id != material.id
        ).first()

        if outro_material:

            flash(
                "Este código já está sendo utilizado por outro material.",
                "danger"
            )

            return render_template(
                "materiais/form.html",
                material=material
            )

        material.codigo = codigo

        material.nome = nome

        material.descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        material.unidade = request.form.get(
            "unidade",
            "UN"
        ).strip()

        material.quantidade = request.form.get(
            "quantidade",
            "0"
        )

        material.estoque_minimo = request.form.get(
            "estoque_minimo",
            "0"
        )

        material.localizacao = request.form.get(
            "localizacao",
            ""
        ).strip()

        db.session.commit()

        flash(
            "Material atualizado com sucesso!",
            "success"
        )

        return redirect(
            url_for("materiais.index")
        )

    return render_template(
        "materiais/form.html",
        material=material
    )


@materiais_bp.route("/desativar/<int:id>", methods=["POST"])
@admin_required
def desativar(id):

    material = db.get_or_404(
        Material,
        id
    )

    material.ativo = False

    db.session.commit()

    flash(
        "Material desativado.",
        "success"
    )

    return redirect(
        url_for("materiais.index")
    )

@materiais_bp.route("/qr-code/<int:id>")
@admin_required
def qr_code(id):

    material = db.get_or_404(
        Material,
        id
    )

    url_material = (
        f"{current_app.config['BASE_URL']}"
        f"{url_for('materiais.visualizar', codigo=material.codigo)}"
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(
        url_material
    )

    qr.make(
        fit=True
    )

    imagem = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    arquivo = io.BytesIO()

    imagem.save(
        arquivo,
        format="PNG"
    )

    arquivo.seek(0)

    return send_file(
        arquivo,
        mimetype="image/png",
        download_name=f"qr-{material.codigo}.png"
    )

@materiais_bp.route("/visualizar/<codigo>")
def visualizar(codigo):

    material = Material.query.filter_by(
        codigo=codigo
    ).first_or_404()

    return render_template(
        "materiais/visualizar.html",
        material=material
    )

@materiais_bp.route("/etiqueta/<int:id>")
@admin_required
def etiqueta(id):

    material = db.get_or_404(
        Material,
        id
    )

    url_material = (
        f"{current_app.config['BASE_URL']}"
        f"{url_for('materiais.visualizar', codigo=material.codigo)}"
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3
    )

    qr.add_data(
        url_material
    )

    qr.make(
        fit=True
    )

    imagem_qr = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    qr_buffer = io.BytesIO()

    imagem_qr.save(
        qr_buffer,
        format="PNG"
    )

    qr_buffer.seek(0)

    pdf_buffer = io.BytesIO()

    largura, altura = A4

    pdf = canvas.Canvas(
        pdf_buffer,
        pagesize=A4
    )

    etiqueta_largura = 300
    etiqueta_altura = 330

    x = (largura - etiqueta_largura) / 2
    y = (altura - etiqueta_altura) / 2

    pdf.roundRect(
        x,
        y,
        etiqueta_largura,
        etiqueta_altura,
        12
    )

    pdf.setFont(
        "Helvetica-Bold",
        16
    )

    pdf.drawCentredString(
        largura / 2,
        y + etiqueta_altura - 30,
        "CONTROLE DE ALMOXARIFADO"
    )

    qr_tamanho = 170

    pdf.drawImage(
        ImageReader(qr_buffer),
        largura / 2 - qr_tamanho / 2,
        y + 90,
        width=qr_tamanho,
        height=qr_tamanho
    )

    pdf.setFont(
        "Helvetica-Bold",
        12
    )

    pdf.drawString(
        x + 25,
        y + 65,
        f"Código: {material.codigo}"
    )

    pdf.setFont(
        "Helvetica",
        11
    )

    nome = material.nome

    if len(nome) > 38:
        nome = nome[:35] + "..."

    pdf.drawString(
        x + 25,
        y + 47,
        f"Material: {nome}"
    )

    pdf.drawString(
        x + 25,
        y + 30,
        f"Unidade: {material.unidade}"
    )

    pdf.save()

    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        download_name=f"etiqueta-{material.codigo}.pdf"
    )