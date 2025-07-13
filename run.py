from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Descomente a linha abaixo na primeira vez que executar
        # para criar todas as tabelas do banco de dados.
        # db.create_all() 
        pass
    app.run(debug=True)