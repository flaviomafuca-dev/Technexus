"""
app/routes/purchases.py — Gestão de Compras e Fornecedores
"""

from decimal import Decimal
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.purchase import Purchase
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.finance import FinancialAccount
from app.services.purchase_service import (
    create_purchase, confirm_purchase, receive_purchase, PurchaseError
)
from app.services.payment_service import register_payment, PaymentError

purchases_bp = Blueprint('purchases', __name__)


@purchases_bp.route('/')
@login_required
def index():
    """Listagem de compras a fornecedores."""
    status = request.args.get('status', '')
    supplier_id = request.args.get('supplier_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = Purchase.query

    if status:
        query = query.filter_by(status=status)
    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)

    pagination = query.order_by(Purchase.purchase_date.desc(), Purchase.id.desc()).paginate(page=page, per_page=15, error_out=False)
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()

    return render_template(
        'purchases/index.html',
        pagination=pagination,
        suppliers=suppliers,
        selected_status=status,
        selected_supplier_id=supplier_id
    )


@purchases_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def create():
    """Criação de nova ordem de compra a fornecedor."""
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', type=int)
        due_date_str = request.form.get('due_date')
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        supplier_doc = request.form.get('supplier_document', '').strip()
        shipping_cost = Decimal(request.form.get('shipping_cost', '0') or '0')
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
            purchase = create_purchase(
                user_id=current_user.id,
                supplier_id=supplier_id,
                due_date=due_date,
                supplier_document=supplier_doc,
                shipping_cost=shipping_cost,
                notes=notes,
                items_data=items_data
            )
            # Confirma a ordem de compra
            confirm_purchase(purchase.id, current_user.id)
            db.session.commit()

            flash(f"Compra {purchase.purchase_number} registada e confirmada com sucesso!", "success")
            return redirect(url_for('purchases.view', purchase_id=purchase.id))
        except PurchaseError as e:
            db.session.rollback()
            flash(f"Erro ao registar compra: {e}", "danger")

    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('purchases/form.html', suppliers=suppliers, products=products)


@purchases_bp.route('/<int:purchase_id>')
@login_required
def view(purchase_id):
    """Ficha da compra, itens e pagamentos efetuados."""
    purchase = Purchase.query.get_or_404(purchase_id)
    payments = purchase.payments.order_by(db.desc('payment_date')).all()
    accounts = FinancialAccount.query.filter_by(is_active=True).all()

    return render_template(
        'purchases/view.html',
        purchase=purchase,
        payments=payments,
        accounts=accounts
    )


@purchases_bp.route('/<int:purchase_id>/receber', methods=['POST'])
@login_required
def receive(purchase_id):
    """Regista a recepção física das mercadorias com entrada no stock."""
    try:
        receive_purchase(purchase_id, current_user.id)
        db.session.commit()
        flash("Mercadorias recebidas com sucesso! Stock atualizado e custo médio recalculado.", "success")
    except PurchaseError as e:
        db.session.rollback()
        flash(f"Erro ao receber compra: {e}", "danger")

    return redirect(url_for('purchases.view', purchase_id=purchase_id))


@purchases_bp.route('/<int:purchase_id>/pagamento', methods=['POST'])
@login_required
def add_payment(purchase_id):
    """Regista um pagamento a fornecedor."""
    amount = Decimal(request.form.get('amount', '0') or '0')
    payment_method = request.form.get('payment_method', 'bank_transfer')
    account_id = request.form.get('account_id', type=int)
    reference = request.form.get('reference', '').strip()

    try:
        register_payment(
            amount=amount,
            payment_method=payment_method,
            account_id=account_id,
            user_id=current_user.id,
            purchase_id=purchase_id,
            reference=reference,
            notes="Pagamento de fatura de fornecedor"
        )
        db.session.commit()
        flash(f"Pagamento de {amount:.2f} MT registado com sucesso!", "success")
    except PaymentError as e:
        db.session.rollback()
        flash(f"Erro no pagamento: {e}", "danger")

    return redirect(url_for('purchases.view', purchase_id=purchase_id))
