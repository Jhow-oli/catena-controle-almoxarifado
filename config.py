import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://"
        f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}"
        f"/{os.getenv('DB_NAME')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BASE_URL = os.getenv(
        "BASE_URL",
        "http://127.0.0.1:5000"
    )

    # E-MAIL CORPORATIVO - CATENA ENGENHARIA

    MAIL_SERVER = os.getenv(
        "MAIL_SERVER",
        "smtp.dialhost.com.br"
    )

    MAIL_PORT = int(
        os.getenv("MAIL_PORT", "587")
    )

    MAIL_USE_TLS = (
        os.getenv("MAIL_USE_TLS", "True").lower()
        == "true"
    )

    MAIL_USERNAME = os.getenv("MAIL_USERNAME")

    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

    MAIL_DEFAULT_SENDER = os.getenv(
        "MAIL_DEFAULT_SENDER",
        "almoxarifado@catena.eng.br"
    )