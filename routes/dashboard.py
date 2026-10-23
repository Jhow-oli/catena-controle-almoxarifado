from flask import Blueprint, render_template 
from flask_login import login_required 

from database.models import Material, Movimentacao 
from utils.decorators import admin_required 

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_

dashboard_bp = Blueprint( 
    "dashboard", 
    __name__, 
    url_prefix="/dashboard" 
) 


@dashboard_bp.route("/")
@login_required
def index():

    # DATA ATUAL - HORÁRIO DE BRASÍLIA
    hoje = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).date()

    limite_calibracao = hoje + timedelta(days=30)

    # 1. TOTAL DE MATERIAIS ATIVOS
    total_materiais = Material.query.filter_by(
        ativo=True
    ).count()

    # 2. MATERIAIS COM ESTOQUE BAIXO
    estoque_baixo = Material.query.filter(
        Material.ativo.is_(True),
        Material.estoque_minimo > 0,
        Material.quantidade <= Material.estoque_minimo
    ).count()

    # 3. EQUIPAMENTOS COM CALIBRAÇÃO PRÓXIMA
    calibracoes_proximas = Material.query.filter(
        Material.ativo.is_(True),
        Material.requer_calibracao.is_(True),
        Material.validade_calibracao >= hoje,
        Material.validade_calibracao <= limite_calibracao
    ).count()

    # 4. EQUIPAMENTOS COM CALIBRAÇÃO VENCIDA
    calibracoes_vencidas = Material.query.filter(
        Material.ativo.is_(True),
        Material.requer_calibracao.is_(True),
        Material.validade_calibracao < hoje
    ).count()

    # 5. SAÍDAS AINDA ABERTAS
    em_movimentacao = Movimentacao.query.filter_by(
        tipo="SAIDA",
        status="ABERTA"
    ).count()

    # EQUIPAMENTOS QUE EXIGEM ATENÇÃO NA CALIBRAÇÃO

    alertas_calibracao = Material.query.filter(
        Material.ativo.is_(True),
        Material.requer_calibracao.is_(True),
        or_(
            Material.validade_calibracao.is_(None),
            Material.validade_calibracao <= limite_calibracao
        )
    ).order_by(
        Material.validade_calibracao.asc()
    ).all()

    # ORGANIZAR OS ALERTAS POR PRIORIDADE

    def prioridade_calibracao(material):

        if material.validade_calibracao is None:
            return (0, hoje)

        if material.validade_calibracao < hoje:
            return (1, material.validade_calibracao)

        return (2, material.validade_calibracao)


    alertas_calibracao.sort(key=prioridade_calibracao)


    return render_template(
        "dashboard.html",
        total_materiais=total_materiais,
        estoque_baixo=estoque_baixo,
        calibracoes_proximas=calibracoes_proximas,
        calibracoes_vencidas=calibracoes_vencidas,
        em_movimentacao=em_movimentacao,
        alertas_calibracao=alertas_calibracao,
        hoje=hoje,
        limite_calibracao=limite_calibracao
    ) 


@dashboard_bp.route("/teste-admin") 
@admin_required 
def teste_admin(): 
    
        return """ 
            <h1>Área administrativa</h1> 
            <p>Se você está vendo esta página, a proteção ADMIN funcionou.</p> 
            <a href="/dashboard/">Voltar</>
        """