"""
config.py — Configurações centrais do TechNexus

Define as configurações para diferentes ambientes:
- Development: desenvolvimento local
- Testing: testes automatizados
- Production: ambiente de produção

As configurações sensíveis são carregadas de variáveis de ambiente.
NUNCA coloca credenciais directamente neste ficheiro.
"""

import os
from datetime import timedelta


def get_database_url(default_sqlite=True):
    """
    Obtém o URL da base de dados das variáveis de ambiente.
    Corrige o prefixo 'postgres://' para 'postgresql://' 
    necessário para SQLAlchemy 2.x.
    """
    url = os.environ.get('DATABASE_URL', '').strip()
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    is_dummy = any(d in url for d in ['usuario:palavra_passe', 'user:password', '@host:5432'])
    if (not url or is_dummy) and default_sqlite:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'technexus_dev.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return f'sqlite:///{db_path}'
    return url


def get_engine_options(url):
    """Retorna as opções adequadas de engine para SQLite ou PostgreSQL."""
    if url and url.startswith('sqlite'):
        return {
            'connect_args': {'check_same_thread': False}
        }
    return {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 5)),
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 30)),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 1800)),
        'pool_pre_ping': True,
        'connect_args': {
            'options': '-c timezone=UTC'
        }
    }


class Config:
    """Configuração base — partilhada por todos os ambientes."""
    
    # ==========================================
    # Segurança
    # ==========================================
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-temporaria-substitui-em-producao'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora
    
    # ==========================================
    # Base de dados
    # ==========================================
    _default_url = get_database_url(default_sqlite=True)
    SQLALCHEMY_DATABASE_URI = _default_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options(_default_url)
    
    # ==========================================
    # Sessões e autenticação
    # ==========================================
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 86400))
    )
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    
    # ==========================================
    # Limite de tentativas de login (Flask-Limiter)
    # ==========================================
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', 5))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get('LOGIN_LOCKOUT_MINUTES', 15))
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # ==========================================
    # Uploads de ficheiros
    # ==========================================
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_SIZE_MB', 10)) * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = set(
        os.environ.get('ALLOWED_UPLOAD_EXTENSIONS', 'pdf,jpg,jpeg,png,xlsx,csv').split(',')
    )
    
    # ==========================================
    # Aplicação — Informações gerais
    # ==========================================
    APP_NAME = os.environ.get('APP_NAME', 'TechNexus')
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')
    APP_CURRENCY = os.environ.get('APP_CURRENCY', 'MZN')
    APP_CURRENCY_SYMBOL = os.environ.get('APP_CURRENCY_SYMBOL', 'MT')
    APP_LOCALE = os.environ.get('APP_LOCALE', 'pt_MZ')
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Africa/Maputo')
    
    # ==========================================
    # Google Gemini AI
    # ==========================================
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
    GEMINI_MAX_TOKENS = int(os.environ.get('GEMINI_MAX_TOKENS', 2048))
    GEMINI_TEMPERATURE = float(os.environ.get('GEMINI_TEMPERATURE', 0.3))
    GEMINI_ENABLED = os.environ.get('GEMINI_ENABLED', 'true').lower() == 'true'
    GEMINI_DAILY_LIMIT = int(os.environ.get('GEMINI_DAILY_LIMIT', 100))
    
    # ==========================================
    # E-mail (opcional — para recuperação de senha)
    # ==========================================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@technexus.co.mz')
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'false').lower() == 'true'
    
    # ==========================================
    # Backups
    # ==========================================
    BACKUP_DIR = os.environ.get('BACKUP_DIR', 'backups')
    BACKUP_RETENTION_DAYS = int(os.environ.get('BACKUP_RETENTION_DAYS', 30))
    
    # ==========================================
    # Logs
    # ==========================================
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/technexus.log')
    
    # ==========================================
    # Alertas (dias de antecedência)
    # ==========================================
    ALERT_DAYS_BEFORE_DUE = int(os.environ.get('ALERT_DAYS_BEFORE_DUE', 7))
    ALERT_DAYS_BEFORE_CONTRACT_END = int(os.environ.get('ALERT_DAYS_BEFORE_CONTRACT_END', 30))


class DevelopmentConfig(Config):
    """Configuração para ambiente de desenvolvimento."""
    
    DEBUG = True
    TESTING = False
    PROPAGATE_EXCEPTIONS = True
    _dev_url = get_database_url(default_sqlite=True)
    SQLALCHEMY_DATABASE_URI = _dev_url
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options(_dev_url)
    SQLALCHEMY_ECHO = False


class TestingConfig(Config):
    """Configuração para testes automatizados."""
    
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False}
    }
    
    GEMINI_ENABLED = False
    MAIL_ENABLED = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_COOKIE_SECURE = False
    MAX_LOGIN_ATTEMPTS = 100
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Configuração para ambiente de produção."""
    
    DEBUG = False
    TESTING = False
    _prod_url = get_database_url(default_sqlite=False)
    SQLALCHEMY_DATABASE_URI = _prod_url
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options(_prod_url) if _prod_url else {}
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """
    Retorna a classe de configuração adequada ao ambiente actual.
    Usa a variável FLASK_ENV para determinar o ambiente.
    """
    env = os.environ.get('FLASK_ENV', 'development').lower()
    return config_map.get(env, DevelopmentConfig)
