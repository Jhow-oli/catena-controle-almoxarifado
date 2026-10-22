from flask import Blueprint, render_template, request, send_file
from flask_login import current_user

# GERAÇÃO DE RELATÓRIOS PDF
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle
)

from utils.decorators import admin_required
from database.models import Material, Movimentacao

import os
from flask import current_app, send_file
from reportlab.platypus import Image

from sqlalchemy import func



# -------------------------------------------------
# BLUEPRINT DE RELATÓRIOS
# -------------------------------------------------

relatorios_bp = Blueprint(
    "relatorios",
    __name__,
    url_prefix="/relatorios"
)


# -------------------------------------------------
# PÁGINA INICIAL DOS RELATÓRIOS
# -------------------------------------------------

@relatorios_bp.route("/")
@admin_required
def index():

    return render_template(
        "relatorios/index.html"
    )

# -------------------------------------------------
# RELATÓRIO DE ESTOQUE
# -------------------------------------------------

@relatorios_bp.route("/estoque")
@admin_required
def estoque():

    materiais = (
        Material.query
        .filter_by(ativo=True)
        .order_by(Material.nome.asc())
        .all()
    )

    pesquisa = request.args.get("pesquisa", "").strip()

    if pesquisa:
        termo = pesquisa.casefold()

        materiais = [
            material for material in materiais
            if termo in (material.nome or "").casefold()
            or termo in (material.codigo or "").casefold()
        ]

    # FILTRO POR SITUAÇÃO DO ESTOQUE
    situacao = request.args.get("situacao", "todos").strip().lower()

    if situacao not in ("todos", "normal", "baixo"):
        situacao = "todos"

    if situacao == "normal":
        materiais = [
            material for material in materiais
            if material.estoque_minimo is None
            or material.quantidade > material.estoque_minimo
        ]

    elif situacao == "baixo":
        materiais = [
            material for material in materiais
            if material.estoque_minimo is not None
            and material.quantidade <= material.estoque_minimo
        ]

    total_materiais = len(materiais)

    estoque_baixo = sum(
        1 for material in materiais
        if material.estoque_minimo is not None
        and material.quantidade <= material.estoque_minimo
    )

    estoque_normal = total_materiais - estoque_baixo

    return render_template(
        "relatorios/estoque.html",
        situacao=situacao,
        pesquisa=pesquisa,
        materiais=materiais,
        total_materiais=total_materiais,
        estoque_normal=estoque_normal,
        estoque_baixo=estoque_baixo
    )

# -------------------------------------------------
# EXPORTAÇÃO DO RELATÓRIO DE ESTOQUE EM PDF
# -------------------------------------------------

