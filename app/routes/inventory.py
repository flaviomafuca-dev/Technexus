"""
app/routes/inventory.py — Gestão de Stock e Movimentações de Inventário
"""

from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.product import Product, StockMovement
from app.services.inventory_service import (
    register_stock_movement, manual_stock_adjustment, InventoryError
)
from app.utils.permissions import admin_required

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/')
@login_required
def index():
    """Painel de inventário, valorização de stock e alertas de reposição."""
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    total_units = sum(float(p.stock_quantity or 0) for p in products)
    total_cost_value = sum(float(p.stock_quantity or 0) * float(p.average_cost or 0) for p in products)
    total_sale_value = sum(float(p.stock_quantity or 0) * float(p.selling_price or 0) for p in products)

    low_stock = [p for p in products if p.is_below_minimum_stock]
    out_of_stock = [p for p in products if p.is_out_of_stock]

    return render_template(
        'inventory/index.html',
        products=products,
        total_units=total_units,
        total_cost_value=total_cost_value,
        total_sale_value=total_sale_value,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
        is_admin=current_user.is_admin
    )


@inventory_bp.route('/movimentacoes')
@login_required
def movements():
    """Histórico detalhado de movimentações de stock com filtros."""
    product_id = request.args.get('product_id', type=int)
    movement_type = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)

    query = StockMovement.query

    if product_id:
        query = query.filter_by(product_id=product_id)
    if movement_type:
        query = query.filter_by(movement_type=movement_type)

    pagination = query.order_by(StockMovement.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    return render_template(
        'inventory/movements.html',
        pagination=pagination,
        products=products,
        selected_product_id=product_id,
        selected_type=movement_type
    )


@inventory_bp.route('/ajuste', methods=['GET', 'POST'])
@login_required
@admin_required
def adjust():
    """Ajuste manual de contagem física de stock."""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        new_quantity = request.form.get('new_quantity', '')
        reason = request.form.get('reason', '').strip()

        if not product_id or new_quantity == '':
            flash("Indique o produto e a nova quantidade contada.", "warning")
            return redirect(url_for('inventory.adjust'))

        try:
            manual_stock_adjustment(
                product_id=product_id,
                new_quantity=new_quantity,
                user_id=current_user.id,
                reason=reason or "Inventário Físico"
            )
            db.session.commit()
            flash("Ajuste de inventário efetuado com sucesso!", "success")
            return redirect(url_for('inventory.index'))
        except InventoryError as e:
            db.session.rollback()
            flash(f"Erro no ajuste: {e}", "danger")

    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template('inventory/adjust.html', products=products)


@inventory_bp.route('/avaria', methods=['POST'])
@login_required
def damaged():
    """Registo de perda por equipamento danificado ou com defeito."""
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', type=float)
    reason = request.form.get('reason', '').strip()

    if not product_id or not quantity or quantity <= 0:
        flash("Dados de avaria inválidos.", "warning")
        return redirect(url_for('inventory.index'))

    try:
        register_stock_movement(
            product_id=product_id,
            movement_type='damaged',
            quantity=quantity,
            user_id=current_user.id,
            reason=f"Produto danificado: {reason}"
        )
        db.session.commit()
        flash("Registo de avaria processado com sucesso.", "info")
    except InventoryError as e:
        db.session.rollback()
        flash(f"Erro ao registar avaria: {e}", "danger")

    return redirect(url_for('inventory.index'))
