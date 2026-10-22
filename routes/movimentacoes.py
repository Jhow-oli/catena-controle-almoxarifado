from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import text, func

from sqlalchemy.exc import IntegrityError
from uuid import UUID, uuid4

from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_login import current_user

from database.connection import db
from database.models import (
    Movimentacao,
    MovimentacaoItem,
    Colaborador,
    Veiculo,
    Material,
    SequenciaOS
)

from utils.decorators import admin_required

import os
from io import BytesIO
from xml.sax.saxutils import escape

from flask import current_app, send_file

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
    KeepTogether,
    Image
)


movimentacoes_bp = Blueprint(
    "movimentacoes",
    __name__,
    url_prefix="/movimentacoes"
)

def gerar_numero_os_saida():
    """
    Gera uma OS sequencial por dia.

    Exemplo:
        20261013/01
        20261013/02

    A numeração é controlada pelo MySQL
    dentro da transação atual.
    """

    data_atual = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).date()

    db.session.execute(
        text("""
            INSERT INTO sequencias_os (
                data_os,
                ultimo_numero
            )
            VALUES (
                :data_os,
                1
            )
            ON DUPLICATE KEY UPDATE
                ultimo_numero = ultimo_numero + 1
        """),
        {"data_os": data_atual}
    )

    ultimo_numero = db.session.execute(
        text("""
            SELECT ultimo_numero
            FROM sequencias_os
            WHERE data_os = :data_os
        """),
        {"data_os": data_atual}
    ).scalar_one()

    return (
        f"{data_atual:%Y%m%d}/"
        f"{ultimo_numero:02d}"
    )

def gerar_numero_os_vinculada(movimentacao_origem):
    """
    Gera a numeração de RETORNO e CONSUMO
    vinculada à OS de uma SAÍDA.

    Exemplo:
        SAÍDA:    20261013/01
        RETORNO:  20261013/01-01
        CONSUMO:  20261013/01-02
    """

    numero_os_origem = movimentacao_origem.numero_os

    if not numero_os_origem:
        raise ValueError(
            "A saída de origem não possui número de OS."
        )

    movimentacoes_vinculadas = (
        db.session.query(Movimentacao.numero_os)
        .filter(
            Movimentacao.movimentacao_origem_id
            == movimentacao_origem.id,
            Movimentacao.numero_os.isnot(None)
        )
        .all()
    )

    maior_sufixo = 0
    prefixo = f"{numero_os_origem}-"

    for (numero_os,) in movimentacoes_vinculadas:
        if numero_os.startswith(prefixo):
            sufixo = numero_os[len(prefixo):]

            if sufixo.isdigit():
                maior_sufixo = max(
                    maior_sufixo,
                    int(sufixo)
                )

    proximo_sufixo = maior_sufixo + 1

    return f"{numero_os_origem}-{proximo_sufixo:02d}"

@movimentacoes_bp.route("/")
@admin_required
def index():

    pesquisa = request.args.get(
        "pesquisa",
        ""
    ).strip()

    data_inicial = request.args.get(
    "data_inicial",
    ""
    ).strip()

    data_final = request.args.get(
        "data_final",
        ""
    ).strip()

    consulta = Movimentacao.query

    # -------------------------------------------------
    # FILTRO POR PERÍODO
    # -------------------------------------------------

    if data_inicial:
        consulta = consulta.filter(
            Movimentacao.data_movimentacao >=
            f"{data_inicial} 00:00:00"
        )

    if data_final:
        consulta = consulta.filter(
            Movimentacao.data_movimentacao <=
            f"{data_final} 23:59:59"
        )

    # -------------------------------------------------
    # PESQUISA
    # -------------------------------------------------

    if pesquisa:

        termo = f"%{pesquisa}%"

        # Pesquisa pelo ID da movimentação (#73 ou 73)
        pesquisa_id = pesquisa.lstrip("#")

        if pesquisa_id.isdigit():
            movimentacao_id = int(pesquisa_id)
        else:
            movimentacao_id = -1

        consulta = (
            consulta
            .outerjoin(
                Movimentacao.colaborador
            )
            .outerjoin(
                Movimentacao.itens
            )
            .outerjoin(
                MovimentacaoItem.material
            )
            .filter(
                db.or_(
                    Movimentacao.id == movimentacao_id,

                    Movimentacao.numero_os.ilike(termo),

                    Movimentacao.tipo.ilike(termo),

                    Movimentacao.status.ilike(termo),

                    Movimentacao.destino.ilike(termo),

                    Colaborador.nome.ilike(termo),

                    Material.nome.ilike(termo),

                    Material.codigo.ilike(termo)
                )
            )
            .distinct()
        )

    movimentacoes = consulta.order_by(
        Movimentacao.id.desc()
    ).all()

    return render_template(
        "movimentacoes/index.html",
        movimentacoes=movimentacoes,
        pesquisa=pesquisa,
        data_inicial=data_inicial,
        data_final=data_final
    )