@relatorios_bp.route("/estoque/pdf")
@admin_required
def estoque_pdf():

    # Consultar materiais ativos
    consulta = (
        Material.query
        .filter_by(ativo=True)
        .order_by(Material.nome.asc())
    )

    materiais = consulta.all()

    # Aplicar pesquisa
    pesquisa = request.args.get("pesquisa", "").strip()

    if pesquisa:
        termo = pesquisa.casefold()

        materiais = [
            material for material in materiais
            if termo in (material.nome or "").casefold()
            or termo in (material.codigo or "").casefold()
        ]

    # Aplicar filtro de situação
    situacao = request.args.get(
        "situacao", "todos"
    ).strip().lower()

    if situacao == "baixo":
        materiais = [
            material for material in materiais
            if material.estoque_minimo is not None
            and material.quantidade <= material.estoque_minimo
        ]

    elif situacao == "normal":
        materiais = [
            material for material in materiais
            if material.estoque_minimo is None
            or material.quantidade > material.estoque_minimo
        ]

    # Preparar PDF em memória
    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    estilos = getSampleStyleSheet()
    elementos = []

    # CABEÇALHO COM LOGOTIPO CATENA
    caminho_logo = os.path.join(
        current_app.static_folder,
        "img",
        "Catena logo.jpg"
    )

    nome_empresa = Paragraph(
        "<b>CATENA ENGENHARIA</b>",
        estilos["Title"]
    )

    if os.path.exists(caminho_logo):

        logo = Image(
            caminho_logo,
            width=2.5 * cm,
            height=2.5 * cm,
            kind="proportional"
        )

        cabecalho = Table(
            [[logo, nome_empresa]],
            colWidths=[3.5 * cm, 22 * cm]
        )

        cabecalho.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0)
        ]))

        elementos.append(cabecalho)

    else:
        elementos.append(nome_empresa)


    elementos.append(
        Paragraph(
            "Relatório de Estoque",
            estilos["Heading2"]
        )
    )

    data_emissao = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).strftime("%d/%m/%Y %H:%M")

    elementos.append(
        Paragraph(
            f"Emitido em: {data_emissao}",
            estilos["Normal"]
        )
    )

    # IDENTIFICAÇÃO DO RESPONSÁVEL PELA EMISSÃO
    from xml.sax.saxutils import escape

    nome_emissor = getattr(current_user, "nome", None)

    if not nome_emissor:
        nome_emissor = getattr(current_user, "usuario", None)

    if not nome_emissor:
        nome_emissor = "Não identificado"

    elementos.append(
        Paragraph(
            f"Emitido por: {escape(str(nome_emissor))}",
            estilos["Normal"]
        )
    )

    elementos.append(Spacer(1, 0.5 * cm))

    # -------------------------------------------------
    # FILTROS UTILIZADOS NO RELATÓRIO
    # -------------------------------------------------

    from xml.sax.saxutils import escape

    filtros = []

    if pesquisa:
        filtros.append(f"Pesquisa: {pesquisa}")

    if situacao == "normal":
        filtros.append("Situação: Estoque normal")

    elif situacao == "baixo":
        filtros.append("Situação: Estoque baixo")

    if filtros:
        texto_filtros = " | ".join(
            escape(str(filtro)) for filtro in filtros
        )
    else:
        texto_filtros = "Nenhum filtro aplicado"

    elementos.append(
        Paragraph(
            f"<b>Filtros utilizados:</b> {texto_filtros}",
            estilos["Normal"]
        )
    )

    elementos.append(Spacer(1, 0.4 * cm))

    # -------------------------------------------------
    # INDICADORES DO RELATÓRIO DE ESTOQUE
    # -------------------------------------------------

    total_materiais = len(materiais)

    estoque_baixo = sum(
        1 for material in materiais
        if material.estoque_minimo is not None
        and material.quantidade <= material.estoque_minimo
    )

    estoque_normal = total_materiais - estoque_baixo

    dados_indicadores = [
        [
            "Total de Materiais",
            "Estoque Normal",
            "Estoque Baixo"
        ],
        [
            str(total_materiais),
            str(estoque_normal),
            str(estoque_baixo)
        ]
    ]

    tabela_indicadores = Table(
        dados_indicadores,
        colWidths=[8.5 * cm] * 3,
        hAlign="LEFT"
    )

    tabela_indicadores.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#1f4e79")),

        ("TEXTCOLOR", (0, 0), (-1, 0),
         colors.white),

        ("FONTNAME", (0, 0), (-1, 0),
         "Helvetica-Bold"),

        ("FONTNAME", (0, 1), (-1, 1),
         "Helvetica-Bold"),

        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 13),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("BACKGROUND", (0, 1), (-1, 1),
         colors.HexColor("#f2f5f8")),

        ("BOX", (0, 0), (-1, -1),
         0.5, colors.lightgrey),

        ("INNERGRID", (0, 0), (-1, -1),
         0.3, colors.lightgrey),

        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9)
    ]))

    elementos.append(tabela_indicadores)
    elementos.append(Spacer(1, 0.5 * cm))

    # Tabela
    dados = [[
        "Código",
        "Material",
        "Unidade",
        "Disponível",
        "Mínimo",
        "Situação"
    ]]

    for material in materiais:

        baixo = (
            material.estoque_minimo is not None
            and material.quantidade <= material.estoque_minimo
        )

        dados.append([
            str(material.codigo or ""),
            str(material.nome or ""),
            str(material.unidade or ""),
            f"{material.quantidade:.3f}",
            f"{(material.estoque_minimo or 0):.3f}",
            "Estoque baixo" if baixo else "Normal"
        ])

    tabela = Table(
        dados,
        colWidths=[
            3.5 * cm,  # Código
            7.5 * cm,  # Material
            2.5 * cm,  # Unidade
            4.0 * cm,  # Disponível
            3.5 * cm,  # Mínimo
            4.5 * cm   # Situação
        ],
        repeatRows=1,
        hAlign="LEFT"
    )

    # PADRÃO VISUAL CATENA — TABELA DE ESTOQUE
    tabela.setStyle(TableStyle([
        # Cabeçalho azul-escuro
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#1f4e79")),

        # Texto branco no cabeçalho
        ("TEXTCOLOR", (0, 0), (-1, 0),
         colors.white),

        # Fonte do cabeçalho
        ("FONTNAME", (0, 0), (-1, 0),
         "Helvetica-Bold"),

        ("FONTSIZE", (0, 0), (-1, -1), 9),

        # Alinhamento dos valores numéricos
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),

        # Alinhamento vertical
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        # Espaçamento padronizado
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),

        # Bordas discretas
        ("GRID", (0, 0), (-1, -1),
         0.3, colors.lightgrey),

        # Linhas alternadas
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#f2f5f8")
        ])
    ]))

    # DESTACAR MATERIAIS COM ESTOQUE BAIXO
    for indice, material in enumerate(materiais, start=1):

        estoque_baixo = (
            material.estoque_minimo is not None
            and material.quantidade <= material.estoque_minimo
        )

        if estoque_baixo:
            tabela.setStyle(TableStyle([
                # Fundo vermelho-claro na situação
                ("BACKGROUND", (5, indice), (5, indice),
                 colors.HexColor("#FDE9E7")),

                # Texto vermelho-escuro
                ("TEXTCOLOR", (5, indice), (5, indice),
                 colors.HexColor("#C62828")),

                # Texto em negrito
                ("FONTNAME", (5, indice), (5, indice),
                 "Helvetica-Bold")
            ]))

    elementos.append(tabela)

    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(
        Paragraph(
            f"Total de materiais: {len(materiais)}",
            estilos["Normal"]
        )
    )

    # RODAPÉ DO RELATÓRIO
    def adicionar_rodape(canvas, doc):
        canvas.saveState()

        largura_pagina, _ = doc.pagesize

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)

        canvas.drawString(
            1.5 * cm,
            1 * cm,
            "CATENA ENGENHARIA | Controle de Almoxarifado"
        )

        canvas.drawRightString(
            largura_pagina - 1.5 * cm,
            1 * cm,
            f"Página {doc.page}"
        )

        canvas.restoreState()

    documento.build(
        elementos,
        onFirstPage=adicionar_rodape,
        onLaterPages=adicionar_rodape
    )

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_estoque_catena.pdf",
        mimetype="application/pdf"
    )

