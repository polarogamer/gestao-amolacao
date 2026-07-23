"""
Gestão Amolação - ponto de entrada da aplicação Flask.
Estrutura organizada em blueprints (um arquivo por área do sistema, dentro de routes/).
Banco: PostgreSQL via Supabase (ver db.py). Configuração por variáveis de ambiente (ver .env.example).
"""
import os
from flask import Flask

from db import init_db
from routes import (
    auth_routes,
    dashboard_routes,
    entrada_routes,
    saida_routes,
    relatorio_routes,
    caixa_routes,
    clientes_routes,
    estoque_routes,
    consumiveis_routes,
    mensagens_routes,
    ferramentas_routes,
)


def create_app():
    app = Flask(__name__)

    # NUNCA deixe a secret_key fixa no código em produção.
    app.secret_key = os.environ.get('SECRET_KEY')
    if not app.secret_key:
        raise RuntimeError(
            "SECRET_KEY não configurada. Defina uma variável de ambiente SECRET_KEY "
            "(pode gerar uma com: python -c \"import secrets; print(secrets.token_hex(32))\")."
        )

    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(dashboard_routes.bp)
    app.register_blueprint(entrada_routes.bp)
    app.register_blueprint(saida_routes.bp)
    app.register_blueprint(relatorio_routes.bp)
    app.register_blueprint(caixa_routes.bp)
    app.register_blueprint(clientes_routes.bp)
    app.register_blueprint(estoque_routes.bp)
    app.register_blueprint(consumiveis_routes.bp)
    app.register_blueprint(mensagens_routes.bp)
    app.register_blueprint(ferramentas_routes.bp)

    @app.cli.command('init-db')
    def init_db_command():
        """Comando `flask init-db` - cria as tabelas no Supabase e insere dados iniciais."""
        init_db()
        print('Banco de dados inicializado com sucesso.')

    return app


app = create_app()

if __name__ == '__main__':
    # Uso local apenas. Em produção (Vercel) quem serve a aplicação é api/index.py.
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
