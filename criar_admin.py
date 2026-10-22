from getpass import getpass

from app import app
from database.connection import db
from database.models import Usuario


with app.app_context():

    usuario_existente = Usuario.query.filter_by(
        usuario="admin"
    ).first()

    if usuario_existente:
        print("O usuário admin já existe.")

    else:
        senha = getpass("Digite a senha do administrador: ")
        confirmar_senha = getpass("Confirme a senha: ")

        if not senha or len(senha) < 12:
            raise ValueError(
                "A senha deve ter pelo menos 12 caracteres."
            )

        if senha != confirmar_senha:
            raise ValueError(
                "As senhas informadas não coincidem."
            )

        admin = Usuario(
            nome="Administrador",
            usuario="admin",
            perfil="ADMIN",
            ativo=True
        )

        admin.definir_senha(senha)

        db.session.add(admin)
        db.session.commit()

        print("Administrador criado com sucesso!")