# -------------------------------------------------
# RELATÓRIO DE MOVIMENTAÇÕES
# -------------------------------------------------

@relatorios_bp.route("/movimentacoes")
@admin_required
def movimentacoes():

    movimentacoes = (
        Movimentacao.query
        .order_by(Movimentacao.id.desc())
        .all()
    )

    # PESQUISA POR NÚMERO DA OS OU ID DA MOVIMENTAÇÃO
    pesquisa = request.args.get("pesquisa", "").strip()

    if pesquisa:

        termo = pesquisa.casefold()
        pesquisa_id = pesquisa.lstrip("#")

        movimentacoes = [
            mov for mov in movimentacoes
            if termo in (mov.numero_os or "").casefold()
            or (
                pesquisa_id.isdigit()
                and mov.id == int(pesquisa_id)
            )
        ]

    # FILTRO POR TIPO DE MOVIMENTAÇÃO
    tipo = request.args.get("tipo", "TODOS").strip().upper()

    tipos_permitidos = (
        "TODOS",
        "ENTRADA",
        "SAIDA",
        "RETORNO",
        "CONSUMO"
    )

    if tipo not in tipos_permitidos:
        tipo = "TODOS"

    if tipo != "TODOS":
        movimentacoes = [
            mov for mov in movimentacoes
            if mov.tipo == tipo
        ]

    # FILTRO POR SITUAÇÃO DA MOVIMENTAÇÃO
    situacao = request.args.get(
        "situacao", "TODAS"
    ).strip().upper()

    situacoes_permitidas = (
        "TODAS",
        "ABERTA",
        "ENCERRADA"
    )

    if situacao not in situacoes_permitidas:
        situacao = "TODAS"

    if situacao != "TODAS":
        movimentacoes = [
            mov for mov in movimentacoes
            if mov.status == situacao
        ]

    # FILTRO POR PERÍODO
    data_inicial = request.args.get("data_inicial", "").strip()
    data_final = request.args.get("data_final", "").strip()

    # Filtrar a partir da data inicial
    if data_inicial:
        try:
            inicio = datetime.strptime(
                data_inicial, "%Y-%m-%d"
            ).date()

            movimentacoes = [
                mov for mov in movimentacoes
                if mov.criado_em
                and mov.criado_em.date() >= inicio
            ]

        except ValueError:
            data_inicial = ""

    # Filtrar até a data final, inclusive
    if data_final:
        try:
            fim = datetime.strptime(
                data_final, "%Y-%m-%d"
            ).date()

            movimentacoes = [
                mov for mov in movimentacoes
                if mov.criado_em
                and mov.criado_em.date() <= fim
            ]

        except ValueError:
            data_final = ""

    # INDICADORES
    total_movimentacoes = len(movimentacoes)

    total_entradas = sum(
        1 for mov in movimentacoes
        if mov.tipo == "ENTRADA"
    )

    total_saidas = sum(
        1 for mov in movimentacoes
        if mov.tipo == "SAIDA"
    )

    total_retornos = sum(
        1 for mov in movimentacoes
        if mov.tipo == "RETORNO"
    )

    total_consumos = sum(
        1 for mov in movimentacoes
        if mov.tipo == "CONSUMO"
    )

    return render_template(
        "relatorios/movimentacoes.html",
        data_inicial=data_inicial,
        data_final=data_final,
        movimentacoes=movimentacoes,
        situacao=situacao,
        tipo=tipo,
        pesquisa=pesquisa,
        total_movimentacoes=total_movimentacoes,
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        total_retornos=total_retornos,
        total_consumos=total_consumos
    )

