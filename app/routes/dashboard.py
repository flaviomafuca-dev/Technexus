"""
app/routes/dashboard.py — Dashboard Executivo e Operacional

Apresenta indicadores de desempenho e gráficos com base em dados reais:
- Faturação, Lucro Bruto, Despesas, Saldo Disponível, Dívidas
- Filtros de período (Hoje, 7 dias, Mês atual, Mês anterior, 30 dias)
- Proteção de dados confidenciais: O Gerente/Vendedor não vê lucro global nem custos confidenciais.
- Gráficos dinâmicos via Chart.js
"""

from datetime import date
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.services.financial_calculations import (
    get_period_dates, get_dashboard_indicators, calculate_cash_flow
)
from app.services.notification_service import check_and_generate_system_alerts
from app.services.analytics_service import generate_business_recommendations
from app.models.product import Product
from app.models.sale import Sale
from app.models.service import ServiceOrder

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """Página principal do Dashboard."""
    period = request.args.get('period', 'month')
    start_date, end_date = get_period_dates(period)

    # Executa verificação de alertas do sistema proativamente
    if current_user.is_admin:
        try:
            check_and_generate_system_alerts()
        except Exception:
            pass

    # Carregar indicadores financeiros e operacionais
    indicators = get_dashboard_indicators(start_date, end_date)
    cash_flow = calculate_cash_flow(start_date, end_date)

    # Produtos mais recentes com stock baixo
    low_stock_items = Product.query.filter(
        Product.is_active == True,
        Product.stock_quantity <= Product.minimum_stock
    ).limit(6).all()

    # Vendas recentes
    recent_sales = Sale.query.filter(
        Sale.sale_type == 'sale'
    ).order_by(Sale.sale_date.desc(), Sale.id.desc()).limit(6).all()

    # Ordens de serviço recentes
    recent_orders = ServiceOrder.query.order_by(
        ServiceOrder.received_date.desc(), ServiceOrder.id.desc()
    ).limit(6).all()

    # Recomendações empresariais para administradores
    recommendations = []
    if current_user.is_admin:
        recommendations = generate_business_recommendations()[:3]

    return render_template(
        'dashboard/index.html',
        period=period,
        start_date=start_date,
        end_date=end_date,
        indicators=indicators,
        cash_flow=cash_flow,
        low_stock_items=low_stock_items,
        recent_sales=recent_sales,
        recent_orders=recent_orders,
        recommendations=recommendations,
        is_admin=current_user.is_admin
    )


@dashboard_bp.route('/api/charts')
@login_required
def charts_data():
    """
    Endpoint JSON para renderização dos gráficos com Chart.js.
    Gera dados mensais dos últimos 6 meses.
    """
    today = date.today()
    months = []
    revenues = []
    profits = []
    expenses = []

    from app.services.financial_calculations import calculate_gross_profit, calculate_operating_expenses
    from dateutil.relativedelta import relativedelta

    for i in range(5, -1, -1):
        target_date = today - relativedelta(months=i)
        m_start = target_date.replace(day=1)
        # Último dia do mês
        next_month = m_start + relativedelta(months=1)
        m_end = next_month - relativedelta(days=1)

        m_name = m_start.strftime('%b/%Y')
        months.append(m_name)

        gross = calculate_gross_profit(m_start, m_end)
        exp = calculate_operating_expenses(m_start, m_end, include_confidential=current_user.is_admin)

        revenues.append(round(gross['total_revenue'], 2))
        if current_user.is_admin:
            profits.append(round(gross['gross_profit'], 2))
            expenses.append(round(exp, 2))

    return jsonify({
        'labels': months,
        'revenue': revenues,
        'profit': profits if current_user.is_admin else [],
        'expenses': expenses if current_user.is_admin else [],
        'can_view_profit': current_user.is_admin
    })
