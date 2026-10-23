import io
import os
import qrcode

from io import BytesIO
from xml.sax.saxutils import escape

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
from database.models import Material, HistoricoCalibracao

from utils.decorators import admin_required

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table,
    TableStyle, Spacer, Image
)
from reportlab.lib import colors
from reportlab.lib.styles import (
    getSampleStyleSheet, ParagraphStyle
)

from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo

from flask_login import current_user




materiais_bp = Blueprint(
    "materiais",
    __name__,
    url_prefix="/materiais"
)

def obter_dados_calibracao():
    requer_calibracao = request.form.get("requer_calibracao") == "1"

    if not requer_calibracao:
        return {
            "requer_calibracao": False,
            "data_ultima_calibracao": None,
            "validade_calibracao": None,
            "numero_certificado": None
        }

    ultima = request.form.get("data_ultima_calibracao", "").strip()
    validade = request.form.get("validade_calibracao", "").strip()
    certificado = request.form.get("numero_certificado", "").strip()

    if not validade:
        raise ValueError(
            "Informe a validade da calibração do equipamento."
        )

    try:
        data_ultima = date.fromisoformat(ultima) if ultima else None
        data_validade = date.fromisoformat(validade)
    except ValueError:
        raise ValueError("Informe datas de calibração válidas.")

    if data_ultima and data_validade < data_ultima:
        raise ValueError(
            "A validade não pode ser anterior à última calibração."
        )

    return {
        "requer_calibracao": True,
        "data_ultima_calibracao": data_ultima,
        "validade_calibracao": data_validade,
        "numero_certificado": certificado or None
    }


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

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    limite_calibracao = hoje + timedelta(days=30)

    return render_template(
        "materiais/index.html",
        materiais=materiais,
        pesquisa=pesquisa,
        hoje=hoje,
        limite_calibracao=limite_calibracao
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

        numero_serie = request.form.get(
            "numero_serie",
            ""
        ).strip() or None

        if numero_serie:
            serie_existente = Material.query.filter_by(
                numero_serie=numero_serie
            ).first()

            if serie_existente:
                flash(
                    "Já existe um equipamento cadastrado com este número de série.",
                    "danger"
                )
                return render_template("materiais/form.html")

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
        try:
            dados_calibracao = obter_dados_calibracao()
        except ValueError as erro:
                flash(str(erro), "danger")
                return render_template("materiais/form.html")

        material = Material(
            codigo=codigo,
            nome=nome,
            descricao=descricao,
            unidade=unidade,
            quantidade=quantidade,
            estoque_minimo=estoque_minimo,
            localizacao=localizacao,
            numero_serie=numero_serie,
            **dados_calibracao,
            ativo=True
        )

        try:
            dados_calibracao = obter_dados_calibracao()
        except ValueError as erro:
            db.session.rollback()
            flash(str(erro), "danger")
            return render_template(
                "materiais/form.html",
                material=material
            )

        for campo, valor in dados_calibracao.items():
            setattr(material, campo, valor)

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

    material = db.get_or_404(Material, id)

    if request.method == "POST":

        codigo = request.form.get("codigo", "").strip()
        nome = request.form.get("nome", "").strip()

        if not codigo or not nome:
            flash("Código e nome são obrigatórios.", "danger")
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

        numero_serie = request.form.get(
            "numero_serie", ""
        ).strip() or None

        if numero_serie:
            serie_existente = Material.query.filter(
                Material.numero_serie == numero_serie,
                Material.id != material.id
            ).first()

            if serie_existente:
                flash(
                    "Este número de série já pertence a outro equipamento.",
                    "danger"
                )
                return render_template(
                    "materiais/form.html",
                    material=material
                )

        # A edição cadastral não registra uma nova calibração.
        # As datas e o certificado existentes são preservados.
        requer_calibracao = (
            request.form.get("requer_calibracao") == "1"
        )

        try:
            material.codigo = codigo
            material.nome = nome
            material.descricao = request.form.get(
                "descricao", ""
            ).strip()
            material.unidade = request.form.get(
                "unidade", "UN"
            ).strip()

            material.quantidade = request.form.get(
                "quantidade", "0"
            )

            material.estoque_minimo = request.form.get(
                "estoque_minimo", "0"
            )

            material.localizacao = request.form.get(
                "localizacao", ""
            ).strip()

            material.numero_serie = numero_serie
            material.requer_calibracao = requer_calibracao

            db.session.commit()

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "Erro ao editar material %s",
                id
            )

            flash(
                "Não foi possível atualizar o material.",
                "danger"
            )

            return redirect(
                url_for("materiais.editar", id=id)
            )

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