# -------------------------------------------------
# EXPORTAÇÃO DO RELATÓRIO DE MOVIMENTAÇÕES EM PDF
# -------------------------------------------------

@relatorios_bp.route("/movimentacoes/pdf")
@admin_required
def movimentacoes_pdf():

    movimentacoes = (
        Movimentacao.query
        .order_by(Movimentacao.id.desc())
        .all()
    )

    # PESQUISA POR OS OU ID
    pesquisa = request.args.get("pesquisa", "").strip()

    if pesquisa:
        termo = pesquisa.casefold()
        pesquisa_id = pesquisa.lstrip("#")

        movimentacoes = [
            mov for mov in movimentacoes
            if termo in (mov.numero_os or "").casefold()
            or (
                pesquisa_id.isdigit()
                and mov.id == int(pesquisa_id)
            )
        ]

    # FILTRO POR TIPO
    tipo = request.args.get("tipo", "TODOS").strip().upper()

    if tipo in ("ENTRADA", "SAIDA", "RETORNO", "CONSUMO"):
        movimentacoes = [
            mov for mov in movimentacoes
            if mov.tipo == tipo
        ]

    # FILTRO POR SITUAÇÃO
    situacao = request.args.get("situacao", "TODAS").strip().upper()

    if situacao in ("ABERTA", "ENCERRADA"):
        movimentacoes = [
            mov for mov in movimentacoes
            if mov.status == situacao
        ]

    # FILTRO POR PERÍODO
    data_inicial = request.args.get("data_inicial", "").strip()
    data_final = request.args.get("data_final", "").strip()

    if data_inicial:
        try:
            inicio = datetime.strptime(data_inicial, "%Y-%m-%d").date()
            movimentacoes = [
                mov for mov in movimentacoes
                if mov.criado_em and mov.criado_em.date() >= inicio
            ]
        except ValueError:
            data_inicial = ""

    if data_final:
        try:
            fim = datetime.strptime(data_final, "%Y-%m-%d").date()
            movimentacoes = [
                mov for mov in movimentacoes
                if mov.criado_em and mov.criado_em.date() <= fim
            ]
        except ValueError:
            data_final = ""

    # INDICADORES DAS MOVIMENTAÇÕES FILTRADAS

    total_movimentacoes = len(movimentacoes)

    total_entradas = sum(
        1 for mov in movimentacoes
        if mov.tipo == "ENTRADA"
    )

    total_saidas = sum(
        1 for mov in movimentacoes
        if mov.tipo == "SAIDA"
    )

    total_retornos = sum(
        1 for mov in movimentacoes
        if mov.tipo == "RETORNO"
    )

    total_consumos = sum(
        1 for mov in movimentacoes
        if mov.tipo == "CONSUMO"
    )

    # PREPARAR DOCUMENTO
    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    estilos = getSampleStyleSheet()
    elementos = []

    # LOGOTIPO DA CATENA
    caminho_logo = os.path.join(
        current_app.static_folder,
        "img",
        "Catena logo.jpg"
    )

    titulo = Paragraph(
        "<b>CATENA ENGENHARIA</b>",
        estilos["Title"]
    )

    if os.path.exists(caminho_logo):
        logo = Image(
            caminho_logo,
            width=2.5 * cm,
            height=2.5 * cm,
            kind="proportional"
        )

        cabecalho = Table(
            [[logo, titulo]],
            colWidths=[3.5 * cm, 22 * cm]
        )

        cabecalho.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0)
        ]))

        elementos.append(cabecalho)
    else:
        elementos.append(titulo)

    elementos.append(
        Paragraph("Relatório de Movimentações", estilos["Heading2"])
    )

    data_emissao = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).strftime("%d/%m/%Y %H:%M")

    elementos.append(
        Paragraph(f"Emitido em: {data_emissao}", estilos["Normal"])
    )

