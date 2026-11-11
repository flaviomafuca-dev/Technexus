"""
app/extensions.py — Inicialização das extensões Flask

Centraliza a criação e configuração de todas as extensões Flask.
As extensões são criadas aqui e inicializadas com a app em create_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ==========================================
# Instâncias das extensões (sem app ainda)
# ==========================================

# Base de dados — acesso via ORM SQLAlchemy
db = SQLAlchemy()

# Migrações de base de dados — Alembic via Flask-Migrate
migrate = Migrate()

# Gestão de sessões de utilizador
login_manager = LoginManager()

# Proteção CSRF para formulários
csrf = CSRFProtect()

# Limitador de pedidos — protege contra brute force e abuso
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)


def init_extensions(app):
    """
    Inicializa todas as extensões com a instância da aplicação.
    
    Parâmetros:
        app: Instância da aplicação Flask.
    """
    # Inicializa SQLAlchemy e Alembic
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Inicializa proteção CSRF
    csrf.init_app(app)
    
    # Inicializa o limitador de pedidos
    limiter.init_app(app)
    
    # Configura o Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sessão para aceder a esta página.'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = None if app.testing else 'strong'
    
    # Define como carregar um utilizador a partir do ID de sessão
    @login_manager.user_loader
    def load_user(user_id):
        """Carrega o utilizador da base de dados pelo ID."""
        from app.models.user import User
        try:
            return User.query.get(int(user_id))
        except (ValueError, Exception):
            return None
    
    # Handler para pedidos não autenticados a rotas protegidas por API
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify, redirect, url_for, flash
        
        # Se for um pedido AJAX/API, retorna JSON
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'erro': 'Não autenticado', 'codigo': 401}), 401
        
        # Caso contrário, redireciona para o login
        flash('Por favor, inicia sessão para aceder a esta página.', 'warning')
        return redirect(url_for('auth.login'))
