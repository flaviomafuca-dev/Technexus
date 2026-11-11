"""
app/routes/finance.py — Gestão Financeira Estratégica, DRE e Ponto de Equilíbrio

Área exclusiva de Administradores:
- Demonstração de Resultados do Exercício (DRE) Simplificada
- Análise de Margens Reais de Lucro
- Ponto de Equilíbrio Operacional (Break-even Analysis)
- Gestão de Contas a Receber e a Pagar (Aging)
"""

from decimal import Decimal
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.services.financial_calculations import (
    calculate_operating_result, calculate_accounts_receivable,
    calculate_accounts_payable, calculate_break_even, get_period_dates,
    calculate_expenses_by_category
)
from app.utils.permissions import admin_required
from app.models.sale import Sale
from app.models.purchase import Purchase

finance_bp = Blueprint('finance', __name__)


@finance_bp.route('/')
@login_required
@admin_required
def index():
    """Painel financeiro central com DRE e ponto de equilíbrio."""
    period = request.args.get('period', 'month')
    start_date, end_date = get_period_dates(period)

    # 1. Demonstração de Resultados
    dre = calculate_operating_result(start_date, end_date)

    # 2. Despesas discriminadas por categoria
    expenses_by_cat = calculate_expenses_by_category(start_date, end_date)

    # 3. Dívidas (Receber vs Pagar)
    receivables = calculate_accounts_receivable()
    payables = calculate_accounts_payable()

    # 4. Ponto de Equilíbrio (Break-even)
    margin_pct = dre.get('gross_margin_percent') or 30.0  # fallback se sem vendas
    fixed_costs = dre.get('operating_expenses') or 0.0
    break_even = calculate_break_even(fixed_costs=fixed_costs, gross_margin_percent=margin_pct)

    return render_template(
        'finance/index.html',
        dre=dre,
        expenses_by_cat=expenses_by_cat,
        receivables=receivables,
        payables=payables,
        break_even=break_even,
        period=period,
        start_date=start_date,
        end_date=end_date
    )


@finance_bp.route('/contas-a-receber')
@login_required
@admin_required
def accounts_receivable():
    """Listagem detalhada de clientes com dívidas e datas de vencimento."""
    pending_sales = Sale.query.filter(
        Sale.status.in_(['confirmed', 'partial']),
        Sale.sale_type == 'sale'
    ).order_by(Sale.due_date.asc().nullslast()).all()

    summary = calculate_accounts_receivable()

    return render_template(
        'finance/receivables.html',
        pending_sales=pending_sales,
        summary=summary
    )


@finance_bp.route('/contas-a-pagar')
@login_required
@admin_required
def accounts_payable():
    """Listagem detalhada de obrigações devidas a fornecedores."""
    pending_purchases = Purchase.query.filter(
        Purchase.status.in_(['confirmed', 'received', 'partial'])
    ).order_by(Purchase.due_date.asc().nullslast()).all()

    summary = calculate_accounts_payable()

    return render_template(
        'finance/payables.html',
        pending_purchases=pending_purchases,
        summary=summary
    )
