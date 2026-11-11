"""
app/routes/auth.py — Autenticação e Gestão de Sessões

Funcionalidades:
- Início e encerramento de sessão seguro.
- Proteção contra ataques de força bruta (bloqueio temporário por tentativas falhadas).
- Registo de auditoria de logins e logouts.
- Alteração segura de palavra-passe.
- Criação inicial protegida do primeiro administrador (fechada definitivamente após uso).
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, limiter
from app.models.user import User
from app.utils.audit import log_login, log_logout, log_action

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def login():
    """Início de sessão no sistema."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # Se ainda não existir nenhum utilizador no sistema, encaminha para setup inicial
    if User.query.count() == 0:
        return redirect(url_for('auth.setup_first_admin'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user:
            log_login(user_id=None, success=False, reason=f"Utilizador '{username}' inexistente")
            flash("Nome de utilizador ou palavra-passe incorretos.", "danger")
            return render_template('auth/login.html')

        if not user.is_active:
            flash("Esta conta de utilizador encontra-se desativada. Contacte a administração.", "warning")
            return render_template('auth/login.html')

        if user.is_locked():
            flash("Conta temporariamente bloqueada devido a tentativas falhadas consecutivas. Aguarda alguns minutos.", "danger")
            return render_template('auth/login.html')

        if not user.check_password(password):
            user.increment_failed_login(max_attempts=5, lockout_minutes=15)
            db.session.commit()
            log_login(user_id=user.id, success=False, reason="Palavra-passe errada")
            flash("Nome de utilizador ou palavra-passe incorretos.", "danger")
            return render_template('auth/login.html')

        # Sucesso no login
        user.record_login(ip_address=request.remote_addr)
        db.session.commit()
        login_user(user, remember=remember)
        log_login(user_id=user.id, success=True)

        flash(f"Bem-vindo de volta, {user.full_name}!", "success")
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Encerra a sessão do utilizador."""
    user_id = current_user.id
    logout_user()
    log_logout(user_id)
    flash("Sessão terminada com sucesso.", "info")
    return redirect(url_for('auth.login'))


@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def profile():
    """Permite ao utilizador consultar o seu perfil e alterar a palavra-passe."""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash("A palavra-passe atual indicada está incorreta.", "danger")
            return redirect(url_for('auth.profile'))

        if len(new_password) < 6:
            flash("A nova palavra-passe deve ter pelo menos 6 caracteres.", "warning")
            return redirect(url_for('auth.profile'))

        if new_password != confirm_password:
            flash("A confirmação da palavra-passe não coincide.", "warning")
            return redirect(url_for('auth.profile'))

        current_user.set_password(new_password)
        db.session.commit()

        log_action(
            action="change_password",
            description=f"Utilizador '{current_user.username}' alterou a sua palavra-passe com sucesso.",
            user_id=current_user.id,
            entity_type="User",
            entity_id=current_user.id
        )

        flash("Palavra-passe atualizada com sucesso!", "success")
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')


@auth_bp.route('/setup-admin', methods=['GET', 'POST'])
def setup_first_admin():
    """
    Criação inicial e única do primeiro Administrador do TechNexus.
    Esta rota fica permanentemente fechada assim que existir pelo menos um utilizador no sistema.
    """
    if User.query.count() > 0:
        flash("O sistema já se encontra configurado.", "info")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not full_name or not username or not email or not password:
            flash("Todos os campos são de preenchimento obrigatório.", "warning")
            return render_template('auth/setup_admin.html')

        if len(password) < 6:
            flash("A palavra-passe deve conter pelo menos 6 caracteres.", "warning")
            return render_template('auth/setup_admin.html')

        if password != confirm:
            flash("As palavras-passe indicadas não coincidem.", "warning")
            return render_template('auth/setup_admin.html')

        admin = User(
            full_name=full_name,
            username=username,
            email=email,
            role='admin',
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        log_action(
            action="setup_initial_admin",
            description=f"Primeiro Administrador '{username}' criado com sucesso.",
            user_id=admin.id,
            entity_type="User",
            entity_id=admin.id
        )

        flash("Conta de Administrador criada com sucesso! Por favor, inicie sessão.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/setup_admin.html')
