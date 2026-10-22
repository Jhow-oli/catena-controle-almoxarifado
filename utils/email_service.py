import smtplib
import ssl

from email.message import EmailMessage

from flask import current_app


def enviar_email(destinatario, assunto, corpo):

    config = current_app.config

    mensagem = EmailMessage()

    mensagem["From"] = config["MAIL_DEFAULT_SENDER"]
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto

    mensagem.set_content(corpo)

    contexto_ssl = ssl.create_default_context()

    with smtplib.SMTP(
        config["MAIL_SERVER"],
        config["MAIL_PORT"],
        timeout=20
    ) as servidor:

        servidor.ehlo()

        # Exigir conexão criptografada
        servidor.starttls(context=contexto_ssl)

        servidor.ehlo()

        servidor.login(
            config["MAIL_USERNAME"],
            config["MAIL_PASSWORD"]
        )

        servidor.send_message(mensagem)

    return True