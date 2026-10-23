from flask import Blueprint, render_template
from flask_login import login_required

from database.models import ListaModelo

listas_bp = Blueprint(
    "listas",
    __name__,
    url_prefix="/listas"
)


@listas_bp.route("/")
@login_required
def index():

    listas = (
        ListaModelo.query
        .order_by(ListaModelo.id.desc())
        .all()
    )

    return render_template(
        "listas/index.html",
        listas=listas
    )