# IDENTIFICAÇÃO DO RESPONSÁVEL PELA EMISSÃO
    from xml.sax.saxutils import escape
    
    nome_emissor = getattr(current_user, "nome", None)
    
    if not nome_emissor:
        nome_emissor = getattr(current_user, "usuario", None)
    
    if not nome_emissor:
        nome_emissor = "Não identificado"
    
    elementos.append(
        Paragraph(
            f"Emitido por: {escape(str(nome_emissor))}",
            estilos["Normal"]
        )
    )

    elementos.append(Spacer(1, 0.5 * cm))

    # RESUMO DOS FILTROS UTILIZADOS

    filtros = []

    if pesquisa:
        filtros.append(f"Pesquisa: {pesquisa}")

    if tipo in ("ENTRADA", "SAIDA", "RETORNO", "CONSUMO"):
        filtros.append(f"Tipo: {tipo}")

    if situacao in ("ABERTA", "ENCERRADA"):
        filtros.append(f"Situação: {situacao}")

    if data_inicial:
        data_formatada = datetime.strptime(
            data_inicial, "%Y-%m-%d"
        ).strftime("%d/%m/%Y")

        filtros.append(f"Data inicial: {data_formatada}")

    if data_final:
        data_formatada = datetime.strptime(
            data_final, "%Y-%m-%d"
        ).strftime("%d/%m/%Y")

        filtros.append(f"Data final: {data_formatada}")

    from xml.sax.saxutils import escape

    if filtros:
        texto_filtros = " | ".join(
            escape(str(filtro)) for filtro in filtros
        )
    else:
        texto_filtros = "Nenhum filtro aplicado"

    elementos.append(
        Paragraph(
            f"<b>Filtros utilizados:</b> {texto_filtros}",
            estilos["Normal"]
        )
    )

    elementos.append(Spacer(1, 0.4 * cm))

    # TABELA DE INDICADORES DO RELATÓRIO

    dados_indicadores = [
        [
            "Total",
            "Entradas",
            "Saídas",
            "Retornos",
            "Consumos"
        ],
        [
            str(total_movimentacoes),
            str(total_entradas),
            str(total_saidas),
            str(total_retornos),
            str(total_consumos)
        ]
    ]

    tabela_indicadores = Table(
        dados_indicadores,
        colWidths=[5 * cm] * 5,
        hAlign="LEFT"
    )

    tabela_indicadores.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#1f4e79")),

        ("TEXTCOLOR", (0, 0), (-1, 0),
         colors.white),

        ("FONTNAME", (0, 0), (-1, 0),
         "Helvetica-Bold"),

        ("FONTNAME", (0, 1), (-1, 1),
         "Helvetica-Bold"),

        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 13),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("BACKGROUND", (0, 1), (-1, 1),
         colors.HexColor("#f2f5f8")),

        ("BOX", (0, 0), (-1, -1),
         0.5, colors.lightgrey),

        ("INNERGRID", (0, 0), (-1, -1),
         0.3, colors.lightgrey),

        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9)
    ]))

    elementos.append(tabela_indicadores)
    elementos.append(Spacer(1, 0.5 * cm))

    # ESTILO DAS CÉLULAS
    estilo_celula = estilos["Normal"].clone("CelulaMovimentacao")
    estilo_celula.fontSize = 8
    estilo_celula.leading = 10

    # TABELA
    dados = [[
        "Identificação",
        "Data",
        "Tipo",
        "Colaborador",
        "Destino",
        "Situação"
    ]]

    for mov in movimentacoes:

        identificacao = mov.numero_os or f"#{mov.id}"

        data = (
            mov.criado_em.strftime("%d/%m/%Y %H:%M")
            if mov.criado_em else "-"
        )

        colaborador = (
            mov.colaborador.nome
            if mov.colaborador else "-"
        )

        valores = [
            identificacao,
            data,
            mov.tipo,
            colaborador,
            mov.destino or "-",
            mov.status
        ]

        from xml.sax.saxutils import escape

        dados.append([
            Paragraph(escape(str(valor)), estilo_celula)
            for valor in valores
        ])

    tabela = Table(
        dados,
        colWidths=[
            3.5 * cm,  # Identificação
            3.5 * cm,  # Data
            2.5 * cm,  # Tipo
            5.5 * cm,  # Colaborador
            6.5 * cm,  # Destino
            3.5 * cm   # Situação
        ],
        repeatRows=1,
        hAlign="LEFT"
    )

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#f2f5f8")
        ])
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(
        Paragraph(
            f"Total de movimentações: {len(movimentacoes)}",
            estilos["Normal"]
        )
    )

    # RODAPÉ
    def adicionar_rodape(canvas, doc):
        canvas.saveState()

        largura, _ = doc.pagesize

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
        onFirstPage=adicionar_rodape,
        onLaterPages=adicionar_rodape
    )

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_movimentacoes_catena.pdf",
        mimetype="application/pdf"
    )

