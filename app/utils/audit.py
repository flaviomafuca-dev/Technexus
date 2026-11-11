"""
app/utils/audit.py — Utilitário de registo de auditoria
"""

from datetime import datetime, timezone
from flask import request


def log_action(action, description, user_id=None, entity_type=None, 
               entity_id=None, reason=None, db_session=None):
    """
    Regista uma acção no histórico de auditoria.
    
    NOTA: Nunca inclui palavras-passe ou credenciais nos logs.
    
    Parâmetros:
        action: Tipo de acção (ex: 'create_sale', 'cancel_payment').
        description: Descrição legível da operação.
        user_id: ID do utilizador que realizou a acção.
        entity_type: Tipo do registo afectado (ex: 'Sale', 'Product').
        entity_id: ID do registo afectado.
        reason: Motivo (para cancelamentos ou ajustes).
        db_session: Sessão de BD a usar (ou None para usar a default).
    """
    try:
        from app.extensions import db
        from app.models.notification import AuditLog
        
        ip = None
        try:
            ip = request.remote_addr
        except RuntimeError:
            pass  # Fora do contexto de pedido (ex: scripts)
        
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            reason=reason,
            ip_address=ip,
            created_at=datetime.now(timezone.utc)
        )
        
        session = db_session or db.session
        session.add(log)
        # Não faz commit aqui — deixa o chamador gerir a transacção
        
    except Exception as e:
        # O log de auditoria não deve interromper a operação principal
        import logging
        logging.getLogger(__name__).error(f"Falha ao registar auditoria: {e}")


def log_login(user_id, success=True, reason=None):
    """Regista tentativa de login."""
    action = 'login_success' if success else 'login_failed'
    description = 'Login bem-sucedido' if success else f'Tentativa de login falhada: {reason}'
    log_action(action=action, description=description, user_id=user_id)


def log_logout(user_id):
    """Regista logout."""
    log_action(action='logout', description='Sessão terminada', user_id=user_id)
