from . import db, bcrypt, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

class Loja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    cnpj = db.Column(db.String(18), unique=True, nullable=True)
    endereco = db.Column(db.String(255))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    usuarios = db.relationship('Usuario', backref='loja', lazy=True)
    produtos = db.relationship('Produto', backref='loja', lazy=True)
    def __repr__(self):
        return f'<Loja {self.nome}>'

class Setor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    produtos = db.relationship('Produto', backref='setor', lazy=True)
    usuarios = db.relationship('Usuario', backref='setor', lazy=True)
    def __repr__(self):
        return f'<Setor {self.nome}>'

class ProdutoCatalogo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(50), unique=True, nullable=False)
    nome_produto = db.Column(db.String(200), nullable=False)
    plu = db.Column(db.String(50))
    def __repr__(self):
        return f'<Catalogo {self.nome_produto}>'

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='auxiliar_gestao')
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=True)
    setor_id = db.Column(db.Integer, db.ForeignKey('setor.id'), nullable=True)
    produtos_criados = db.relationship('Produto', backref='criado_por', lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    # --- NOVA PROPRIEDADE PARA EXIBIR O NOME ---
    @property
    def nome_display(self):
        if '@' in self.username:
            return self.username.split('@')[0].capitalize()
        return self.username

    def __repr__(self):
        return f'<Usuario {self.username}>'

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_produto = db.Column(db.String(200), nullable=False)
    plu = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    validade = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Para Rebaixa')
    data_cadastro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    motivo_rebaixa = db.Column(db.String(255), nullable=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)
    setor_id = db.Column(db.Integer, db.ForeignKey('setor.id'), nullable=False)
    
    # --- NOVO CAMPO PARA GUARDAR O CRIADOR DO PRODUTO ---
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    def __repr__(self):
        return f'<Produto {self.nome_produto}>'