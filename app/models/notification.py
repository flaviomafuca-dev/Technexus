"""
app/models/notification.py — Modelos de Notificação e Auditoria
"""

from datetime import datetime, timezone
from app.extensions import db


class Notification(db.Model):
    """
    Notificação interna do sistema.
    
    Tipos: 
    - stock_low: Stock abaixo do mínimo
    - stock_out: Stock esgotado
    - debt_overdue: Dívida vencida
    - payment_due: Pagamento próximo
    - service_overdue: Serviço atrasado
    - contract_expiring: Contrato a expirar
    - goal_at_risk: Meta em risco
    """
    
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    notification_type = db.Column(db.String(30), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Prioridade: 'low', 'medium', 'high', 'critical'
    priority = db.Column(db.String(10), nullable=False, default='medium')
    
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Link para o registo relacionado
    link_url = db.Column(db.String(250), nullable=True)
    
    # Referência ao registo relacionado (para evitar duplicados)
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Índice único para evitar notificações duplicadas
    __table_args__ = (
        db.Index('ix_notification_reference', 'user_id', 'reference_type', 'reference_id',
                 'notification_type'),
    )
    
    def __repr__(self):
        return f'<Notification {self.notification_type}: {self.title}>'
    
    def mark_as_read(self):
        """Marca a notificação como lida."""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)


class AuditLog(db.Model):
    """
    Registo de auditoria para operações importantes.
    
    Operações registadas:
    - login, logout
    - create_sale, cancel_sale
    - create_purchase, confirm_purchase
    - register_payment
    - update_price, update_stock
    - create_user, update_user_role
    - update_settings
    - cancel_movement
    """
    
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    # Tipo de operação
    action = db.Column(db.String(50), nullable=False, index=True)
    
    # Tipo e ID do registo afectado
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    
    # Descrição legível da operação
    description = db.Column(db.Text, nullable=False)
    
    # Motivo (para cancelamentos, ajustes, etc.)
    reason = db.Column(db.String(250), nullable=True)
    
    # IP do utilizador no momento da operação
    ip_address = db.Column(db.String(45), nullable=True)
    
    # NOTA: Nunca guardar palavras-passe ou credenciais aqui!
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action} by user_id={self.user_id}>'


class AppSettings(db.Model):
    """
    Configurações da aplicação guardadas na base de dados.
    
    NOTA: Credenciais e chaves secretas NUNCA devem ser guardadas aqui.
    Usam-se variáveis de ambiente para isso.
    """
    
    __tablename__ = 'app_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True, index=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(250), nullable=True)
    
    # Tipo do valor: 'string', 'integer', 'decimal', 'boolean', 'json'
    value_type = db.Column(db.String(20), nullable=False, default='string')
    
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    def __repr__(self):
        return f'<AppSettings {self.key}>'
    
    def get_typed_value(self):
        """Retorna o valor no tipo correcto."""
        if self.value is None:
            return None
        if self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'decimal':
            from decimal import Decimal
            return Decimal(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        return self.value


class AIConversation(db.Model):
    """Histórico de conversas com o assistente IA."""
    
    __tablename__ = 'ai_conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Sessão da conversa (agrupa mensagens relacionadas)
    session_id = db.Column(db.String(50), nullable=False, index=True)
    
    # 'user' ou 'assistant'
    role = db.Column(db.String(10), nullable=False)
    
    # NOTA: Não guardar dados sensíveis nas mensagens!
    message = db.Column(db.Text, nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    def __repr__(self):
        return f'<AIConversation {self.role}: {self.message[:50]}>'
