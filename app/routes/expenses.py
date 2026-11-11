"""
app/routes/expenses.py — Gestão de Despesas, Compromissos Fixos e Reserva para a Renda
"""

import os
from decimal import Decimal
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.finance import Expense, ExpenseCategory, RecurringExpense, FinancialAccount
from app.services.payment_service import register_payment, PaymentError
from app.utils.permissions import admin_required

expenses_bp = Blueprint('expenses', __name__)


@expenses_bp.route('/')
@login_required
def index():
    """Listagem de despesas operacionais."""
    category_id = request.args.get('category_id', type=int)
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)

    query = Expense.query
    # Se utilizador não for admin, oculta despesas confidenciais
    if not current_user.is_admin:
        query = query.filter_by(is_confidential=False)

    if category_id:
        query = query.filter_by(category_id=category_id)
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).paginate(page=page, per_page=15, error_out=False)
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    accounts = FinancialAccount.query.filter_by(is_active=True).all()

    # Total despesas pendentes e pagas
    all_exp = query.all()
    total_amount = sum(float(e.amount or 0) for e in all_exp)
    total_paid = sum(float(e.paid_amount or 0) for e in all_exp)
    total_pending = total_amount - total_paid

    return render_template(
        'expenses/index.html',
        pagination=pagination,
        categories=categories,
        accounts=accounts,
        total_amount=total_amount,
        total_paid=total_paid,
        total_pending=total_pending,
        selected_category_id=category_id,
        selected_status=status,
        is_admin=current_user.is_admin
    )


@expenses_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def create():
    """Registo de nova despesa operacional."""
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', type=int)
        amount = Decimal(request.form.get('amount', '0') or '0')

        exp_date_str = request.form.get('expense_date')
        exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date() if exp_date_str else date.today()

        due_date_str = request.form.get('due_date')
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

        beneficiary = request.form.get('beneficiary', '').strip()
        is_confidential = bool(request.form.get('is_confidential')) and current_user.is_admin
        is_paid = bool(request.form.get('is_paid'))
        notes = request.form.get('notes', '').strip()

        if not description or amount <= Decimal('0'):
            flash("Indique uma descrição válida e um montante positivo.", "warning")
            return redirect(url_for('expenses.create'))

        # Tratamento de ficheiro de comprovativo (receipt)
        receipt_filename = None
        file = request.files.get('receipt')
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[-1].lower()
            allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'png', 'jpg', 'jpeg'})
            if ext in allowed:
                sec_name = secure_filename(f"rec_{int(datetime.now().timestamp())}_{file.filename}")
                upload_path = os.path.join(current_app.config.get('UPLOAD_FOLDER'), sec_name)
                file.save(upload_path)
                receipt_filename = sec_name
            else:
                flash("Formato de comprovativo não permitido (use PDF, PNG ou JPG).", "warning")

        expense = Expense(
            description=description,
            category_id=category_id if category_id else None,
            amount=amount,
            paid_amount=Decimal('0'),
            expense_date=exp_date,
            due_date=due_date,
            status='pending',
            beneficiary=beneficiary,
            is_confidential=is_confidential,
            receipt_file=receipt_filename,
            notes=notes,
            created_by=current_user.id
        )
        db.session.add(expense)
        db.session.flush()

        # Se já foi paga na hora
        if is_paid:
            account_id = request.form.get('account_id', type=int)
            payment_method = request.form.get('payment_method', 'cash')
            register_payment(
                amount=amount,
                payment_method=payment_method,
                account_id=account_id,
                user_id=current_user.id,
                expense_id=expense.id,
                payment_date=exp_date,
                notes="Pagamento imediato de despesa"
            )

        db.session.commit()
        flash(f"Despesa '{description}' no valor de {amount:.2f} MT registada com sucesso!", "success")
        return redirect(url_for('expenses.index'))

    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    accounts = FinancialAccount.query.filter_by(is_active=True).all()
    return render_template('expenses/form.html', categories=categories, accounts=accounts, is_admin=current_user.is_admin)


@expenses_bp.route('/<int:expense_id>/pagamento', methods=['POST'])
@login_required
def add_payment(expense_id):
    """Regista o pagamento de uma despesa que estava pendente."""
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
            expense_id=expense_id,
            reference=reference,
            notes="Liquidação de despesa"
        )
        db.session.commit()
        flash(f"Pagamento de despesa no valor de {amount:.2f} MT processado com sucesso!", "success")
    except PaymentError as e:
        db.session.rollback()
        flash(f"Erro no pagamento: {e}", "danger")

    return redirect(url_for('expenses.index'))


# ==========================================
# Compromissos Fixos e Recorrentes
# ==========================================

@expenses_bp.route('/recorrentes')
@login_required
@admin_required
def recurring():
    """Listagem de compromissos fixos recorrentes (Renda, Internet, Salários)."""
    items = RecurringExpense.query.filter_by(is_active=True).all()
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    return render_template('expenses/recurring.html', items=items, categories=categories)


@expenses_bp.route('/recorrentes/novo', methods=['POST'])
@login_required
@admin_required
def create_recurring():
    """Cadastro de despesa recorrente regular."""
    desc = request.form.get('description', '').strip()
    cat_id = request.form.get('category_id', type=int)
    amount = Decimal(request.form.get('expected_amount', '0') or '0')
    freq = request.form.get('frequency', 'monthly')
    due_day = request.form.get('due_day', type=int) or 1
    beneficiary = request.form.get('beneficiary', '').strip()

    rec = RecurringExpense(
        description=desc,
        category_id=cat_id if cat_id else None,
        expected_amount=amount,
        frequency=freq,
        due_day=due_day,
        beneficiary=beneficiary,
        start_date=date.today(),
        is_active=True,
        created_by=current_user.id
    )
    db.session.add(rec)
    db.session.commit()

    flash(f"Compromisso recorrente '{desc}' registado com sucesso!", "success")
    return redirect(url_for('expenses.recurring'))
