import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(app.instance_path, "database.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Importa e registra os Blueprints (nossos conjuntos de rotas)
    from .routes import routes
    from .auth import auth_bp
    
    app.register_blueprint(routes)
    app.register_blueprint(auth_bp)

    # Adiciona comandos customizados para inicializar o sistema
    @app.cli.command("init-db")
    def init_db_command():
        """Cria as tabelas e povoa os dados iniciais."""
        from .models import Setor, Loja
        
        db.create_all()
        
        # Povoar setores
        setores_iniciais = ['Padaria', 'Açougue', 'Frios', 'Mercearia']
        for nome_setor in setores_iniciais:
            if not Setor.query.filter_by(nome=nome_setor).first():
                setor = Setor(nome=nome_setor)
                db.session.add(setor)
        
        # Povoar uma loja padrão
        if not Loja.query.filter_by(nome='Loja Matriz').first():
            loja_matriz = Loja(nome='Loja Matriz', cidade='Sua Cidade', estado='UF')
            db.session.add(loja_matriz)
            
        db.session.commit()
        print("Banco de dados inicializado e dados padrão criados com sucesso.")


    @app.cli.command("create-general-manager")
    def create_manager():
        """Cria o usuário gerente geral inicial."""
        from .models import Usuario
        
        username = input("Digite o e-mail do Gerente Geral: ")
        password = input("Digite a senha do Gerente Geral: ")
        
        if Usuario.query.filter_by(username=username).first():
            print(f"Usuário '{username}' já existe.")
            return

        # O gerente geral não pertence a uma loja específica
        manager = Usuario(username=username, role='gerente_geral', loja_id=None)
        manager.set_password(password)
        db.session.add(manager)
        db.session.commit()
        print(f"Usuário Gerente Geral '{username}' criado com sucesso!")

    return app