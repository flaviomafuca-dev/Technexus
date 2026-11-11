"""
app/__init__.py — Fábrica da aplicação Flask (Application Factory Pattern)

Este módulo cria e configura a instância da aplicação Flask.
Utiliza o padrão Application Factory para facilitar os testes
e suportar múltiplas configurações.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do ficheiro .env
load_dotenv()


def create_app(config_class=None):
    """
    Cria e configura a instância da aplicação Flask.
    
    Parâmetros:
        config_class: Classe de configuração a usar. Se None, 
                      usa a configuração baseada em FLASK_ENV.
    
    Retorna:
        app: Instância configurada da aplicação Flask.
    """
    # Cria a aplicação Flask com a pasta de templates e static
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    # ==========================================
    # Carregar configuração
    # ==========================================
    if config_class is None:
        from config import get_config
        config_class = get_config()
    elif isinstance(config_class, str):
        from config import config_map, get_config
        config_class = config_map.get(config_class.lower(), get_config())
    
    app.config.from_object(config_class)
    
    # Garante que a pasta de uploads existe
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'app/static/uploads'), exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # ==========================================
    # Inicializar extensões
    # ==========================================
    from app.extensions import init_extensions
    init_extensions(app)
    
    # ==========================================
    # Registar blueprints (rotas)
    # ==========================================
    register_blueprints(app)
    
    # ==========================================
    # Registar handlers de erro
    # ==========================================
    register_error_handlers(app)
    
    # ==========================================
    # Registar filtros Jinja2
    # ==========================================
    register_template_filters(app)
    
    # ==========================================
    # Registar processadores de contexto
    # ==========================================
    register_context_processors(app)
    
    # ==========================================
    # Configurar logs
    # ==========================================
    setup_logging(app)
    
    app.logger.info(f"TechNexus iniciado — Ambiente: {os.environ.get('FLASK_ENV', 'development')}")
    
    return app


def register_blueprints(app):
    """Regista todos os blueprints (módulos de rotas) da aplicação."""
    
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.customers import customers_bp
    from app.routes.suppliers import suppliers_bp
    from app.routes.products import products_bp
    from app.routes.inventory import inventory_bp
    from app.routes.sales import sales_bp
    from app.routes.purchases import purchases_bp
    from app.routes.services import services_bp
    from app.routes.service_orders import service_orders_bp
    from app.routes.finance import finance_bp
    from app.routes.expenses import expenses_bp
    from app.routes.cashflow import cashflow_bp
    from app.routes.reports import reports_bp
    from app.routes.contracts import contracts_bp
    from app.routes.employees import employees_bp
    from app.routes.ai_assistant import ai_bp
    from app.routes.settings import settings_bp
    from app.routes.users import users_bp
    
    # Regista cada blueprint com o seu prefixo de URL
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(customers_bp, url_prefix='/clientes')
    app.register_blueprint(suppliers_bp, url_prefix='/fornecedores')
    app.register_blueprint(products_bp, url_prefix='/produtos')
    app.register_blueprint(inventory_bp, url_prefix='/stock')
    app.register_blueprint(sales_bp, url_prefix='/vendas')
    app.register_blueprint(purchases_bp, url_prefix='/compras')
    app.register_blueprint(services_bp, url_prefix='/servicos')
    app.register_blueprint(service_orders_bp, url_prefix='/ordens-servico')
    app.register_blueprint(finance_bp, url_prefix='/financas')
    app.register_blueprint(expenses_bp, url_prefix='/despesas')
    app.register_blueprint(cashflow_bp, url_prefix='/caixa')
    app.register_blueprint(reports_bp, url_prefix='/relatorios')
    app.register_blueprint(contracts_bp, url_prefix='/contratos')
    app.register_blueprint(employees_bp, url_prefix='/funcionarios')
    app.register_blueprint(ai_bp, url_prefix='/assistente')
    app.register_blueprint(settings_bp, url_prefix='/configuracoes')
    app.register_blueprint(users_bp, url_prefix='/utilizadores')


def register_error_handlers(app):
    """Regista handlers para erros HTTP comuns."""
    
    from flask import render_template, request, jsonify
    
    def is_api_request():
        """Verifica se o pedido é uma chamada API (espera JSON)."""
        return request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json'
    
    @app.errorhandler(400)
    def bad_request(e):
        if is_api_request():
            return jsonify({'erro': 'Pedido inválido', 'codigo': 400}), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        if is_api_request():
            return jsonify({'erro': 'Não autenticado', 'codigo': 401}), 401
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(e):
        if is_api_request():
            return jsonify({'erro': 'Acesso negado', 'codigo': 403}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(e):
        if is_api_request():
            return jsonify({'erro': 'Página não encontrada', 'codigo': 404}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(429)
    def too_many_requests(e):
        if is_api_request():
            return jsonify({'erro': 'Demasiados pedidos. Aguarda um momento.', 'codigo': 429}), 429
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_error(e):
        # Regista o erro sem expor detalhes ao utilizador
        app.logger.error(f'Erro interno do servidor: {e}', exc_info=True)
        if is_api_request():
            return jsonify({'erro': 'Erro interno do servidor', 'codigo': 500}), 500
        return render_template('errors/500.html'), 500


def register_template_filters(app):
    """Regista filtros personalizados para os templates Jinja2."""
    
    from app.utils.formatting import (
        format_currency, format_date, format_datetime,
        format_percentage, format_number
    )
    
    # Filtro para formatar valores monetários em MZN
    @app.template_filter('moeda')
    def moeda_filter(value):
        return format_currency(value)
    
    # Filtro para formatar datas no formato pt-MZ
    @app.template_filter('data')
    def data_filter(value):
        return format_date(value)
    
    # Filtro para formatar datas e horas
    @app.template_filter('data_hora')
    def data_hora_filter(value):
        return format_datetime(value)
    
    # Filtro para formatar percentagens
    @app.template_filter('percentagem')
    def percentagem_filter(value, casas=1):
        return format_percentage(value, casas)
    
    # Filtro para formatar números
    @app.template_filter('numero')
    def numero_filter(value, casas=2):
        return format_number(value, casas)
    
    # Filtro para truncar texto
    @app.template_filter('truncar')
    def truncar_filter(value, length=50):
        if value and len(str(value)) > length:
            return str(value)[:length] + '...'
        return value or ''


def register_context_processors(app):
    """Regista processadores de contexto globais para os templates."""
    
    @app.context_processor
    def inject_globals():
        """Injeta variáveis globais disponíveis em todos os templates."""
        from flask_login import current_user
        from app.services.notification_service import get_unread_count
        
        unread_notifications = 0
        if current_user and current_user.is_authenticated:
            try:
                unread_notifications = get_unread_count(current_user.id)
            except Exception:
                pass
        
        return {
            'APP_NAME': app.config.get('APP_NAME', 'TechNexus'),
            'APP_CURRENCY': app.config.get('APP_CURRENCY', 'MZN'),
            'APP_CURRENCY_SYMBOL': app.config.get('APP_CURRENCY_SYMBOL', 'MT'),
            'unread_notifications': unread_notifications,
        }


def setup_logging(app):
    """Configura o sistema de logs da aplicação."""
    
    if not app.debug and not app.testing:
        # Em produção, grava logs em ficheiro com rotação
        log_file = app.config.get('LOG_FILE', 'logs/technexus.log')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10_000_000,  # 10 MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)s em %(module)s: %(message)s'
        ))
        
        log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
        file_handler.setLevel(log_level)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(log_level)
