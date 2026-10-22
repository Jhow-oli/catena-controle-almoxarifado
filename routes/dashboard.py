from flask import Blueprint, render_template 
from flask_login import login_required 

from database.models import Material, Movimentacao 
from utils.decorators import admin_required 

dashboard_bp = Blueprint( 
    "dashboard", 
    __name__, 
    url_prefix="/dashboard" 
) 


@dashboard_bp.route("/") 
@login_required 
def index(): 
    # Total de materiais cadastrados e ativos 
    total_materiais = Material.query.filter_by( 
        ativo=True 
    ).count() 
    
    # Total de movimentações do tipo RETORNO 
    total_retornos = Movimentacao.query.filter_by(
        tipo="RETORNO" 
    ).count() 
    
    # Total de movimentações do tipo SAIDA 
    total_saidas = Movimentacao.query.filter_by( 
        tipo="SAIDA" 
    ).count() 

    # Saídas que ainda estão abertas 
    em_movimentacao = Movimentacao.query.filter_by( 
        tipo="SAIDA", 
        status="ABERTA" 
    ).count() 
    
    return render_template( 
        "dashboard.html", 
        total_materiais=total_materiais, 
        total_retornos=total_retornos, 
        total_saidas=total_saidas, 
        em_movimentacao=em_movimentacao 
    ) 


@dashboard_bp.route("/teste-admin") 
@admin_required 
def teste_admin(): 
    
        return """ 
            <h1>Área administrativa</h1> 
            <p>Se você está vendo esta página, a proteção ADMIN funcionou.</p> 
            <a href="/dashboard/">Voltar</>
        """