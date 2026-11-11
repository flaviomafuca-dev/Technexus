"""
app/routes/customers.py — Gestão de Clientes e Saldos Devedores
"""

from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.customer import Customer
from app.utils.audit import log_action

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/')
@login_required
def index():
    """Listagem de clientes com saldos em dívida e pesquisa."""
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Customer.query.filter_by(is_active=True)
    if q:
        query = query.filter(
            (Customer.name.ilike(f"%{q}%")) |
            (Customer.trade_name.ilike(f"%{q}%")) |
            (Customer.phone.ilike(f"%{q}%")) |
            (Customer.nuit.ilike(f"%{q}%"))
        )

    pagination = query.order_by(Customer.name.asc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('customers/index.html', pagination=pagination, q=q)


@customers_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def create():
    """Cadastro de cliente (Pessoa Singular ou Empresa)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        customer_type = request.form.get('customer_type', 'individual')
        trade_name = request.form.get('trade_name', '').strip()
        phone = request.form.get('phone', '').strip()
        phone2 = request.form.get('phone2', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', 'Maputo').strip()
        nuit = request.form.get('nuit', '').strip()
        credit_limit = Decimal(request.form.get('credit_limit', '0') or '0')
        notes = request.form.get('notes', '').strip()

        if not name:
            flash("O nome do cliente é de preenchimento obrigatório.", "warning")
            return redirect(url_for('customers.create'))

        if nuit:
            existing = Customer.query.filter_by(nuit=nuit).first()
            if existing:
                flash(f"Já existe um cliente registado com o NUIT '{nuit}'.", "danger")
                return redirect(url_for('customers.create'))

        customer = Customer(
            name=name,
            customer_type=customer_type,
            trade_name=trade_name if trade_name else None,
            phone=phone,
            phone2=phone2,
            email=email if email else None,
            address=address,
            city=city,
            nuit=nuit if nuit else None,
            credit_limit=credit_limit,
            notes=notes,
            is_active=True,
            created_by=current_user.id
        )
        db.session.add(customer)
        db.session.commit()

        log_action(
            action="create_customer",
            description=f"Cliente '{customer.name}' cadastrado com sucesso",
            user_id=current_user.id,
            entity_type="Customer",
            entity_id=customer.id
        )

        flash(f"Cliente '{customer.name}' registado com sucesso!", "success")
        return redirect(url_for('customers.view', customer_id=customer.id))

    return render_template('customers/form.html', customer=None)


@customers_bp.route('/<int:customer_id>')
@login_required
def view(customer_id):
    """Ficha do cliente com histórico completo de compras, ordens de serviço e dívidas."""
    customer = Customer.query.get_or_404(customer_id)
    sales = customer.sales.order_by(db.desc('sale_date')).limit(15).all()
    service_orders = customer.service_orders.order_by(db.desc('received_date')).limit(10).all()
    contracts = customer.contracts.all()

    total_debt = customer.get_total_debt()

    return render_template(
        'customers/view.html',
        customer=customer,
        sales=sales,
        service_orders=service_orders,
        contracts=contracts,
        total_debt=total_debt
    )


@customers_bp.route('/<int:customer_id>/editar', methods=['GET', 'POST'])
@login_required
def edit(customer_id):
    """Edição dos dados cadastrais do cliente."""
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        customer.name = request.form.get('name', '').strip()
        customer.customer_type = request.form.get('customer_type', 'individual')
        customer.trade_name = request.form.get('trade_name', '').strip()
        customer.phone = request.form.get('phone', '').strip()
        customer.phone2 = request.form.get('phone2', '').strip()
        customer.email = request.form.get('email', '').strip() or None
        customer.address = request.form.get('address', '').strip()
        customer.city = request.form.get('city', 'Maputo').strip()
        customer.nuit = request.form.get('nuit', '').strip() or None
        customer.credit_limit = Decimal(request.form.get('credit_limit', '0') or '0')
        customer.notes = request.form.get('notes', '').strip()

        db.session.commit()

        log_action(
            action="update_customer",
            description=f"Dados do cliente '{customer.name}' atualizados",
            user_id=current_user.id,
            entity_type="Customer",
            entity_id=customer.id
        )

        flash(f"Dados de '{customer.name}' atualizados com sucesso!", "success")
        return redirect(url_for('customers.view', customer_id=customer.id))

    return render_template('customers/form.html', customer=customer)


@customers_bp.route('/<int:customer_id>/desativar', methods=['POST'])
@login_required
def deactivate(customer_id):
    """Desativação lógica do cliente preservando integridade financeira."""
    customer = Customer.query.get_or_404(customer_id)
    customer.is_active = False
    db.session.commit()

    log_action(
        action="deactivate_customer",
        description=f"Cliente '{customer.name}' desativado",
        user_id=current_user.id,
        entity_type="Customer",
        entity_id=customer.id
    )

    flash(f"Cliente '{customer.name}' desativado com sucesso.", "info")
    return redirect(url_for('customers.index'))
