"""
app/routes/suppliers.py — Gestão de Fornecedores e Obrigações a Pagar
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.supplier import Supplier
from app.utils.audit import log_action

suppliers_bp = Blueprint('suppliers', __name__)


@suppliers_bp.route('/')
@login_required
def index():
    """Listagem de fornecedores e contas a pagar."""
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Supplier.query.filter_by(is_active=True)
    if q:
        query = query.filter(
            (Supplier.name.ilike(f"%{q}%")) |
            (Supplier.trade_name.ilike(f"%{q}%")) |
            (Supplier.phone.ilike(f"%{q}%")) |
            (Supplier.nuit.ilike(f"%{q}%"))
        )

    pagination = query.order_by(Supplier.name.asc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('suppliers/index.html', pagination=pagination, q=q)


@suppliers_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def create():
    """Registo de novo fornecedor."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        trade_name = request.form.get('trade_name', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        phone = request.form.get('phone', '').strip()
        phone2 = request.form.get('phone2', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', 'Maputo').strip()
        nuit = request.form.get('nuit', '').strip()
        payment_terms = request.form.get('payment_terms', '').strip()
        notes = request.form.get('notes', '').strip()

        if not name:
            flash("O nome do fornecedor é de preenchimento obrigatório.", "warning")
            return redirect(url_for('suppliers.create'))

        supplier = Supplier(
            name=name,
            trade_name=trade_name if trade_name else None,
            contact_person=contact_person,
            phone=phone,
            phone2=phone2,
            email=email if email else None,
            address=address,
            city=city,
            nuit=nuit if nuit else None,
            payment_terms=payment_terms,
            notes=notes,
            is_active=True,
            created_by=current_user.id
        )
        db.session.add(supplier)
        db.session.commit()

        log_action(
            action="create_supplier",
            description=f"Fornecedor '{supplier.name}' criado com sucesso",
            user_id=current_user.id,
            entity_type="Supplier",
            entity_id=supplier.id
        )

        flash(f"Fornecedor '{supplier.name}' registado com sucesso!", "success")
        return redirect(url_for('suppliers.view', supplier_id=supplier.id))

    return render_template('suppliers/form.html', supplier=None)


@suppliers_bp.route('/<int:supplier_id>')
@login_required
def view(supplier_id):
    """Ficha do fornecedor, compras efetuadas e dívidas pendentes."""
    supplier = Supplier.query.get_or_404(supplier_id)
    purchases = supplier.purchases.order_by(db.desc('purchase_date')).limit(15).all()
    products = supplier.products.all()
    total_debt = supplier.get_total_debt()

    return render_template(
        'suppliers/view.html',
        supplier=supplier,
        purchases=purchases,
        products=products,
        total_debt=total_debt
    )


@suppliers_bp.route('/<int:supplier_id>/editar', methods=['GET', 'POST'])
@login_required
def edit(supplier_id):
    """Edição de dados do fornecedor."""
    supplier = Supplier.query.get_or_404(supplier_id)

    if request.method == 'POST':
        supplier.name = request.form.get('name', '').strip()
        supplier.trade_name = request.form.get('trade_name', '').strip() or None
        supplier.contact_person = request.form.get('contact_person', '').strip()
        supplier.phone = request.form.get('phone', '').strip()
        supplier.phone2 = request.form.get('phone2', '').strip()
        supplier.email = request.form.get('email', '').strip() or None
        supplier.address = request.form.get('address', '').strip()
        supplier.city = request.form.get('city', 'Maputo').strip()
        supplier.nuit = request.form.get('nuit', '').strip() or None
        supplier.payment_terms = request.form.get('payment_terms', '').strip()
        supplier.notes = request.form.get('notes', '').strip()

        db.session.commit()

        log_action(
            action="update_supplier",
            description=f"Dados do fornecedor '{supplier.name}' atualizados",
            user_id=current_user.id,
            entity_type="Supplier",
            entity_id=supplier.id
        )

        flash(f"Fornecedor '{supplier.name}' atualizado com sucesso!", "success")
        return redirect(url_for('suppliers.view', supplier_id=supplier.id))

    return render_template('suppliers/form.html', supplier=supplier)