# -------------------------------------------------
# RELATÓRIO DE ORDENS DE SERVIÇO
# -------------------------------------------------

@relatorios_bp.route("/ordens-servico")
@admin_required
def ordens_servico():

    # FILTROS
    pesquisa = request.args.get(
        "pesquisa", ""
    ).strip()

    situacao = request.args.get(
        "situacao", "TODAS"
    ).strip().upper()

    data_inicial = request.args.get(
        "data_inicial", ""
    ).strip()

    data_final = request.args.get(
        "data_final", ""
    ).strip()

    # CONSULTA DAS ORDENS DE SERVIÇO
    consulta = Movimentacao.query.filter(
        Movimentacao.tipo == "SAIDA",
        Movimentacao.numero_os.isnot(None)
    )

    # FILTRO POR NÚMERO DA OS
    if pesquisa:
        consulta = consulta.filter(
            Movimentacao.numero_os.ilike(
                f"%{pesquisa}%"
            )
        )

    # FILTRO POR SITUAÇÃO
    if situacao in ("ABERTA", "ENCERRADA"):
        consulta = consulta.filter(
            Movimentacao.status == situacao
        )
    else:
        situacao = "TODAS"

    # FILTRO POR DATA INICIAL
    if data_inicial:
        try:
            inicio = datetime.strptime(
                data_inicial, "%Y-%m-%d"
            ).date()

            consulta = consulta.filter(
                func.date(Movimentacao.data_movimentacao) >= inicio
            )

        except ValueError:
            data_inicial = ""

    # FILTRO POR DATA FINAL
    if data_final:
        try:
            fim = datetime.strptime(
                data_final, "%Y-%m-%d"
            ).date()

            consulta = consulta.filter(
                func.date(Movimentacao.data_movimentacao) <= fim
            )

        except ValueError:
            data_final = ""

    # ORDENAÇÃO
    ordens = consulta.order_by(
        Movimentacao.id.desc()
    ).all()

    # INDICADORES
    total_os = len(ordens)

    os_abertas = sum(
        1 for ordem in ordens
        if ordem.status == "ABERTA"
    )

    os_encerradas = sum(
        1 for ordem in ordens
        if ordem.status == "ENCERRADA"
    )

    return render_template(
        "relatorios/ordens_servico.html",
        ordens=ordens,
        total_os=total_os,
        os_abertas=os_abertas,
        os_encerradas=os_encerradas,
        pesquisa=pesquisa,
        situacao=situacao,
        data_inicial=data_inicial,
        data_final=data_final
    )

# -------------------------------------------------
# EXPORTAÇÃO PDF — ORDENS DE SERVIÇO
# -------------------------------------------------

