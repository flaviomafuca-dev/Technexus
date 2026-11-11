"""
app/models/user.py — Modelo de Utilizador

Define a estrutura da tabela de utilizadores e as regras de autenticação.
Integra com Flask-Login para gestão de sessões.
"""

from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    """
    Modelo de utilizador do sistema TechNexus.
    
    Perfis disponíveis:
    - admin: Acesso total ao sistema
    - manager: Acesso operacional (sem dados financeiros confidenciais)
    """
    
    __tablename__ = 'users'
    
    # ==========================================
    # Campos principais
    # ==========================================
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Nome completo do utilizador
    full_name = db.Column(db.String(100), nullable=False)
    
    # Perfil: 'admin' ou 'manager'
    role = db.Column(db.String(20), nullable=False, default='manager')
    
    # Estado da conta
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # ==========================================
    # Segurança — controlo de tentativas de login
    # ==========================================
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    
    # ==========================================
    # Recuperação de senha
    # ==========================================
    reset_token = db.Column(db.String(100), nullable=True, unique=True)
    reset_token_expires = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # ==========================================
    # Preferências do utilizador
    # ==========================================
    # Idioma preferido (para futura internacionalização)
    language = db.Column(db.String(10), default='pt', nullable=False)
    
    # ==========================================
    # Auditoria
    # ==========================================
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # ==========================================
    # Relacionamentos
    # ==========================================
    # Vendas registadas por este utilizador
    sales = db.relationship('Sale', backref='registered_by_user', lazy='dynamic',
                            foreign_keys='Sale.registered_by')
    
    # Notificações do utilizador
    notifications = db.relationship('Notification', backref='user', lazy='dynamic',
                                    foreign_keys='Notification.user_id')
    
    # Histórico de auditoria
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic',
                                 foreign_keys='AuditLog.user_id')
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
    
    # ==========================================
    # Gestão de senha
    # ==========================================
    
    def set_password(self, password):
        """
        Cria o hash seguro da senha.
        NUNCA guarda a senha em texto simples.
        
        Parâmetros:
            password: Senha em texto simples.
        """
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256:600000')
    
    def check_password(self, password):
        """
        Verifica se a senha fornecida corresponde ao hash guardado.
        
        Parâmetros:
            password: Senha a verificar.
        
        Retorna:
            True se a senha estiver correcta, False caso contrário.
        """
        return check_password_hash(self.password_hash, password)
    
    # ==========================================
    # Controlo de bloqueio por tentativas falhadas
    # ==========================================
    
    def is_locked(self):
        """
        Verifica se a conta está bloqueada por excesso de tentativas de login.
        
        Retorna:
            True se a conta estiver bloqueada, False caso contrário.
        """
        if self.locked_until is None:
            return False
        now = datetime.now(timezone.utc)
        if self.locked_until.tzinfo is None:
            from datetime import timezone as tz
            locked = self.locked_until.replace(tzinfo=tz.utc)
        else:
            locked = self.locked_until
        return now < locked
    
    def increment_failed_login(self, max_attempts=5, lockout_minutes=15):
        """
        Regista uma tentativa de login falhada.
        Bloqueia a conta após exceder o número máximo de tentativas.
        
        Parâmetros:
            max_attempts: Número máximo de tentativas antes do bloqueio.
            lockout_minutes: Duração do bloqueio em minutos.
        """
        from datetime import timedelta
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
    
    def reset_failed_login(self):
        """Repõe o contador de tentativas falhadas após login bem-sucedido."""
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def record_login(self, ip_address=None):
        """
        Regista o login bem-sucedido.
        
        Parâmetros:
            ip_address: Endereço IP do utilizador.
        """
        self.last_login = datetime.now(timezone.utc)
        self.last_login_ip = ip_address
        self.reset_failed_login()
    
    # ==========================================
    # Permissões por perfil
    # ==========================================
    
    @property
    def is_admin(self):
        """Verifica se o utilizador é administrador."""
        return self.role == 'admin'
    
    @property
    def is_manager(self):
        """Verifica se o utilizador é gerente/vendedor."""
        return self.role == 'manager'
    
    def can_access_financial_reports(self):
        """Apenas administradores podem ver relatórios financeiros confidenciais."""
        return self.is_admin
    
    def can_manage_users(self):
        """Apenas administradores podem gerir utilizadores."""
        return self.is_admin
    
    def can_view_global_profit(self):
        """Apenas administradores podem ver o lucro global."""
        return self.is_admin
    
    def can_access_settings(self):
        """Apenas administradores podem aceder às configurações."""
        return self.is_admin
    
    def can_manage_backups(self):
        """Apenas administradores podem gerir backups."""
        return self.is_admin
    
    def can_view_expenses(self, confidential=False):
        """
        Verifica se o utilizador pode ver despesas.
        Despesas confidenciais requerem perfil de administrador.
        """
        if confidential:
            return self.is_admin
        return True  # Todos os utilizadores podem ver despesas não confidenciais
    
    # ==========================================
    # Serialização
    # ==========================================
    
    def to_dict(self, include_sensitive=False):
        """
        Serializa o utilizador para dicionário.
        Por defeito, não inclui dados sensíveis.
        
        Parâmetros:
            include_sensitive: Se True, inclui dados como IP e tentativas de login.
        """
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_sensitive:
            data.update({
                'failed_login_attempts': self.failed_login_attempts,
                'locked_until': self.locked_until.isoformat() if self.locked_until else None,
                'last_login_ip': self.last_login_ip,
            })
        
        return data