@movimentacoes_bp.route(
    "/nova",
    methods=["GET", "POST"]
)
@admin_required
def nova():

    colaboradores = Colaborador.query.filter_by(
        ativo=True
    ).order_by(
        Colaborador.nome.asc()
    ).all()

    veiculos = Veiculo.query.filter_by(
        ativo=True
    ).order_by(
        Veiculo.marca.asc(),
        Veiculo.modelo.asc()
    ).all()

    materiais = Material.query.filter_by(
        ativo=True
    ).order_by(
        Material.nome.asc()
    ).all()

    # -------------------------------------------------
    # SAÍDAS ABERTAS
    # -------------------------------------------------

    saidas_abertas = Movimentacao.query.filter_by(
        tipo="SAIDA",
        status="ABERTA"
    ).order_by(
        Movimentacao.data_movimentacao.desc()
    ).all()

    # -------------------------------------------------
    # MATERIAIS PARA JAVASCRIPT
    # -------------------------------------------------

    materiais_json = []

    for material in materiais:

        materiais_json.append({
            "id": material.id,
            "nome": material.nome,
            "codigo": material.codigo,
            "unidade": material.unidade,
            "quantidade": float(
                material.quantidade
            )
        })

    # -------------------------------------------------
    # SAÍDAS PARA JAVASCRIPT
    # -------------------------------------------------

    saidas_json = []

    for saida in saidas_abertas:

        itens_saida = []

        for item in saida.itens:

            # Quantidade que já voltou anteriormente
            quantidade_retorno = (
                db.session.query(
                    db.func.coalesce(
                        db.func.sum(
                            MovimentacaoItem.quantidade_retorno
                        ),
                        0
                    )
                )
                .filter(
                    MovimentacaoItem.movimentacao_item_origem_id
                    == item.id
                )
                .scalar()
            )

            quantidade_retorno = Decimal(
                quantidade_retorno or 0
            )

            # Soma os consumos anteriores deste item
            quantidade_consumida = (
                db.session.query(
                    db.func.coalesce(
                        db.func.sum(
                            MovimentacaoItem.quantidade_consumida
                        ),
                        0
                    )
                )
                .filter(
                    MovimentacaoItem.movimentacao_item_origem_id == item.id
                )
                .scalar()
            )

            quantidade_consumida = Decimal(
                quantidade_consumida or 0
            )

            quantidade_disponivel_retorno = (
            Decimal(item.quantidade)
            - quantidade_retorno
            - quantidade_consumida
        )

            itens_saida.append({
                "id": item.id,
                "material_id": item.material_id,
                "codigo": item.material.codigo,
                "nome": item.material.nome,
                "unidade": item.material.unidade,
                "quantidade": float(
                    item.quantidade
                ),
                "quantidade_retorno": float(
                    quantidade_retorno
                ),
                "quantidade_disponivel_retorno": float(
                    quantidade_disponivel_retorno
                ),
                "quantidade_consumida": float(
                    quantidade_consumida
                ),

                "quantidade_disponivel_consumo": float(
                    quantidade_disponivel_retorno
                ),
            })

        saidas_json.append({
            "id": saida.id,
            "numero_os": saida.numero_os or f"#{saida.id}",
            "data": saida.data_movimentacao.strftime(
                "%d/%m/%Y %H:%M"
            ),
            "colaborador": (
                saida.colaborador.nome
                if saida.colaborador
                else "-"
            ),
            "veiculo": (
                saida.veiculo.placa
                if saida.veiculo
                else "-"
            ),
            "destino": saida.destino or "-",
            "itens": itens_saida
        })

    # -------------------------------------------------
    # POST
    # -------------------------------------------------

    if request.method == "POST":

        dados_formulario = request.form.to_dict(flat=False)

        chave_idempotencia = request.form.get(
            "chave_idempotencia", ""
        ).strip()

        try:
            chave_idempotencia = str(
                UUID(chave_idempotencia)
            )
        except (ValueError, AttributeError):
            flash(
                "Identificador da solicitação inválido. "
                "Abra novamente o formulário.",
                "danger"
            )
            return redirect(
                url_for("movimentacoes.nova")
            )

        movimentacao_existente = Movimentacao.query.filter_by(
            chave_idempotencia=chave_idempotencia
        ).first()

        if movimentacao_existente:
            flash(
                "Esta movimentação já foi registrada anteriormente.",
                "warning"
            )
            return redirect(
                url_for(
                    "movimentacoes.visualizar",
                    id=movimentacao_existente.id
                )
            )

        tipo = request.form.get(
            "tipo",
            ""
        ).strip().upper()

        colaborador_id = request.form.get(
            "colaborador_id"
        )

        veiculo_id = request.form.get(
            "veiculo_id"
        )

        destino = request.form.get(
            "destino",
            ""
        ).strip()

        observacoes = request.form.get(
            "observacoes",
            ""
        ).strip()

        material_ids = request.form.getlist(
            "material_id[]"
        )

        quantidades = request.form.getlist(
            "quantidade[]"
        )

        item_observacoes = request.form.getlist(
            "item_observacao[]"
        )

        movimentacao_item_origem_ids = request.form.getlist(
            "movimentacao_item_origem_id[]"
        )

        movimentacao_origem_id = request.form.get(
            "movimentacao_origem_id"
        )

        # -------------------------------------------------
        # VALIDAÇÕES
        # -------------------------------------------------

        if tipo not in [
            "ENTRADA",
            "SAIDA",
            "RETORNO",
            "CONSUMO"
        ]:

            flash(
                "Tipo de movimentação inválido.",
                "danger"
            )

            return render_template(
                "movimentacoes/form.html",
                colaboradores=colaboradores,
                veiculos=veiculos,
                materiais=materiais,
                materiais_json=materiais_json,
                saidas_json=saidas_json,
                chave_idempotencia=chave_idempotencia,
                dados_formulario=dados_formulario
            )

        if not colaborador_id:

            flash(
                "Selecione o colaborador.",
                "danger"
            )

            return render_template(
                "movimentacoes/form.html",
                colaboradores=colaboradores,
                veiculos=veiculos,
                materiais=materiais,
                materiais_json=materiais_json,
                saidas_json=saidas_json,
                chave_idempotencia=chave_idempotencia,
                dados_formulario=dados_formulario
            )

        # -------------------------------------------------
        # RETORNO — MOVIMENTAÇÃO DE ORIGEM
        # -------------------------------------------------

        if (
            tipo in ["RETORNO", "CONSUMO"]
            and not movimentacao_origem_id
        ):

            flash(
                "Selecione a movimentação de saída de origem.",
                "danger"
            )

            return render_template(
                "movimentacoes/form.html",
                colaboradores=colaboradores,
                veiculos=veiculos,
                materiais=materiais,
                materiais_json=materiais_json,
                saidas_json=saidas_json,
                chave_idempotencia=chave_idempotencia,
                dados_formulario=dados_formulario
            )

        movimentacao_origem = None

        if tipo in ["RETORNO", "CONSUMO"]:

            movimentacao_origem = (
                db.session.query(Movimentacao)
                .filter(
                    Movimentacao.id == int(movimentacao_origem_id)
                )
                .populate_existing()
                .with_for_update()
                .first()
            )

            if not movimentacao_origem:

                flash(
                    "A movimentação de saída selecionada não foi encontrada.",
                    "danger"
                )

                return render_template(
                    "movimentacoes/form.html",
                    colaboradores=colaboradores,
                    veiculos=veiculos,
                    materiais=materiais,
                    materiais_json=materiais_json,
                    saidas_json=saidas_json,
                    chave_idempotencia=chave_idempotencia,
                    dados_formulario=dados_formulario
                )

            if movimentacao_origem.tipo != "SAIDA":

                flash(
                    "A movimentação selecionada não é uma saída.",
                    "danger"
                )

                return render_template(
                    "movimentacoes/form.html",
                    colaboradores=colaboradores,
                    veiculos=veiculos,
                    materiais=materiais,
                    materiais_json=materiais_json,
                    saidas_json=saidas_json,
                    chave_idempotencia=chave_idempotencia,
                    dados_formulario=dados_formulario
                )

            if movimentacao_origem.status != "ABERTA":

                flash(
                    "Esta saída já está encerrada e não aceita novos retornos ou consumos.",
                    "danger"
                )

                return render_template(
                    "movimentacoes/form.html",
                    colaboradores=colaboradores,
                    veiculos=veiculos,
                    materiais=materiais,
                    materiais_json=materiais_json,
                    saidas_json=saidas_json,
                    chave_idempotencia=chave_idempotencia,
                    dados_formulario=dados_formulario
                )

        if not material_ids:

            flash(
                "Adicione pelo menos um material.",
                "danger"
            )

            return render_template(
                "movimentacoes/form.html",
                colaboradores=colaboradores,
                veiculos=veiculos,
                materiais=materiais,
                materiais_json=materiais_json,
                saidas_json=saidas_json,
                chave_idempotencia=chave_idempotencia,
                dados_formulario=dados_formulario
            )

        if len(material_ids) != len(
            quantidades
        ):

            flash(
                "Os materiais e quantidades não foram enviados corretamente.",
                "danger"
            )

            return render_template(
                "movimentacoes/form.html",
                colaboradores=colaboradores,
                veiculos=veiculos,
                materiais=materiais,
                materiais_json=materiais_json,
                saidas_json=saidas_json,
                chave_idempotencia=chave_idempotencia,
                dados_formulario=dados_formulario
            )

        # -------------------------------------------------
        # GERA NÚMERO DA ORDEM DE SERVIÇO
        # -------------------------------------------------

        numero_os = None

        if tipo == "SAIDA":
            numero_os = gerar_numero_os_saida()

        elif tipo in ["RETORNO", "CONSUMO"]:
            numero_os = gerar_numero_os_vinculada(
                movimentacao_origem
            )

        # -------------------------------------------------
        # CRIA MOVIMENTAÇÃO
        # -------------------------------------------------

        movimentacao = Movimentacao(
            tipo=tipo,
            numero_os=numero_os,
            chave_idempotencia=chave_idempotencia,

            movimentacao_origem_id=(
                movimentacao_origem.id
                if movimentacao_origem
                else None
            ),

            usuario_id=current_user.id,

            colaborador_id=int(
                colaborador_id
            ),

            veiculo_id=(
                int(veiculo_id)
                if veiculo_id
                else None
            ),

            destino=destino or None,

            observacoes=observacoes or None,

            status="ENCERRADA" if tipo == "ENTRADA" else "ABERTA"
        )

        db.session.add(
            movimentacao
        )

        db.session.flush()

        # -------------------------------------------------
        # CRIA OS ITENS
        # -------------------------------------------------

        itens_registrados = 0

        itens_origem_processados = set()

        for indice, material_id in enumerate(
            material_ids
        ):

            # ---------------------------------------------
            # CONVERTE MATERIAL E QUANTIDADE
            # ---------------------------------------------

            try:

                material_id_int = int(
                    material_id
                )

                quantidade = Decimal(
                    quantidades[indice].replace(
                        ",",
                        "."
                    )
                )

            except (
                ValueError,
                TypeError,
                InvalidOperation
            ):

                db.session.rollback()

                flash(
                    "Um dos materiais ou quantidades é inválido.",
                    "danger"
                )

                return render_template(
                    "movimentacoes/form.html",
                    colaboradores=colaboradores,
                    veiculos=veiculos,
                    materiais=materiais,
                    materiais_json=materiais_json,
                    saidas_json=saidas_json,
                    chave_idempotencia=chave_idempotencia,
                    dados_formulario=dados_formulario
                )

            # -------------------------------------------------
            # VALIDAÇÃO DA QUANTIDADE
            # -------------------------------------------------

            if quantidade < 0:

                db.session.rollback()

                flash(
                    "A quantidade não pode ser negativa.",
                    "danger"
                )

                return render_template(
                    "movimentacoes/form.html",
                    colaboradores=colaboradores,
                    veiculos=veiculos,
                    materiais=materiais,
                    materiais_json=materiais_json,
                    saidas_json=saidas_json,
                    chave_idempotencia=chave_idempotencia,
                    dados_formulario=dados_formulario
                )

            # -------------------------------------------------
            # RETORNO COM ZERO = IGNORA O ITEM
            # -------------------------------------------------

            if tipo in ["RETORNO", "CONSUMO"] and quantidade == 0:
                continue

            # -------------------------------------------------
            # ENTRADA E SAÍDA EXIGEM QUANTIDADE > 0
            # -------------------------------------------------

            if tipo not in ["RETORNO", "CONSUMO"] and quantidade <= 0:

                db.session.rollback()

                flash(
                    "A quantidade dos materiais deve ser maior que zero.",
                    "danger"
                )

                return render_template(
                    "movimentacoes/form.html",
                    colaboradores=colaboradores,
                    veiculos=veiculos,
                    materiais=materiais,
                    materiais_json=materiais_json,
                    saidas_json=saidas_json,
                    chave_idempotencia=chave_idempotencia,
                    dados_formulario=dados_formulario
                )

            # ---------------------------------------------
            # BUSCA MATERIAL
            # ---------------------------------------------

            material = (
                db.session.query(Material)
                .filter(Material.id == material_id_int)
                .populate_existing()
                .with_for_update()
                .first()
            )

            if not material or not material.ativo:

                db.session.rollback()

                flash(
                    "Um dos materiais selecionados não está disponível.",
                    "danger"
                )

                return render_template(
                    "movimentacoes/form.html",
                    colaboradores=colaboradores,
                    veiculos=veiculos,
                    materiais=materiais,
                    materiais_json=materiais_json,
                    saidas_json=saidas_json,
                    chave_idempotencia=chave_idempotencia,
                    dados_formulario=dados_formulario
                )

            # ---------------------------------------------
            # OBSERVAÇÃO
            # ---------------------------------------------

            observacao_item = ""

            if indice < len(
                item_observacoes
            ):

                observacao_item = (
                    item_observacoes[indice]
                    or ""
                ).strip()

            # ---------------------------------------------
            # RETORNO
            # ---------------------------------------------

            movimentacao_item_origem_id = None

            quantidade_retorno = Decimal("0")
            quantidade_consumida = Decimal("0")

            if tipo in ["RETORNO", "CONSUMO"]:

                if indice >= len(
                    movimentacao_item_origem_ids
                ):

                    db.session.rollback()

                    flash(
                        "Não foi possível identificar o item de origem do retorno.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                
                try:
                    movimentacao_item_origem_id = int(
                        movimentacao_item_origem_ids[indice]
                    )

                except (ValueError, TypeError):

                    db.session.rollback()

                    flash(
                        "O item de origem do retorno ou consumo é inválido.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                # -----------------------------------------
                # IMPEDE ITENS DE ORIGEM DUPLICADOS
                # -----------------------------------------

                if movimentacao_item_origem_id in itens_origem_processados:

                    db.session.rollback()

                    flash(
                        "O mesmo item da saída foi informado mais de uma vez.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                itens_origem_processados.add(
                    movimentacao_item_origem_id
                )


                # -----------------------------------------
                # BUSCA ITEM DA SAÍDA
                # -----------------------------------------

                item_origem = db.session.get(
                    MovimentacaoItem,
                    movimentacao_item_origem_id
                )

                if not item_origem:

                    db.session.rollback()

                    flash(
                        "O item de origem do retorno não foi encontrado.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                # -----------------------------------------
                # CONFIRMA QUE O ITEM PERTENCE À SAÍDA
                # -----------------------------------------

                if (
                    item_origem.movimentacao_id
                    != movimentacao_origem.id
                ):

                    db.session.rollback()

                    flash(
                        "O item selecionado não pertence à saída informada.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                # -----------------------------------------
                # CONFIRMA O MESMO MATERIAL
                # -----------------------------------------

                if (
                    item_origem.material_id
                    != material.id
                ):

                    db.session.rollback()

                    flash(
                        "O material do retorno não corresponde ao material da saída.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                # -----------------------------------------
                # SOMA DOS RETORNOS ANTERIORES
                # -----------------------------------------

                retornos_anteriores = (
                    db.session.query(
                        db.func.coalesce(
                            db.func.sum(
                                MovimentacaoItem.quantidade_retorno
                            ),
                            0
                        )
                    )
                    .filter(
                        MovimentacaoItem.movimentacao_item_origem_id
                        == item_origem.id
                    )
                    .scalar()
                )

                retornos_anteriores = Decimal(
                    retornos_anteriores or 0
                )

                # -----------------------------------------
                # SOMA DOS CONSUMOS ANTERIORES
                # -----------------------------------------

                consumos_anteriores = (
                    db.session.query(
                        db.func.coalesce(
                            db.func.sum(
                                MovimentacaoItem.quantidade_consumida
                            ),
                            0
                        )
                    )
                    .filter(
                        MovimentacaoItem.movimentacao_item_origem_id
                        == item_origem.id
                    )
                    .scalar()
                )

                consumos_anteriores = Decimal(
                    consumos_anteriores or 0
                )

                quantidade_disponivel = (
                    Decimal(item_origem.quantidade)
                    - retornos_anteriores
                    - consumos_anteriores
                )

                # -----------------------------------------
                # NÃO PERMITIR RETORNO ACIMA DO DISPONÍVEL
                # -----------------------------------------

                if quantidade > quantidade_disponivel:

                    db.session.rollback()

                    flash(
                        f"Quantidade de retorno inválida para "
                        f"'{material.nome}'. "
                        f"Máximo permitido: "
                        f"{quantidade_disponivel:g} "
                        f"{material.unidade}.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                if tipo == "RETORNO":
                    quantidade_retorno = quantidade

                elif tipo == "CONSUMO":
                    quantidade_consumida = quantidade

                # -----------------------------------------
                # RETORNO NÃO É UMA NOVA SAÍDA
                # -----------------------------------------

                quantidade = Decimal(
                    "0"
                )

            # ---------------------------------------------
            # ENTRADA — ADICIONA AO ESTOQUE
            # ---------------------------------------------

            if tipo == "ENTRADA":

                estoque_atual = Decimal(
                    material.quantidade
                )

                material.quantidade = (
                    estoque_atual
                    + quantidade
                )

            # ---------------------------------------------
            # SAÍDA — CONTROLE DE ESTOQUE
            # ---------------------------------------------

            if tipo == "SAIDA":

                estoque_atual = Decimal(
                    material.quantidade
                )

                if quantidade > estoque_atual:

                    print(
                        f"[VALIDAÇÃO ESTOQUE] "
                        f"Material: {material.nome} | "
                        f"Solicitado: {quantidade} | "
                        f"Disponível: {estoque_atual}",
                        flush=True
                    )
                    
                    db.session.rollback()

                    flash(
                        f"Estoque insuficiente para o material "
                        f"'{material.nome}'. "
                        f"Disponível: "
                        f"{estoque_atual.normalize():f} "
                        f"{material.unidade}.",
                        "danger"
                    )

                    return render_template(
                        "movimentacoes/form.html",
                        colaboradores=colaboradores,
                        veiculos=veiculos,
                        materiais=materiais,
                        materiais_json=materiais_json,
                        saidas_json=saidas_json,
                        chave_idempotencia=chave_idempotencia,
                        dados_formulario=dados_formulario
                    )

                material.quantidade = (
                    estoque_atual
                    - quantidade
                )

            # ---------------------------------------------
            # RETORNO — DEVOLVE AO ESTOQUE
            # ---------------------------------------------

            if tipo == "RETORNO":

                estoque_atual = Decimal(
                    material.quantidade
                )

                material.quantidade = (
                    estoque_atual
                    + quantidade_retorno
                )

            # ---------------------------------------------
            # CRIA ITEM
            # ---------------------------------------------

            item = MovimentacaoItem(
                movimentacao_id=movimentacao.id,
                movimentacao_item_origem_id=movimentacao_item_origem_id,
                material_id=material.id,
                quantidade=quantidade,
                quantidade_retorno=quantidade_retorno,
                quantidade_consumida=quantidade_consumida,
                observacoes=observacao_item or None
            )

            db.session.add(
                item
            )

            db.session.flush()

            itens_registrados += 1

            # -------------------------------------------------
            # VERIFICA SE A SAÍDA FOI TOTALMENTE
            # DEVOLVIDA OU CONSUMIDA
            # -------------------------------------------------

            if tipo in ["RETORNO", "CONSUMO"]:

                saida_encerrada = True

                for item_saida in movimentacao_origem.itens:

                    totais = (
                        db.session.query(
                            db.func.coalesce(
                                db.func.sum(
                                    MovimentacaoItem.quantidade_retorno
                                ),
                                0
                            ),
                            db.func.coalesce(
                                db.func.sum(
                                    MovimentacaoItem.quantidade_consumida
                                ),
                                0
                            )
                        )
                        .filter(
                            MovimentacaoItem.movimentacao_item_origem_id
                            == item_saida.id
                        )
                        .first()
                    )

                    total_retornado = Decimal(totais[0] or 0)
                    total_consumido = Decimal(totais[1] or 0)

                    quantidade_original = Decimal(
                        item_saida.quantidade
                    )

                    quantidade_pendente = (
                        quantidade_original
                        - total_retornado
                        - total_consumido
                    )

                    if quantidade_pendente > 0:
                        saida_encerrada = False
                        break

                if saida_encerrada:

                    # Encerra a saída original
                    movimentacao_origem.status = "ENCERRADA"

                    # Encerra a movimentação atual
                    movimentacao.status = "ENCERRADA"

                    # Encerra todos os retornos e consumos
                    # vinculados à saída original
                    movimentacoes_vinculadas = (
                        Movimentacao.query.filter(
                            Movimentacao.movimentacao_origem_id
                            == movimentacao_origem.id,
                            Movimentacao.tipo.in_(
                                ["RETORNO", "CONSUMO"]
                            )
                        ).all()
                    )

                    for vinculada in movimentacoes_vinculadas:
                        vinculada.status = "ENCERRADA"

        # -------------------------------------------------
        # SALVA
        # -------------------------------------------------

        if itens_registrados == 0:

            db.session.rollback()

            flash(
                "Informe uma quantidade maior que zero "
                "para pelo menos um material.",
                "danger"
            )

            return render_template(
                "movimentacoes/form.html",
                colaboradores=colaboradores,
                veiculos=veiculos,
                materiais=materiais,
                materiais_json=materiais_json,
                saidas_json=saidas_json,
                chave_idempotencia=chave_idempotencia,
                dados_formulario=dados_formulario
            )

        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()

            movimentacao_existente = Movimentacao.query.filter_by(
                chave_idempotencia=chave_idempotencia
            ).first()

            if movimentacao_existente:
                flash(
                    "Esta movimentação já havia sido registrada.",
                    "warning"
                )
                return redirect(
                    url_for(
                        "movimentacoes.visualizar",
                        id=movimentacao_existente.id
                    )
                )

            raise

        flash(
            "Movimentação criada com sucesso!",
            "success"
        )

        return redirect(
            url_for(
                "movimentacoes.visualizar",
                id=movimentacao.id
            )
        )

    # -------------------------------------------------
    # GET
    # -------------------------------------------------

    return render_template(
        "movimentacoes/form.html",
        colaboradores=colaboradores,
        veiculos=veiculos,
        materiais=materiais,
        materiais_json=materiais_json,
        saidas_json=saidas_json,
        chave_idempotencia=str(uuid4())
    )


@movimentacoes_bp.route(
    "/visualizar/<int:id>"
)
@admin_required
def visualizar(id):

    movimentacao = Movimentacao.query.get_or_404(id)

    # -------------------------------------------------
    # PREPARA OS ITENS PARA EXIBIÇÃO
    # -------------------------------------------------

    itens_visualizacao = []

    for item in movimentacao.itens:

        quantidade_recebida = (
            Decimal(item.quantidade or 0)
            if movimentacao.tipo == "ENTRADA"
            else Decimal("0")
        )

        quantidade_retirada = Decimal(
            item.quantidade or 0
        )

        quantidade_retorno = Decimal(
            item.quantidade_retorno or 0
        )

        quantidade_consumida = Decimal(
            item.quantidade_consumida or 0
        )

        quantidade_pendente = Decimal("0")

        # -------------------------------------------------
        # SAÍDA: SOMA RETORNOS E CONSUMOS VINCULADOS
        # -------------------------------------------------

        if movimentacao.tipo == "SAIDA":

            totais = (
                db.session.query(
                    db.func.coalesce(
                        db.func.sum(
                            MovimentacaoItem.quantidade_retorno
                        ),
                        0
                    ),
                    db.func.coalesce(
                        db.func.sum(
                            MovimentacaoItem.quantidade_consumida
                        ),
                        0
                    )
                )
                .filter(
                    MovimentacaoItem.movimentacao_item_origem_id
                    == item.id
                )
                .first()
            )

            quantidade_retorno = Decimal(
                totais[0] or 0
            )

            quantidade_consumida = Decimal(
                totais[1] or 0
            )

            quantidade_pendente = (
                quantidade_retirada
                - quantidade_retorno
                - quantidade_consumida
            )

        # -------------------------------------------------
        # RETORNO: MOSTRA SOMENTE O QUE FOI DEVOLVIDO
        # NESTA MOVIMENTAÇÃO
        # -------------------------------------------------

        elif movimentacao.tipo == "RETORNO":

            quantidade_retirada = Decimal("0")

            quantidade_consumida = Decimal("0")

        # -------------------------------------------------
        # CONSUMO: MOSTRA SOMENTE O QUE FOI CONSUMIDO
        # NESTA MOVIMENTAÇÃO
        # -------------------------------------------------

        elif movimentacao.tipo == "CONSUMO":

            quantidade_retirada = Decimal("0")

            quantidade_retorno = Decimal("0")

        # -------------------------------------------------
        # ENTRADA: NÃO REPRESENTA RETIRADA
        # -------------------------------------------------

        elif movimentacao.tipo == "ENTRADA":

            quantidade_retirada = Decimal("0")

        itens_visualizacao.append({
            "item": item,
            "quantidade_recebida": quantidade_recebida,
            "quantidade_retirada": quantidade_retirada,
            "quantidade_retorno": quantidade_retorno,
            "quantidade_consumida": quantidade_consumida,
            "quantidade_pendente": quantidade_pendente
        })

        # -------------------------------------------------
        # HISTÓRICO DE MOVIMENTAÇÕES VINCULADAS
        # -------------------------------------------------
        
        movimentacoes_vinculadas = []
        
        if movimentacao.tipo == "SAIDA":
        
            movimentacoes_vinculadas = (
                Movimentacao.query
                .filter(
                    Movimentacao.movimentacao_origem_id == movimentacao.id,
                    Movimentacao.tipo.in_(["RETORNO", "CONSUMO"])
                )
                .order_by(
                    Movimentacao.data_movimentacao.asc(),
                    Movimentacao.id.asc()
                )
                .all()
            )

    return render_template(
        "movimentacoes/visualizar.html",
        movimentacao=movimentacao,
        itens_visualizacao=itens_visualizacao,
        movimentacoes_vinculadas=movimentacoes_vinculadas
    )

@movimentacoes_bp.route("/imprimir-os/<int:id>")
@admin_required
def imprimir_os(id):

    movimentacao = Movimentacao.query.get_or_404(id)

    if movimentacao.tipo not in ["SAIDA", "RETORNO", "CONSUMO"]:
        flash(
            "A impressão não está disponível para esta movimentação.",
            "warning"
        )
        return redirect(
            url_for("movimentacoes.visualizar", id=id)
        )

    itens_resumo = []
    movimentacoes_vinculadas = []

    if movimentacao.tipo == "SAIDA":

        for item in movimentacao.itens:

            totais = (
                db.session.query(
                    func.coalesce(
                        func.sum(MovimentacaoItem.quantidade_retorno), 0
                    ),
                    func.coalesce(
                        func.sum(MovimentacaoItem.quantidade_consumida), 0
                    )
                )
                .filter(
                    MovimentacaoItem.movimentacao_item_origem_id == item.id
                )
                .first()
            )

            retirado = Decimal(item.quantidade or 0)
            retornado = Decimal(totais[0] or 0)
            consumido = Decimal(totais[1] or 0)

            itens_resumo.append({
                "item": item,
                "retirado": retirado,
                "retornado": retornado,
                "consumido": consumido,
                "pendente": retirado - retornado - consumido
            })

        movimentacoes_vinculadas = (
            Movimentacao.query
            .filter(
                Movimentacao.movimentacao_origem_id == movimentacao.id,
                Movimentacao.tipo.in_(["RETORNO", "CONSUMO"])
            )
            .order_by(
                Movimentacao.data_movimentacao.asc(),
                Movimentacao.id.asc()
            )
            .all()
        )

    return render_template(
        "movimentacoes/imprimir_os.html",
        movimentacao=movimentacao,
        itens_resumo=itens_resumo,
        movimentacoes_vinculadas=movimentacoes_vinculadas
    )

@movimentacoes_bp.route("/imprimir-os-pdf/<int:id>")
@admin_required
def imprimir_os_pdf(id):

    movimentacao = Movimentacao.query.get_or_404(id)

    if movimentacao.tipo != "SAIDA":
        flash("Selecione uma OS original de saída.", "warning")
        return redirect(url_for("movimentacoes.visualizar", id=id))

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
        "TextoOSCatena",
        parent=estilos["Normal"],
        fontSize=8,
        leading=11
    )

    estilo_titulo = ParagraphStyle(
        "TituloOSCatena",
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

    def criar_tabela(cabecalho, linhas, larguras):
        dados = [[
            Paragraph(
                f"<b>{escape(str(coluna))}</b>",
                ParagraphStyle(
                    "CabecalhoTabelaOS",
                    parent=estilos["Normal"],
                    fontName="Helvetica-Bold",
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
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1),
             0.3, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))

        # Cabeçalho branco sobre fundo azul
        for celula in dados[0]:
            celula.style.textColor = colors.white

        return tabela

    # CABEÇALHO
    caminho_logo = os.path.join(
        current_app.static_folder,
        "img",
        "Catena logo.jpg"
    )

    titulo = Paragraph(
        "<b>CATENA ENGENHARIA</b><br/>"
        "ORDEM DE SERVIÇO — SAÍDA DE MATERIAIS",
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

    # DADOS DA OS
    veiculo = "-"
    if movimentacao.veiculo:
        v = movimentacao.veiculo
        veiculo = f"{v.marca} {v.modelo} - {v.placa}"

    dados_os = [
        ["Número da OS", movimentacao.numero_os or f"#{id}"],
        ["Data", movimentacao.data_movimentacao.strftime(
            "%d/%m/%Y %H:%M"
        )],
        ["Status", movimentacao.status],
        ["Colaborador",
         movimentacao.colaborador.nome
         if movimentacao.colaborador else "-"],
        ["Responsável pelo registro",
         movimentacao.usuario.nome
         if movimentacao.usuario else "-"],
        ["Veículo", veiculo],
        ["Destino", movimentacao.destino or "-"]
    ]

    tabela_dados = Table(
        [[texto(campo), texto(valor)] for campo, valor in dados_os],
        colWidths=[5 * cm, 13 * cm]
    )

    tabela_dados.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
    ]))

    elementos.append(tabela_dados)

    # MATERIAIS DE SAÍDA
    elementos.append(Paragraph("Materiais de saída", estilo_titulo))

    linhas_saida = []
    linhas_retorno = []

    for item in movimentacao.itens:
        retirado = Decimal(item.quantidade or 0)

        totais = db.session.query(
            func.coalesce(
                func.sum(MovimentacaoItem.quantidade_retorno), 0
            ),
            func.coalesce(
                func.sum(MovimentacaoItem.quantidade_consumida), 0
            )
        ).filter(
            MovimentacaoItem.movimentacao_item_origem_id == item.id
        ).first()

        retornado = Decimal(totais[0] or 0)

        linhas_saida.append([
            item.material.codigo,
            item.material.nome,
            item.material.unidade,
            f"{retirado:.3f}"
        ])

        if retornado > 0:
            linhas_retorno.append([
                item.material.codigo,
                item.material.nome,
                item.material.unidade,
                f"{retornado:.3f}"
            ])

    if not linhas_saida:
        linhas_saida.append(["-", "Nenhum material", "-", "-"])

    elementos.append(criar_tabela(
        ["Código", "Material", "Unidade", "Retirado"],
        linhas_saida,
        [3.5 * cm, 9 * cm, 2.5 * cm, 3 * cm]
    ))

    # HISTÓRICO
    elementos.append(Paragraph(
        "Histórico de retornos e consumos",
        estilo_titulo
    ))

    vinculadas = Movimentacao.query.filter(
        Movimentacao.movimentacao_origem_id == movimentacao.id,
        Movimentacao.tipo.in_(["RETORNO", "CONSUMO"])
    ).order_by(
        Movimentacao.data_movimentacao.asc(),
        Movimentacao.id.asc()
    ).all()

    linhas_historico = []

    for vinculada in vinculadas:
        for item in vinculada.itens:
            quantidade = (
                item.quantidade_retorno
                if vinculada.tipo == "RETORNO"
                else item.quantidade_consumida
            )

            linhas_historico.append([
                vinculada.numero_os or f"#{vinculada.id}",
                vinculada.data_movimentacao.strftime(
                    "%d/%m/%Y %H:%M"
                ),
                vinculada.tipo,
                item.material.nome,
                f"{Decimal(quantidade or 0):.3f}",
                item.material.unidade
            ])

    if not linhas_historico:
        linhas_historico.append([
            "-", "-", "-", "Nenhuma movimentação", "-", "-"
        ])

    elementos.append(criar_tabela(
        ["OS vinculada", "Data", "Tipo",
         "Material", "Quantidade", "Un."],
        linhas_historico,
        [3 * cm, 3.4 * cm, 2.1 * cm,
         5.2 * cm, 2.8 * cm, 1.5 * cm]
    ))

    # MATERIAIS EFETIVAMENTE RETORNADOS
    elementos.append(Paragraph(
        "Materiais retornados ao almoxarifado",
        estilo_titulo
    ))

    if not linhas_retorno:
        linhas_retorno.append([
            "-", "Nenhum material retornado", "-", "-"
        ])

    elementos.append(criar_tabela(
        ["Código", "Material", "Unidade", "Retornado"],
        linhas_retorno,
        [3.5 * cm, 9 * cm, 2.5 * cm, 3 * cm]
    ))

    # ASSINATURAS
    # Duas linhas independentes, com espaço entre elas
    estilo_assinatura = ParagraphStyle(
        "AssinaturaCentralizada",
        parent=estilo_texto,
        alignment=TA_CENTER
    )   

    assinatura_saida = Paragraph(
        "Responsável pela saída do material",
        estilo_assinatura
    )

    assinatura_retorno = Paragraph(
        "Responsável pelo retorno do material",
        estilo_assinatura
    )

    tabela_assinaturas = Table(
        [[assinatura_saida, "", assinatura_retorno]],
        colWidths=[8 * cm, 2 * cm, 8 * cm],
        hAlign="CENTER"
    )

    tabela_assinaturas.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (0, 0), 0.7, colors.black),
        ("LINEABOVE", (2, 0), (2, 0), 0.7, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER")
    ]))

    elementos.append(
        KeepTogether([
            Spacer(1, 1 * cm),
            tabela_assinaturas
        ])
    )

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
        f"OS_{movimentacao.numero_os or movimentacao.id}"
        .replace("/", "-")
        + ".pdf"
    )

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=nome_arquivo
    )
    