"""
app/routes/users.py — Gestão de Utilizadores e Controlo de Perfis (RBAC)

Acesso exclusivo a Administradores:
- Criação de contas de utilizador (admin ou manager).
- Ativação / desativação de contas.
- Salvaguarda fundamental: impede a desativação ou alteração de perfil do último administrador ativo.
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User
from app.utils.permissions import admin_required
from app.utils.audit import log_action

users_bp = Blueprint('users', __name__)


@users_bp.route('/')
@login_required
@admin_required
def index():
    """Listagem de todos os utilizadores do sistema."""
    users_list = User.query.order_by(User.full_name).all()
    return render_template('users/index.html', users=users_list)


@users_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Criação de um novo utilizador."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'manager')
        password = request.form.get('password', '')

        if not full_name or not username or not email or not password:
            flash("Todos os campos obrigatórios devem ser preenchidos.", "warning")
            return redirect(url_for('users.create'))

        if len(password) < 6:
            flash("A palavra-passe deve conter pelo menos 6 caracteres.", "warning")
            return redirect(url_for('users.create'))

        if User.query.filter_by(username=username).first():
            flash(f"O nome de utilizador '{username}' já se encontra registado.", "danger")
            return redirect(url_for('users.create'))

        if User.query.filter_by(email=email).first():
            flash(f"O e-mail '{email}' já está associado a outra conta.", "danger")
            return redirect(url_for('users.create'))

        user = User(
            full_name=full_name,
            username=username,
            email=email,
            role=role,
            is_active=True,
            created_by=current_user.id,
            created_at=datetime.now(timezone.utc)
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        log_action(
            action="create_user",
            description=f"Utilizador '{username}' criado com perfil '{role}'",
            user_id=current_user.id,
            entity_type="User",
            entity_id=user.id
        )

        flash(f"Utilizador '{full_name}' criado com sucesso!", "success")
        return redirect(url_for('users.index'))

    return render_template('users/form.html', user=None)


@users_bp.route('/<int:user_id>/estado', methods=['POST'])
@login_required
@admin_required
def toggle_status(user_id):
    """Ativa ou desativa a conta de um utilizador com salvaguarda do último administrador."""
    user = User.query.get_or_404(user_id)

    # Regra de Segurança: Não permitir desativar o último admin ativo
    if user.is_admin and user.is_active:
        active_admins_count = User.query.filter_by(role='admin', is_active=True).count()
        if active_admins_count <= 1:
            flash("Operação bloqueada: Não é permitido desativar o único Administrador ativo do sistema.", "danger")
            return redirect(url_for('users.index'))

    user.is_active = not user.is_active
    db.session.commit()

    action_name = "ativada" if user.is_active else "desativada"
    log_action(
        action="toggle_user_status",
        description=f"Conta do utilizador '{user.username}' foi {action_name}",
        user_id=current_user.id,
        entity_type="User",
        entity_id=user.id
    )

    flash(f"Conta de '{user.full_name}' {action_name} com sucesso.", "info")
    return redirect(url_for('users.index'))