@relatorios_bp.route("/ordens-servico/pdf")
@admin_required
def ordens_servico_pdf():

    # CONSULTA DAS ORDENS DE SERVIÇO
    pesquisa = request.args.get("pesquisa", "").strip()
    situacao = request.args.get("situacao", "TODAS").strip().upper()
    data_inicial = request.args.get("data_inicial", "").strip()
    data_final = request.args.get("data_final", "").strip()

    consulta = Movimentacao.query.filter(
        Movimentacao.tipo == "SAIDA",
        Movimentacao.numero_os.isnot(None)
    )

    # FILTRO POR NÚMERO DA OS
    if pesquisa:
        consulta = consulta.filter(
            Movimentacao.numero_os.ilike(f"%{pesquisa}%")
        )

    # FILTRO POR SITUAÇÃO
    if situacao in ("ABERTA", "ENCERRADA"):
        consulta = consulta.filter(
            Movimentacao.status == situacao
        )

    # FILTRO POR DATA INICIAL
    if data_inicial:
        try:
            inicio = datetime.strptime(
                data_inicial, "%Y-%m-%d"
            ).date()

            consulta = consulta.filter(
                func.date(Movimentacao.data_movimentacao) >= inicio
            )
        except ValueError:
            data_inicial = ""

    # FILTRO POR DATA FINAL
    if data_final:
        try:
            fim = datetime.strptime(
                data_final, "%Y-%m-%d"
            ).date()

            consulta = consulta.filter(
                func.date(Movimentacao.data_movimentacao) <= fim
            )
        except ValueError:
            data_final = ""

    # ORDENS FILTRADAS
    ordens = consulta.order_by(
        Movimentacao.id.desc()
    ).all()

    # INDICADORES
    total_os = len(ordens)

    os_abertas = sum(
        1 for ordem in ordens
        if ordem.status == "ABERTA"
    )

    os_encerradas = sum(
        1 for ordem in ordens
        if ordem.status == "ENCERRADA"
    )

    # DOCUMENTO PDF
    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    estilos = getSampleStyleSheet()
    elementos = []

    # LOGOTIPO E TÍTULO
    caminho_logo = os.path.join(
        current_app.static_folder,
        "img",
        "Catena logo.jpg"
    )

    titulo = Paragraph(
        "<b>CATENA ENGENHARIA</b>",
        estilos["Title"]
    )

    if os.path.exists(caminho_logo):

        logo = Image(
            caminho_logo,
            width=2.5 * cm,
            height=2.5 * cm,
            kind="proportional"
        )

        cabecalho = Table(
            [[logo, titulo]],
            colWidths=[3.5 * cm, 22 * cm]
        )

        cabecalho.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0)
        ]))

        elementos.append(cabecalho)

    else:
        elementos.append(titulo)

    # TÍTULO DO RELATÓRIO
    elementos.append(
        Paragraph(
            "Relatório de Ordens de Serviço",
            estilos["Heading2"]
        )
    )

    # DATA DE EMISSÃO
    data_emissao = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).strftime("%d/%m/%Y %H:%M")

    elementos.append(
        Paragraph(
            f"Emitido em: {data_emissao}",
            estilos["Normal"]
        )
    )

    # IDENTIFICAÇÃO DO RESPONSÁVEL PELA EMISSÃO
    from xml.sax.saxutils import escape
    
    nome_emissor = getattr(current_user, "nome", None)
    
    if not nome_emissor:
        nome_emissor = getattr(current_user, "usuario", None)
    
    if not nome_emissor:
        nome_emissor = "Não identificado"
    
    elementos.append(
        Paragraph(
            f"Emitido por: {escape(str(nome_emissor))}",
            estilos["Normal"]
        )
    )

    elementos.append(Spacer(1, 0.5 * cm))

    # RESUMO DOS FILTROS UTILIZADOS
    from xml.sax.saxutils import escape

    pesquisa = request.args.get("pesquisa", "").strip()
    situacao = request.args.get("situacao", "TODAS").strip().upper()
    data_inicial = request.args.get("data_inicial", "").strip()
    data_final = request.args.get("data_final", "").strip()

    filtros = []

    if pesquisa:
        filtros.append(f"Pesquisa: {pesquisa}")

    if situacao in ("ABERTA", "ENCERRADA"):
        filtros.append(f"Situação: {situacao}")

    if data_inicial:
        try:
            data_formatada = datetime.strptime(
                data_inicial, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
            filtros.append(f"Data inicial: {data_formatada}")
        except ValueError:
            pass

    if data_final:
        try:
            data_formatada = datetime.strptime(
                data_final, "%Y-%m-%d"
            ).strftime("%d/%m/%Y")
            filtros.append(f"Data final: {data_formatada}")
        except ValueError:
            pass

    if filtros:
        texto_filtros = " | ".join(
            escape(str(filtro)) for filtro in filtros
        )
    else:
        texto_filtros = "Nenhum filtro aplicado"

    elementos.append(
        Paragraph(
            f"<b>Filtros utilizados:</b> {texto_filtros}",
            estilos["Normal"]
        )
    )

    elementos.append(Spacer(1, 0.4 * cm))

    # TABELA DE INDICADORES
    dados_indicadores = [
        ["Total de OS", "OS Abertas", "OS Encerradas"],
        [str(total_os), str(os_abertas), str(os_encerradas)]
    ]

    tabela_indicadores = Table(
        dados_indicadores,
        colWidths=[8.5 * cm, 8.5 * cm, 8.5 * cm],
        hAlign="LEFT"
    )

    tabela_indicadores.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#1f4e79")),

        ("TEXTCOLOR", (0, 0), (-1, 0),
         colors.white),

        ("FONTNAME", (0, 0), (-1, 0),
         "Helvetica-Bold"),

        ("FONTNAME", (0, 1), (-1, 1),
         "Helvetica-Bold"),

        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 13),

        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("BACKGROUND", (0, 1), (-1, 1),
         colors.HexColor("#f2f5f8")),

        ("BOX", (0, 0), (-1, -1),
         0.5, colors.lightgrey),

        ("INNERGRID", (0, 0), (-1, -1),
         0.3, colors.lightgrey),

        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9)
    ]))

    elementos.append(tabela_indicadores)

    elementos.append(Spacer(1, 0.5 * cm))

    # -------------------------------------------------
    # TABELA DE ORDENS DE SERVIÇO
    # -------------------------------------------------

    from xml.sax.saxutils import escape

    estilo_celula = estilos["Normal"].clone(
        "CelulaOrdemServico"
    )

    estilo_celula.fontSize = 8
    estilo_celula.leading = 10

    dados = [[
        "Número da OS",
        "Data",
        "Colaborador",
        "Destino",
        "Situação"
    ]]

    for ordem in ordens:

        numero_os = ordem.numero_os or f"#{ordem.id}"

        data = (
            ordem.data_movimentacao.strftime("%d/%m/%Y %H:%M")
            if ordem.data_movimentacao
            else "-"
        )

        colaborador = (
            ordem.colaborador.nome
            if ordem.colaborador
            else "-"
        )

        destino = ordem.destino or "-"

        situacao = (
            "Aberta"
            if ordem.status == "ABERTA"
            else "Encerrada"
            if ordem.status == "ENCERRADA"
            else ordem.status or "-"
        )

        valores = [
            numero_os,
            data,
            colaborador,
            destino,
            situacao
        ]

        dados.append([
            Paragraph(
                escape(str(valor)),
                estilo_celula
            )
            for valor in valores
        ])

    if not ordens:
        dados.append([
            Paragraph(
                "Nenhuma Ordem de Serviço encontrada.",
                estilo_celula
            ),
            "",
            "",
            "",
            ""
        ])

    tabela_os = Table(
        dados,
        colWidths=[
            4.5 * cm,  # Número da OS
            4.0 * cm,  # Data
            6.0 * cm,  # Colaborador
            7.0 * cm,  # Destino
            4.0 * cm   # Situação
        ],
        repeatRows=1,
        hAlign="LEFT"
    )

    # PADRÃO VISUAL CATENA — TABELA DE OS
    tabela_os.setStyle(TableStyle([
        # Cabeçalho azul-escuro
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#1f4e79")),

        # Texto branco no cabeçalho
        ("TEXTCOLOR", (0, 0), (-1, 0),
         colors.white),

        # Fonte do cabeçalho
        ("FONTNAME", (0, 0), (-1, 0),
         "Helvetica-Bold"),

        ("FONTSIZE", (0, 0), (-1, 0), 9),

        # Alinhamento vertical
        ("VALIGN", (0, 0), (-1, -1),
         "MIDDLE"),

        # Espaçamento das células
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),

        # Bordas discretas
        ("GRID", (0, 0), (-1, -1),
         0.3, colors.lightgrey),

        # Linhas alternadas
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#f2f5f8")
        ])
    ]))

    elementos.append(tabela_os)

    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(
        Paragraph(
            f"Total de Ordens de Serviço: {total_os}",
            estilos["Normal"]
        )
    )

    # GERA O PDF
    # -------------------------------------------------
    # RODAPÉ PADRÃO CATENA ENGENHARIA
    # -------------------------------------------------

    def adicionar_rodape(canvas, doc):
        canvas.saveState()

        largura, _ = doc.pagesize

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

    # GERA O PDF COM RODAPÉ EM TODAS AS PÁGINAS
    documento.build(
        elementos,
        onFirstPage=adicionar_rodape,
        onLaterPages=adicionar_rodape
    )

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_ordens_servico_catena.pdf",
        mimetype="application/pdf"
    )
