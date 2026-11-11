"""
app/routes/contracts.py — Gestão de Contratos Recorrentes de Assistência e Manutenção
"""

from decimal import Decimal
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.finance import Contract
from app.models.customer import Customer
from app.utils.audit import log_action

contracts_bp = Blueprint('contracts', __name__)


def generate_contract_number():
    year = date.today().year
    count = Contract.query.count() + 1
    return f"CTR-{year}-{count:04d}"


@contracts_bp.route('/')
@login_required
def index():
    """Listagem de contratos de manutenção informática e suporte técnico."""
    status = request.args.get('status', 'active')
    query = Contract.query
    if status != 'all':
        query = query.filter_by(status=status)

    contracts_list = query.order_by(Contract.end_date.asc().nullslast()).all()
    return render_template('contracts/index.html', contracts=contracts_list, selected_status=status)


@contracts_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def create():
    """Criação de novo contrato de suporte ou manutenção."""
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        value = Decimal(request.form.get('value', '0') or '0')
        frequency = request.form.get('frequency', 'monthly')

        start_date_str = request.form.get('start_date')
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else date.today()

        end_date_str = request.form.get('end_date')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        terms = request.form.get('terms', '').strip()

        if not customer_id or not title or value <= Decimal('0'):
            flash("Indique o cliente, o título e o valor contratual.", "warning")
            return redirect(url_for('contracts.create'))

        contract = Contract(
            contract_number=generate_contract_number(),
            customer_id=customer_id,
            title=title,
            description=description,
            value=value,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            terms=terms,
            status='active',
            created_by=current_user.id
        )
        db.session.add(contract)
        db.session.commit()

        log_action(
            action="create_contract",
            description=f"Contrato {contract.contract_number} ('{title}') registado no valor de {value:.2f} MT ({frequency})",
            user_id=current_user.id,
            entity_type="Contract",
            entity_id=contract.id
        )

        flash(f"Contrato {contract.contract_number} registado com sucesso!", "success")
        return redirect(url_for('contracts.index'))

    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    return render_template('contracts/form.html', customers=customers)


@contracts_bp.route('/<int:contract_id>/cancelar', methods=['POST'])
@login_required
def cancel(contract_id):
    """Encerra ou cancela um contrato de suporte."""
    contract = Contract.query.get_or_404(contract_id)
    contract.status = 'cancelled'
    db.session.commit()

    flash(f"Contrato {contract.contract_number} cancelado com sucesso.", "info")
    return redirect(url_for('contracts.index'))
