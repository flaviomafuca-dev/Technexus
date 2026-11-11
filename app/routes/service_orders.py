"""
app/routes/service_orders.py — Gestão de Ordens de Serviço (Assistência Técnica)
"""

from decimal import Decimal
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.service import ServiceOrder, Service
from app.models.customer import Customer
from app.models.product import Product
from app.models.employee import Employee
from app.models.finance import FinancialAccount
from app.services.service_order_service import (
    create_service_order, update_order_status, add_material_to_order, ServiceOrderError
)
from app.services.payment_service import register_payment, PaymentError

service_orders_bp = Blueprint('service_orders', __name__)


@service_orders_bp.route('/')
@login_required
def index():
    """Listagem de Ordens de Serviço com filtros por estado e técnico."""
    status = request.args.get('status', '')
    technician_id = request.args.get('technician_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = ServiceOrder.query
    if status:
        query = query.filter_by(status=status)
    if technician_id:
        query = query.filter_by(technician_id=technician_id)

    pagination = query.order_by(ServiceOrder.received_date.desc(), ServiceOrder.id.desc()).paginate(page=page, per_page=15, error_out=False)
    technicians = Employee.query.filter_by(status='active').all()

    return render_template(
        'service_orders/index.html',
        pagination=pagination,
        technicians=technicians,
        selected_status=status,
        selected_technician_id=technician_id,
        is_admin=current_user.is_admin
    )


@service_orders_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def create():
    """Abertura de nova Ordem de Serviço com recolha de equipamento."""
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        service_id = request.form.get('service_id', type=int)
        technician_id = request.form.get('technician_id', type=int)

        eq_type = request.form.get('equipment_type', '').strip()
        eq_brand = request.form.get('equipment_brand', '').strip()
        eq_model = request.form.get('equipment_model', '').strip()
        eq_serial = request.form.get('equipment_serial', '').strip()

        problem = request.form.get('problem_description', '').strip()
        agreed_price = Decimal(request.form.get('agreed_price', '0') or '0')
        labor_cost = Decimal(request.form.get('labor_cost', '0') or '0')

        est_date_str = request.form.get('estimated_completion_date')
        est_date = datetime.strptime(est_date_str, '%Y-%m-%d').date() if est_date_str else None

        notes = request.form.get('notes', '').strip()

        try:
            order = create_service_order(
                user_id=current_user.id,
                customer_id=customer_id,
                problem_description=problem,
                equipment_type=eq_type,
                equipment_brand=eq_brand,
                equipment_model=eq_model,
                equipment_serial=eq_serial,
                service_id=service_id if service_id else None,
                technician_id=technician_id if technician_id else None,
                agreed_price=agreed_price,
                labor_cost=labor_cost,
                estimated_completion_date=est_date,
                notes=notes
            )
            db.session.commit()
            flash(f"Ordem de Serviço {order.order_number} criada com sucesso!", "success")
            return redirect(url_for('service_orders.view', order_id=order.id))
        except ServiceOrderError as e:
            db.session.rollback()
            flash(f"Erro ao abrir OS: {e}", "danger")

    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    services = Service.query.filter_by(is_active=True).order_by(Service.name).all()
    technicians = Employee.query.filter_by(status='active').all()

    return render_template('service_orders/form.html', customers=customers, services=services, technicians=technicians)


@service_orders_bp.route('/<int:order_id>')
@login_required
def view(order_id):
    """Consulta detalhada da OS, peças utilizadas, custos reais e histórico de estados."""
    order = ServiceOrder.query.get_or_404(order_id)
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    accounts = FinancialAccount.query.filter_by(is_active=True).all()
    payments = order.payments.all()
    history = order.status_history.all()

    return render_template(
        'service_orders/view.html',
        order=order,
        products=products,
        accounts=accounts,
        payments=payments,
        history=history,
        is_admin=current_user.is_admin
    )


@service_orders_bp.route('/<int:order_id>/estado', methods=['POST'])
@login_required
def update_status(order_id):
    """Atualiza o estado de evolução da ordem de serviço."""
    new_status = request.form.get('status')
    notes = request.form.get('notes', '').strip()

    try:
        update_order_status(order_id, new_status, current_user.id, notes=notes)
        db.session.commit()
        flash("Estado da Ordem de Serviço atualizado com sucesso!", "success")
    except ServiceOrderError as e:
        db.session.rollback()
        flash(f"Erro ao atualizar estado: {e}", "danger")

    return redirect(url_for('service_orders.view', order_id=order_id))


@service_orders_bp.route('/<int:order_id>/material', methods=['POST'])
@login_required
def add_material(order_id):
    """Adiciona material ou peça de reposição consumida na reparação."""
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', type=float)
    description = request.form.get('description', '').strip()
    unit_cost = request.form.get('unit_cost', type=float)

    try:
        add_material_to_order(
            order_id=order_id,
            user_id=current_user.id,
            quantity=quantity,
            product_id=product_id if product_id else None,
            description=description,
            unit_cost=unit_cost
        )
        db.session.commit()
        flash("Material adicionado à Ordem de Serviço com sucesso!", "success")
    except ServiceOrderError as e:
        db.session.rollback()
        flash(f"Erro ao adicionar peça: {e}", "danger")

    return redirect(url_for('service_orders.view', order_id=order_id))


@service_orders_bp.route('/<int:order_id>/pagamento', methods=['POST'])
@login_required
def add_payment(order_id):
    """Regista pagamento de cliente referente à Ordem de Serviço."""
    order = ServiceOrder.query.get_or_404(order_id)
    amount = Decimal(request.form.get('amount', '0') or '0')
    payment_method = request.form.get('payment_method', 'cash')
    account_id = request.form.get('account_id', type=int)
    reference = request.form.get('reference', '').strip()

    pending = Decimal(str(order.agreed_price)) - Decimal(str(order.paid_amount or 0))
    if amount > pending:
        flash(f"O montante ({amount:.2f} MT) não pode exceder o saldo pendente ({pending:.2f} MT).", "danger")
        return redirect(url_for('service_orders.view', order_id=order_id))

    try:
        account = FinancialAccount.query.get_or_404(account_id)
        from app.models.payment import Payment
        from app.models.finance import FinancialMovement

        pay = Payment(
            reference=reference,
            payment_date=datetime.now().date(),
            amount=amount,
            payment_method=payment_method,
            service_order_id=order.id,
            account_id=account.id,
            direction='in',
            notes="Pagamento de Ordem de Serviço",
            created_by=current_user.id
        )
        db.session.add(pay)
        db.session.flush()

        fin_mov = FinancialMovement(
            account_id=account.id,
            movement_type='in',
            amount=amount,
            movement_date=datetime.now().date(),
            category='service_receipt',
            description=f"Recebimento de OS {order.order_number}",
            payment_id=pay.id,
            created_by=current_user.id
        )
        db.session.add(fin_mov)

        order.paid_amount = Decimal(str(order.paid_amount or 0)) + amount
        db.session.commit()

        flash(f"Pagamento de {amount:.2f} MT registado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao registar pagamento: {e}", "danger")

    return redirect(url_for('service_orders.view', order_id=order_id))
