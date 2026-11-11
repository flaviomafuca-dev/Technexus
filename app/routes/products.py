"""
app/routes/products.py — Gestão de Produtos, Marcas e Categorias
"""

from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.product import Product, Category, Brand, ProductSerialNumber
from app.models.supplier import Supplier
from app.utils.permissions import admin_required
from app.utils.audit import log_action

products_bp = Blueprint('products', __name__)


@products_bp.route('/')
@login_required
def index():
    """Listagem de produtos com pesquisa e filtros."""
    query_str = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)
    brand_id = request.args.get('brand_id', type=int)
    stock_status = request.args.get('stock_status', '')  # 'low', 'out', 'all'
    page = request.args.get('page', 1, type=int)

    query = Product.query.filter_by(is_active=True)

    if query_str:
        query = query.filter(
            (Product.name.ilike(f"%{query_str}%")) |
            (Product.sku.ilike(f"%{query_str}%")) |
            (Product.model.ilike(f"%{query_str}%"))
        )
    if category_id:
        query = query.filter_by(category_id=category_id)
    if brand_id:
        query = query.filter_by(brand_id=brand_id)

    if stock_status == 'low':
        query = query.filter(Product.stock_quantity <= Product.minimum_stock, Product.stock_quantity > 0)
    elif stock_status == 'out':
        query = query.filter(Product.stock_quantity <= 0)

    pagination = query.order_by(Product.name.asc()).paginate(page=page, per_page=15, error_out=False)

    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    brands = Brand.query.filter_by(is_active=True).order_by(Brand.name).all()

    return render_template(
        'products/index.html',
        pagination=pagination,
        categories=categories,
        brands=brands,
        query_str=query_str,
        category_id=category_id,
        brand_id=brand_id,
        stock_status=stock_status,
        is_admin=current_user.is_admin
    )


