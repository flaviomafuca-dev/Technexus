"""
app/routes/settings.py — Configurações Gerais da Empresa e Backups

Acesso exclusivo a Administradores.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.notification import AppSettings
from app.models.finance import ExpenseCategory
from app.models.product import Category
from app.services.backup_service import create_system_backup, list_available_backups
from app.utils.permissions import admin_required
from app.utils.audit import log_action

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    """Painel de configurações gerais da empresa."""
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        company_phone = request.form.get('company_phone', '').strip()
        company_email = request.form.get('company_email', '').strip()
        company_address = request.form.get('company_address', '').strip()
        company_nuit = request.form.get('company_nuit', '').strip()
        rent_reserve_target = request.form.get('rent_reserve_target', '0').strip()

        def set_val(k, v):
            s = AppSettings.query.filter_by(key=k).first()
            if not s:
                s = AppSettings(key=k, value=str(v), value_type='string', updated_by=current_user.id)
                db.session.add(s)
            else:
                s.value = str(v)
                s.updated_by = current_user.id

        set_val('COMPANY_NAME', company_name or 'TechNexus')
        set_val('COMPANY_PHONE', company_phone)
        set_val('COMPANY_EMAIL', company_email)
        set_val('COMPANY_ADDRESS', company_address)
        set_val('COMPANY_NUIT', company_nuit)
        set_val('RENT_RESERVE_TARGET', rent_reserve_target or '0')

        db.session.commit()

        log_action(
            action="update_settings",
            description="Configurações gerais da empresa atualizadas",
            user_id=current_user.id,
            entity_type="Settings"
        )

        flash("Configurações atualizadas com sucesso!", "success")
        return redirect(url_for('settings.index'))

    def get_val(k, default=""):
        s = AppSettings.query.filter_by(key=k).first()
        return s.value if s and s.value else default

    settings_data = {
        'company_name': get_val('COMPANY_NAME', 'TechNexus'),
        'company_phone': get_val('COMPANY_PHONE', '+258 84 000 0000'),
        'company_email': get_val('COMPANY_EMAIL', 'contacto@technexus.co.mz'),
        'company_address': get_val('COMPANY_ADDRESS', 'Maputo, Moçambique'),
        'company_nuit': get_val('COMPANY_NUIT', '400123456'),
        'rent_reserve_target': get_val('RENT_RESERVE_TARGET', '25000')
    }

    backups = list_available_backups()
    return render_template('settings/index.html', settings=settings_data, backups=backups)


@settings_bp.route('/backup/criar', methods=['POST'])
@login_required
@admin_required
def create_backup_action():
    """Gera um backup completo da base de dados e guarda na pasta de segurança."""
    try:
        res = create_system_backup(user_id=current_user.id)
        flash(f"Cópia de segurança criada com sucesso! Ficheiro: {res['filename']} ({res['size_kb']} KB)", "success")
    except Exception as e:
        flash(f"Falha ao gerar cópia de segurança: {e}", "danger")

    return redirect(url_for('settings.index'))


@settings_bp.route('/backup/download/<filename>')
@login_required
@admin_required
def download_backup(filename):
    """Permite ao administrador descarregar uma cópia de segurança guardada."""
    import os
    backup_dir = current_app.config.get('BACKUP_DIR', 'backups')
    filepath = os.path.join(backup_dir, filename)

    if not os.path.exists(filepath) or not filename.endswith('.json.gz'):
        flash("Ficheiro de backup inexistente ou inválido.", "danger")
        return redirect(url_for('settings.index'))

    return send_file(filepath, as_attachment=True, download_name=filename)
