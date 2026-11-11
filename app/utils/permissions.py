"""
app/utils/permissions.py — Utilitários de Controlo de Permissões

Decoradores e funções para verificar permissões de utilizador.
AS VERIFICAÇÕES SÃO SEMPRE FEITAS NO SERVIDOR — nunca apenas no frontend.
"""

from functools import wraps
from flask import abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user


def admin_required(f):
    """
    Decorador que requer perfil de administrador.
    
    Uso:
        @app.route('/admin/...')
        @login_required
        @admin_required
        def admin_view():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin:
            # Regista tentativa de acesso não autorizado
            from app.utils.audit import log_action
            log_action(
                action='unauthorized_access',
                description=f'Tentativa de acesso a área restrita: {request.path}',
                user_id=current_user.id
            )
            
            # Responde conforme o tipo de pedido
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'erro': 'Acesso negado. Requer perfil de administrador.'}), 403
            
            flash('Não tens permissão para aceder a esta área.', 'danger')
            return abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def manager_or_admin_required(f):
    """
    Decorador que permite acesso a gerentes e administradores.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not (current_user.is_admin or current_user.is_manager):
            if request.is_json:
                return jsonify({'erro': 'Acesso negado.'}), 403
            flash('Não tens permissão para aceder a esta área.', 'danger')
            return abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def financial_reports_required(f):
    """
    Decorador para relatórios financeiros confidenciais.
    Apenas administradores têm acesso.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.can_access_financial_reports():
            if request.is_json:
                return jsonify({'erro': 'Acesso restrito a administradores.'}), 403
            flash('Os relatórios financeiros são apenas acessíveis a administradores.', 'danger')
            return abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def check_permission(permission_func, *args, **kwargs):
    """
    Verifica uma permissão de forma programática (sem decorador).
    
    Parâmetros:
        permission_func: Função do modelo User que retorna True/False.
    
    Retorna:
        True se autorizado, False caso contrário.
    """
    if not current_user.is_authenticated:
        return False
    
    return getattr(current_user, permission_func)(*args, **kwargs) if callable(
        getattr(current_user, permission_func, None)
    ) else bool(getattr(current_user, permission_func, False))


def get_permission_context():
    """
    Retorna um dicionário com as permissões do utilizador actual.
    Útil para injectar nos templates.
    """
    if not current_user.is_authenticated:
        return {}
    
    return {
        'can_admin': current_user.is_admin,
        'can_view_profit': current_user.can_view_global_profit(),
        'can_manage_users': current_user.can_manage_users(),
        'can_access_financial': current_user.can_access_financial_reports(),
        'can_access_settings': current_user.can_access_settings(),
        'can_manage_backups': current_user.can_manage_backups(),
    }