@materiais_bp.route(
    "/registrar-calibracao/<int:id>",
    methods=["GET", "POST"]
)
@admin_required
def registrar_calibracao(id):

    material = db.get_or_404(Material, id)

    if not material.ativo or not material.requer_calibracao:
        flash(
            "Este equipamento não está habilitado para calibração.",
            "warning"
        )
        return redirect(url_for("materiais.index"))

    if request.method == "POST":

        try:
            data_calibracao = date.fromisoformat(
                request.form.get("data_calibracao", "")
            )

            validade_calibracao = date.fromisoformat(
                request.form.get("validade_calibracao", "")
            )

        except ValueError:
            flash(
                "Informe datas de calibração válidas.",
                "danger"
            )
            return render_template(
                "materiais/registrar_calibracao.html",
                material=material
            )

        if validade_calibracao < data_calibracao:
            flash(
                "A validade não pode ser anterior à data da calibração.",
                "danger"
            )
            return render_template(
                "materiais/registrar_calibracao.html",
                material=material
            )

        numero_certificado = request.form.get(
            "numero_certificado", ""
        ).strip() or None

        laboratorio = request.form.get(
            "laboratorio", ""
        ).strip() or None

        observacoes = request.form.get(
            "observacoes", ""
        ).strip() or None

        if numero_certificado and len(numero_certificado) > 100:
            flash("O certificado excede 100 caracteres.", "danger")
            return render_template(
                "materiais/registrar_calibracao.html",
                material=material
            )

        if laboratorio and len(laboratorio) > 150:
            flash("O laboratório excede 150 caracteres.", "danger")
            return render_template(
                "materiais/registrar_calibracao.html",
                material=material
            )

        # Verificar se esta calibração já foi registrada
        calibracao_existente = HistoricoCalibracao.query.filter_by(
            material_id=material.id,
            data_calibracao=data_calibracao,
            validade_calibracao=validade_calibracao,
            numero_certificado=numero_certificado
        ).first()

        if calibracao_existente:
            flash(
                "Esta calibração já foi registrada para este equipamento.",
                "warning"
            )

            return redirect(
                url_for(
                    "materiais.visualizar",
                    codigo=material.codigo
                )
            )

        try:
            historico = HistoricoCalibracao(
                material_id=material.id,
                data_calibracao=data_calibracao,
                validade_calibracao=validade_calibracao,
                numero_certificado=numero_certificado,
                laboratorio=laboratorio,
                observacoes=observacoes,
                usuario_id=current_user.id
            )

            db.session.add(historico)

            material.data_ultima_calibracao = data_calibracao
            material.validade_calibracao = validade_calibracao
            material.numero_certificado = numero_certificado

            db.session.commit()

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "Erro ao registrar calibração do material %s",
                id
            )

            flash(
                "Não foi possível registrar a calibração.",
                "danger"
            )

            return redirect(
                url_for("materiais.registrar_calibracao", id=id)
            )

        flash(
            "Nova calibração registrada com sucesso!",
            "success"
        )

        return redirect(
            url_for("materiais.visualizar", codigo=material.codigo)
        )

    return render_template(
        "materiais/registrar_calibracao.html",
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

    historico_calibracoes = HistoricoCalibracao.query.filter_by(
        material_id=material.id
    ).order_by(
        HistoricoCalibracao.data_calibracao.desc(),
        HistoricoCalibracao.id.desc()
    ).all()

    return render_template(
        "materiais/visualizar.html",
        material=material,
        historico_calibracoes=historico_calibracoes
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

@materiais_bp.route("/calibracoes-pdf/<int:id>")
@admin_required
def calibracoes_pdf(id):

    material = db.get_or_404(Material, id)

    historico = HistoricoCalibracao.query.filter_by(
        material_id=material.id
    ).order_by(
        HistoricoCalibracao.data_calibracao.desc(),
        HistoricoCalibracao.id.desc()
    ).all()

    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.5 * cm
    )

    estilos = getSampleStyleSheet()
    elementos = []

    estilo_texto = ParagraphStyle(
        "TextoCalibracaoCatena",
        parent=estilos["Normal"],
        fontSize=8,
        leading=11
    )

    estilo_titulo = ParagraphStyle(
        "TituloCalibracaoCatena",
        parent=estilos["Heading2"],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=8
    )

    def texto(valor):
        return Paragraph(
            escape(str(valor if valor is not None else "-")),
            estilo_texto
        )

    def formatar_data(valor):
        return valor.strftime("%d/%m/%Y") if valor else "-"

    def criar_tabela(cabecalho, linhas, larguras):

        dados = [[
            Paragraph(
                f"<b>{escape(str(coluna))}</b>",
                ParagraphStyle(
                    "CabecalhoCalibracaoCatena",
                    parent=estilos["Normal"],
                    fontSize=8,
                    leading=10,
                    textColor=colors.white
                )
            )
            for coluna in cabecalho
        ]]

        dados.extend(
            [texto(valor) for valor in linha]
            for linha in linhas
        )

        tabela = Table(
            dados,
            colWidths=larguras,
            repeatRows=1,
            hAlign="LEFT"
        )

        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#1f4e79")),
            ("GRID", (0, 0), (-1, -1),
             0.3, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))

        return tabela

    # CABEÇALHO
    caminho_logo = os.path.join(
        current_app.static_folder,
        "img",
        "Catena logo.jpg"
    )

    titulo = Paragraph(
        "<b>CATENA ENGENHARIA</b><br/>"
        "FICHA DE EQUIPAMENTO E HISTÓRICO DE CALIBRAÇÕES",
        estilos["Heading2"]
    )

    if os.path.exists(caminho_logo):

        logo = Image(
            caminho_logo,
            width=2.3 * cm,
            height=2.3 * cm,
            kind="proportional"
        )

        cabecalho = Table(
            [[logo, titulo]],
            colWidths=[3 * cm, 15 * cm]
        )

        elementos.append(cabecalho)

    else:
        elementos.append(titulo)

    elementos.append(Spacer(1, 0.5 * cm))

    # IDENTIFICAÇÃO DO EQUIPAMENTO
    elementos.append(
        Paragraph("Identificação do equipamento", estilo_titulo)
    )

    dados_material = [
        ["Código", material.codigo],
        ["Equipamento", material.nome],
        ["Descrição", material.descricao or "-"],
        ["Número de série", material.numero_serie or "-"],
        ["Unidade", material.unidade],
        ["Localização", material.localizacao or "-"],
        ["Status", "Ativo" if material.ativo else "Inativo"]
    ]

    tabela_material = Table(
        [[texto(campo), texto(valor)]
         for campo, valor in dados_material],
        colWidths=[5 * cm, 13 * cm]
    )

    tabela_material.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
    ]))

    elementos.append(tabela_material)

    # CALIBRAÇÃO ATUAL
    elementos.append(
        Paragraph("Calibração atual", estilo_titulo)
    )

    if material.requer_calibracao:
        dados_atuais = [
            ["Última calibração",
             formatar_data(material.data_ultima_calibracao)],
            ["Validade",
             formatar_data(material.validade_calibracao)],
            ["Certificado",
             material.numero_certificado or "-"]
        ]
    else:
        dados_atuais = [
            ["Controle de calibração", "Não aplicável"]
        ]

    tabela_atual = Table(
        [[texto(campo), texto(valor)]
         for campo, valor in dados_atuais],
        colWidths=[5 * cm, 13 * cm]
    )

    tabela_atual.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
    ]))

    elementos.append(tabela_atual)

    # HISTÓRICO
    elementos.append(
        Paragraph("Histórico de calibrações", estilo_titulo)
    )

    linhas_historico = []

    for registro in historico:

        responsavel = (
            registro.usuario.nome
            if registro.usuario else "-"
        )

        linhas_historico.append([
            formatar_data(registro.data_calibracao),
            formatar_data(registro.validade_calibracao),
            registro.numero_certificado or "-",
            registro.laboratorio or "-",
            responsavel
        ])

    if not linhas_historico:
        linhas_historico.append([
            "-", "-", "Nenhuma calibração registrada", "-", "-"
        ])

    elementos.append(criar_tabela(
        [
            "Calibração",
            "Validade",
            "Certificado",
            "Laboratório",
            "Registrado por"
        ],
        linhas_historico,
        [
            2.6 * cm,
            2.6 * cm,
            3.1 * cm,
            4.2 * cm,
            5.5 * cm
        ]
    ))

    # RODAPÉ
    def rodape(canvas, doc):

        canvas.saveState()

        largura, _ = A4

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)

        canvas.drawString(
            1.5 * cm,
            1 * cm,
            "CATENA ENGENHARIA | Controle de Almoxarifado"
        )

        canvas.drawRightString(
            largura - 1.5 * cm,
            1 * cm,
            f"Página {doc.page}"
        )

        canvas.restoreState()

    documento.build(
        elementos,
        onFirstPage=rodape,
        onLaterPages=rodape
    )

    buffer.seek(0)

    nome_arquivo = (
        f"Calibracoes_{material.codigo}"
        .replace("/", "-")
        .replace("\\", "-")
        + ".pdf"
    )

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=nome_arquivo
    )