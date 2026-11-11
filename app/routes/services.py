"""
app/routes/services.py — Catálogo de Serviços Informáticos e Técnicos
"""

from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.service import Service, ServiceCategory
from app.utils.audit import log_action

services_bp = Blueprint('services', __name__)


@services_bp.route('/')
@login_required
def index():
    """Listagem do catálogo de serviços técnicos."""
    services_list = Service.query.filter_by(is_active=True).order_by(Service.name).all()
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return render_template('services/index.html', services=services_list, categories=categories)


@services_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def create():
    """Registo de novo tipo de serviço técnico."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', type=int)
        ref_price = Decimal(request.form.get('reference_price', '0') or '0')
        est_cost = Decimal(request.form.get('estimated_cost', '0') or '0')
        est_hours = Decimal(request.form.get('estimated_hours', '1') or '1')

        if not name:
            flash("O nome do serviço é obrigatório.", "warning")
            return redirect(url_for('services.create'))

        service = Service(
            name=name,
            description=description,
            category_id=category_id if category_id else None,
            reference_price=ref_price,
            estimated_cost=est_cost,
            estimated_hours=est_hours,
            is_active=True
        )
        db.session.add(service)
        db.session.commit()

        log_action(
            action="create_service",
            description=f"Serviço '{service.name}' cadastrado",
            user_id=current_user.id,
            entity_type="Service",
            entity_id=service.id
        )

        flash(f"Serviço '{service.name}' criado com sucesso!", "success")
        return redirect(url_for('services.index'))

    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return render_template('services/form.html', service=None, categories=categories)