@products_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def create():
    """Cadastro de um novo produto informático."""
    if request.method == 'POST':
        sku = request.form.get('sku', '').strip()
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        model = request.form.get('model', '').strip()
        unit = request.form.get('unit', 'unidade').strip()

        category_id = request.form.get('category_id', type=int)
        brand_id = request.form.get('brand_id', type=int)
        supplier_id = request.form.get('supplier_id', type=int)

        purchase_price = Decimal(request.form.get('purchase_price', '0') or '0')
        selling_price = Decimal(request.form.get('selling_price', '0') or '0')
        initial_stock = Decimal(request.form.get('initial_stock', '0') or '0')
        minimum_stock = Decimal(request.form.get('minimum_stock', '5') or '5')
        has_serial = bool(request.form.get('has_serial_number'))

        if not sku or not name:
            flash("O código SKU e o Nome do produto são obrigatórios.", "warning")
            return redirect(url_for('products.create'))

        existing = Product.query.filter_by(sku=sku).first()
        if existing:
            flash(f"Já existe um produto com o código SKU '{sku}'.", "danger")
            return redirect(url_for('products.create'))

        if selling_price < purchase_price and selling_price > 0:
            flash("Atenção: O preço de venda definido é inferior ao custo de compra!", "warning")

        product = Product(
            sku=sku,
            name=name,
            description=description,
            model=model,
            unit=unit,
            category_id=category_id if category_id else None,
            brand_id=brand_id if brand_id else None,
            supplier_id=supplier_id if supplier_id else None,
            purchase_price=purchase_price,
            average_cost=purchase_price,
            selling_price=selling_price,
            stock_quantity=initial_stock,
            minimum_stock=minimum_stock,
            has_serial_number=has_serial,
            is_active=True,
            created_by=current_user.id
        )
        db.session.add(product)
        db.session.flush()

        # Se houver stock inicial, registar o movimento de abertura
        if initial_stock > Decimal('0'):
            from app.models.product import StockMovement
            from datetime import datetime, timezone
            sm = StockMovement(
                product_id=product.id,
                movement_type='adjustment_in',
                quantity=initial_stock,
                unit_cost=purchase_price,
                stock_before=Decimal('0'),
                stock_after=initial_stock,
                reason="Saldo inicial de inventário no cadastro",
                created_by=current_user.id,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(sm)

        db.session.commit()

        log_action(
            action="create_product",
            description=f"Produto '{product.name}' (SKU: {product.sku}) criado",
            user_id=current_user.id,
            entity_type="Product",
            entity_id=product.id
        )

        flash(f"Produto '{product.name}' registado com sucesso!", "success")
        return redirect(url_for('products.view', product_id=product.id))

    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    brands = Brand.query.filter_by(is_active=True).order_by(Brand.name).all()
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()

    return render_template('products/form.html', product=None, categories=categories, brands=brands, suppliers=suppliers)


@products_bp.route('/<int:product_id>')
@login_required
def view(product_id):
    """Ficha detalhada do produto e histórico de movimentações."""
    product = Product.query.get_or_404(product_id)
    movements = product.stock_movements.order_by(db.desc('created_at')).limit(20).all()
    serials = product.serial_numbers.filter_by(status='in_stock').all() if product.has_serial_number else []

    return render_template(
        'products/view.html',
        product=product,
        movements=movements,
        serials=serials,
        is_admin=current_user.is_admin
    )


@products_bp.route('/<int:product_id>/editar', methods=['GET', 'POST'])
@login_required
def edit(product_id):
    """Edição dos dados cadastrais do produto."""
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.description = request.form.get('description', '').strip()
        product.model = request.form.get('model', '').strip()
        product.unit = request.form.get('unit', 'unidade').strip()

        cat_id = request.form.get('category_id', type=int)
        product.category_id = cat_id if cat_id else None

        brd_id = request.form.get('brand_id', type=int)
        product.brand_id = brd_id if brd_id else None

        sup_id = request.form.get('supplier_id', type=int)
        product.supplier_id = sup_id if sup_id else None

        new_selling_price = Decimal(request.form.get('selling_price', '0') or '0')
        product.minimum_stock = Decimal(request.form.get('minimum_stock', '5') or '5')
        product.has_serial_number = bool(request.form.get('has_serial_number'))

        # Apenas admin pode alterar o preço de compra e custo diretamente
        if current_user.is_admin:
            new_purchase_price = Decimal(request.form.get('purchase_price', '0') or '0')
            product.purchase_price = new_purchase_price
            if float(product.average_cost or 0) <= 0:
                product.average_cost = new_purchase_price

        product.selling_price = new_selling_price

        if product.selling_price < product.average_cost and product.selling_price > 0:
            flash("Aviso: O preço de venda fixado é inferior ao custo médio!", "warning")

        db.session.commit()

        log_action(
            action="update_product",
            description=f"Produto '{product.name}' (SKU: {product.sku}) atualizado",
            user_id=current_user.id,
            entity_type="Product",
            entity_id=product.id
        )

        flash(f"Produto '{product.name}' atualizado com sucesso!", "success")
        return redirect(url_for('products.view', product_id=product.id))

    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    brands = Brand.query.filter_by(is_active=True).order_by(Brand.name).all()
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()

    return render_template('products/form.html', product=product, categories=categories, brands=brands, suppliers=suppliers)


@products_bp.route('/<int:product_id>/desativar', methods=['POST'])
@login_required
@admin_required
def deactivate(product_id):
    """Desativação lógica do produto para preservar histórico financeiro."""
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()

    log_action(
        action="deactivate_product",
        description=f"Produto '{product.name}' (SKU: {product.sku}) desativado",
        user_id=current_user.id,
        entity_type="Product",
        entity_id=product.id
    )

    flash(f"Produto '{product.name}' desativado com sucesso.", "info")
    return redirect(url_for('products.index'))


@products_bp.route('/categorias', methods=['GET', 'POST'])
@login_required
def categories():
    """Gestão de categorias de produtos."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip()
        if not name:
            flash("O nome da categoria é obrigatório.", "warning")
        else:
            cat = Category(name=name, description=desc, is_active=True)
            db.session.add(cat)
            db.session.commit()
            flash(f"Categoria '{name}' criada!", "success")
        return redirect(url_for('products.categories'))

    all_categories = Category.query.order_by(Category.name).all()
    return render_template('products/categories.html', categories=all_categories)


@products_bp.route('/marcas', methods=['GET', 'POST'])
@login_required
def brands():
    """Gestão de marcas."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("O nome da marca é obrigatório.", "warning")
        else:
            brand = Brand(name=name, is_active=True)
            db.session.add(brand)
            db.session.commit()
            flash(f"Marca '{name}' criada!", "success")
        return redirect(url_for('products.brands'))

    all_brands = Brand.query.order_by(Brand.name).all()
    return render_template('products/brands.html', brands=all_brands)
