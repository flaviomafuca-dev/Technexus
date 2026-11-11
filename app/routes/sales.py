"""
app/routes/sales.py — Gestão de Vendas, PDV e Orçamentos
"""

from decimal import Decimal
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.sale import Sale, SaleItem
from app.models.customer import Customer
from app.models.product import Product
from app.models.service import Service
from app.models.finance import FinancialAccount
from app.services.sales_service import (
    create_sale_or_quote, confirm_sale, cancel_sale, convert_quote_to_sale, SaleError
)
from app.services.payment_service import register_payment, PaymentError

sales_bp = Blueprint('sales', __name__)


@sales_bp.route('/')
@login_required
def index():
    """Listagem de vendas confirmadas e a crédito."""
    status = request.args.get('status', '')
    customer_id = request.args.get('customer_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = Sale.query.filter(Sale.sale_type == 'sale')

    if status:
        query = query.filter(Sale.status == status)
    if customer_id:
        query = query.filter(Sale.customer_id == customer_id)

    pagination = query.order_by(Sale.sale_date.desc(), Sale.id.desc()).paginate(page=page, per_page=15, error_out=False)
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()

    return render_template(
        'sales/index.html',
        pagination=pagination,
        customers=customers,
        selected_status=status,
        selected_customer_id=customer_id,
        is_admin=current_user.is_admin
    )


@sales_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def create():
    """Ponto de Venda (PDV) e emissão de nova venda direta."""
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        due_date_str = request.form.get('due_date')
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        discount_amount = Decimal(request.form.get('discount_amount', '0') or '0')
        notes = request.form.get('notes', '').strip()
        is_credit = bool(request.form.get('is_credit'))

        # Itens da venda
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        items_data = []
        for i in range(len(product_ids)):
            if product_ids[i]:
                items_data.append({
                    'product_id': int(product_ids[i]),
                    'quantity': Decimal(quantities[i] or '1'),
                    'unit_price': Decimal(unit_prices[i] or '0'),
                    'discount_amount': Decimal('0')
                })

        if not items_data:
            flash("Adicione pelo menos um produto à venda.", "warning")
            return redirect(url_for('sales.create'))

        try:
            # 1. Cria a venda em rascunho
            sale = create_sale_or_quote(
                user_id=current_user.id,
                customer_id=customer_id if customer_id else None,
                sale_type='sale',
                due_date=due_date,
                discount_amount=discount_amount,
                notes=notes,
                items_data=items_data
            )

            # 2. Informação de pagamento inicial
            initial_payment = None
            if not is_credit:
                account_id = request.form.get('account_id', type=int)
                pay_method = request.form.get('payment_method', 'cash')
                pay_ref = request.form.get('payment_reference', '').strip()
                initial_payment = {
                    'amount': sale.total_amount,
                    'account_id': account_id,
                    'payment_method': pay_method,
                    'reference': pay_ref
                }
            else:
                # Se for a crédito, pode ter entrada parcial
                down_payment = Decimal(request.form.get('down_payment', '0') or '0')
                if down_payment > Decimal('0'):
                    account_id = request.form.get('account_id', type=int)
                    pay_method = request.form.get('payment_method', 'cash')
                    initial_payment = {
                        'amount': down_payment,
                        'account_id': account_id,
                        'payment_method': pay_method,
                        'reference': request.form.get('payment_reference', '').strip()
                    }

            # 3. Confirma a venda e abate o stock
            confirm_sale(sale.id, current_user.id, initial_payment=initial_payment)
            db.session.commit()

            flash(f"Venda {sale.sale_number} registada e confirmada com sucesso!", "success")
            return redirect(url_for('sales.view', sale_id=sale.id))

        except (SaleError, PaymentError) as e:
            db.session.rollback()
            flash(f"Erro ao processar venda: {e}", "danger")
            return redirect(url_for('sales.create'))

    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    accounts = FinancialAccount.query.filter_by(is_active=True).order_by(FinancialAccount.name).all()

    return render_template('sales/form.html', customers=customers, products=products, accounts=accounts)


@sales_bp.route('/<int:sale_id>')
@login_required
def view(sale_id):
    """Consulta detalhada e recibo de venda."""
    sale = Sale.query.get_or_404(sale_id)
    payments = sale.payments.order_by(db.desc('payment_date')).all()
    accounts = FinancialAccount.query.filter_by(is_active=True).all()

    return render_template(
        'sales/view.html',
        sale=sale,
        payments=payments,
        accounts=accounts,
        is_admin=current_user.is_admin
    )


@sales_bp.route('/<int:sale_id>/pagamento', methods=['POST'])
@login_required
def add_payment(sale_id):
    """Regista um pagamento para saldo a receber de venda a crédito."""
    amount = Decimal(request.form.get('amount', '0') or '0')
    payment_method = request.form.get('payment_method', 'cash')
    account_id = request.form.get('account_id', type=int)
    reference = request.form.get('reference', '').strip()

    try:
        register_payment(
            amount=amount,
            payment_method=payment_method,
            account_id=account_id,
            user_id=current_user.id,
            sale_id=sale_id,
            reference=reference,
            notes="Liquidação de saldo a receber"
        )
        db.session.commit()
        flash(f"Pagamento de {amount:.2f} MT registado com sucesso!", "success")
    except PaymentError as e:
        db.session.rollback()
        flash(f"Erro no pagamento: {e}", "danger")

    return redirect(url_for('sales.view', sale_id=sale_id))


@sales_bp.route('/<int:sale_id>/cancelar', methods=['POST'])
@login_required
def cancel(sale_id):
    """Cancela uma venda com reposição de stock e anulação de pagamentos."""
    reason = request.form.get('cancellation_reason', '').strip()
    try:
        cancel_sale(sale_id=sale_id, user_id=current_user.id, cancellation_reason=reason)
        db.session.commit()
        flash("Venda cancelada com sucesso e stock reposto.", "info")
    except SaleError as e:
        db.session.rollback()
        flash(f"Erro ao cancelar venda: {e}", "danger")

    return redirect(url_for('sales.view', sale_id=sale_id))


# ==========================================
# Gestão de Orçamentos
# ==========================================

@sales_bp.route('/orcamentos')
@login_required
def quotes():
    """Listagem de orçamentos emitidos."""
    quotes_list = Sale.query.filter(
        Sale.sale_type == 'quote'
    ).order_by(Sale.sale_date.desc(), Sale.id.desc()).all()
    return render_template('sales/quotes.html', quotes=quotes_list)


@sales_bp.route('/orcamentos/novo', methods=['GET', 'POST'])
@login_required
def create_quote():
    """Emissão de novo orçamento profissional."""
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        expires_str = request.form.get('quote_expires_at')
        expires_at = datetime.strptime(expires_str, '%Y-%m-%d').date() if expires_str else None
        notes = request.form.get('notes', '').strip()

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        items_data = []
        for i in range(len(product_ids)):
            if product_ids[i]:
                items_data.append({
                    'product_id': int(product_ids[i]),
                    'quantity': Decimal(quantities[i] or '1'),
                    'unit_price': Decimal(unit_prices[i] or '0')
                })

        try:
            quote = create_sale_or_quote(
                user_id=current_user.id,
                customer_id=customer_id if customer_id else None,
                sale_type='quote',
                quote_expires_at=expires_at,
                notes=notes,
                items_data=items_data
            )
            db.session.commit()
            flash(f"Orçamento {quote.sale_number} gerado com sucesso!", "success")
            return redirect(url_for('sales.view_quote', quote_id=quote.id))
        except SaleError as e:
            db.session.rollback()
            flash(f"Erro no orçamento: {e}", "danger")

    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('sales/quote_form.html', customers=customers, products=products)


@sales_bp.route('/orcamentos/<int:quote_id>')
@login_required
def view_quote(quote_id):
    """Consulta e impressão de orçamento."""
    quote = Sale.query.filter_by(id=quote_id, sale_type='quote').first_or_404()
    return render_template('sales/quote_view.html', quote=quote)


@sales_bp.route('/orcamentos/<int:quote_id>/converter', methods=['POST'])
@login_required
def convert_quote(quote_id):
    """Aprova e converte um orçamento numa venda formal."""
    try:
        sale = convert_quote_to_sale(quote_id, current_user.id)
        db.session.commit()
        flash(f"Orçamento convertido na Venda {sale.sale_number} com sucesso!", "success")
        return redirect(url_for('sales.view', sale_id=sale.id))
    except SaleError as e:
        db.session.rollback()
        flash(f"Erro ao converter orçamento: {e}", "danger")
        return redirect(url_for('sales.view_quote', quote_id=quote_id))
