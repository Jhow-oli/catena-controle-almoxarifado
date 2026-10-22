from flask import Flask, flash, render_template, current_app, redirect, url_for
from flask_limiter.errors import RateLimitExceeded

from config import Config
from database.connection import db

from flask_login import LoginManager

from extensions import limiter, csrf


login_manager = LoginManager()


def create_app():

    app = Flask(__name__)

    limiter.init_app(app)

    app.config["WTF_CSRF_CHECK_DEFAULT"] = False

    csrf.init_app(app)

    @app.errorhandler(RateLimitExceeded)
    def limite_excedido(e):

        flash(
            "Você atingiu o limite de solicitações. "
            "Aguarde 15 minutos antes de tentar novamente.",
            "warning"
        )

        resposta = redirect(
            url_for("auth.esqueci_senha"),
            code=303
        )

        resposta.headers["Retry-After"] = "900"

        return resposta

    app.config.from_object(Config)

    db.init_app(app)

    login_manager.init_app(app)

    login_manager.login_view = "auth.login"

    from database.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):

        return db.session.get(
            Usuario,
            int(user_id)
        )

    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.materiais import materiais_bp
    from routes.veiculos import veiculos_bp
    from routes.colaboradores import colaboradores_bp
    from routes.usuarios import usuarios_bp
    from routes.movimentacoes import movimentacoes_bp
    from routes.relatorios import relatorios_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(materiais_bp)
    app.register_blueprint(veiculos_bp)
    app.register_blueprint(colaboradores_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(movimentacoes_bp)
    app.register_blueprint(relatorios_bp)

    with app.app_context():

        db.create_all()

    @app.errorhandler(403)
    def acesso_negado(error):

        return render_template(
            "403.html"
        ), 403

    return app


app = create_app()


if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )