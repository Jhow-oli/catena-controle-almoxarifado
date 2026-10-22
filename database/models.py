from datetime import datetime
from zoneinfo import ZoneInfo

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash

from database.connection import db


class Usuario(UserMixin, db.Model):

    __tablename__ = "usuarios"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    colaborador_id = db.Column(
        db.Integer,
        db.ForeignKey("colaboradores.id"),
        nullable=True
    )

    colaborador = db.relationship(
        "Colaborador",
        backref="usuario",
        uselist=False
    )

    nome = db.Column(
        db.String(150),
        nullable=False
    )

    usuario = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=True
    )

    senha_hash = db.Column(
        db.String(255),
        nullable=False
    )

    perfil = db.Column(
        db.String(20),
        nullable=False,
        default="COLABORADOR"
    )

    ativo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    ultimo_acesso = db.Column(
        db.DateTime,
        nullable=True
    )

    def definir_senha(self, senha):

        self.senha_hash = generate_password_hash(
            senha
        )

    def verificar_senha(self, senha):

        from werkzeug.security import check_password_hash

        return check_password_hash(
            self.senha_hash,
            senha
        )


class Colaborador(db.Model):

    __tablename__ = "colaboradores"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(150),
        nullable=False
    )

    funcao = db.Column(
        db.String(100),
        nullable=False
    )

    categoria_cnh = db.Column(
        db.String(10),
        nullable=True
    )

    validade_cnh = db.Column(
        db.Date,
        nullable=True
    )

    ativo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )


class Material(db.Model):

    __tablename__ = "materiais"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    codigo = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    nome = db.Column(
        db.String(150),
        nullable=False
    )

    descricao = db.Column(
        db.Text,
        nullable=True
    )

    unidade = db.Column(
        db.String(20),
        nullable=False,
        default="UN"
    )

    quantidade = db.Column(
        db.Numeric(12, 3),
        nullable=False,
        default=0
    )

    estoque_minimo = db.Column(
        db.Numeric(12, 3),
        nullable=False,
        default=0
    )

    localizacao = db.Column(
        db.String(100),
        nullable=True
    )

    ativo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Veiculo(db.Model):

    __tablename__ = "veiculos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    marca = db.Column(
        db.String(80),
        nullable=False
    )

    modelo = db.Column(
        db.String(100),
        nullable=False
    )

    placa = db.Column(
        db.String(10),
        unique=True,
        nullable=False
    )

    ano = db.Column(
        db.Integer,
        nullable=True
    )

    tipo = db.Column(
        db.String(50),
        nullable=True
    )

    ativo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

def horario_brasilia():
    return datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).replace(tzinfo=None)

class Movimentacao(db.Model):

    __tablename__ = "movimentacoes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Número da Ordem de Serviço
    numero_os = db.Column(
            db.String(30),
            unique=True,
            nullable=True
        )

    movimentacao_origem_id = db.Column(
        db.Integer,
        db.ForeignKey("movimentacoes.id"),
        nullable=True
    )

    movimentacao_origem = db.relationship(
        "Movimentacao",
        remote_side="Movimentacao.id",
        backref="retornos"
    )

    tipo = db.Column(
        db.String(20),
        nullable=False
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False
    )

    colaborador_id = db.Column(
        db.Integer,
        db.ForeignKey("colaboradores.id"),
        nullable=True
    )

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey("veiculos.id"),
        nullable=True
    )

    data_movimentacao = db.Column(
        db.DateTime,
        default=horario_brasilia,
        nullable=False
    )

    destino = db.Column(
        db.String(150),
        nullable=True
    )

    observacoes = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(20),
        default="ABERTA",
        nullable=False
    )

    chave_idempotencia = db.Column(
        db.String(36),
        unique=True,
        nullable=True
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    usuario = db.relationship(
        "Usuario",
        backref="movimentacoes"
    )

    colaborador = db.relationship(
        "Colaborador",
        backref="movimentacoes"
    )

    veiculo = db.relationship(
        "Veiculo",
        backref="movimentacoes"
    )

    itens = db.relationship(
        "MovimentacaoItem",
        back_populates="movimentacao",
        cascade="all, delete-orphan"
    )


class MovimentacaoItem(db.Model):

    __tablename__ = "movimentacao_itens"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    movimentacao_id = db.Column(
        db.Integer,
        db.ForeignKey("movimentacoes.id"),
        nullable=False
    )

    movimentacao_item_origem_id = db.Column(
        db.Integer,
        db.ForeignKey("movimentacao_itens.id"),
        nullable=True
    )

    material_id = db.Column(
        db.Integer,
        db.ForeignKey("materiais.id"),
        nullable=False
    )

    quantidade = db.Column(
        db.Numeric(12, 3),
        nullable=False
    )

    quantidade_retorno = db.Column(
        db.Numeric(12, 3),
        default=0,
        nullable=False
    )

    quantidade_consumida = db.Column(
        db.Numeric(12, 3),
        default=0,
        nullable=False
    )

    observacoes = db.Column(
        db.String(255),
        nullable=True
    )

    item_origem = db.relationship(
        "MovimentacaoItem",
        remote_side="MovimentacaoItem.id",
        foreign_keys=[movimentacao_item_origem_id],
        backref="retornos"
    )

    material = db.relationship(
        "Material",
        backref="movimentacao_itens"
    )

    movimentacao = db.relationship(
        "Movimentacao",
        back_populates="itens"
    )

class SequenciaOS(db.Model):
    __tablename__ = "sequencias_os"

    data_os = db.Column(
        db.Date,
        primary_key=True
    )

    ultimo_numero = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )