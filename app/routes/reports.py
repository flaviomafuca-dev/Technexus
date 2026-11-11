"""
app/routes/reports.py — Central de Relatórios Empresariais e Exportações
"""

from datetime import date
from flask import Blueprint, render_template, request, send_file
from flask_login import login_required, current_user
from app.services.financial_calculations import (
    calculate_operating_result, calculate_cash_flow, get_period_dates
)
from app.services.analytics_service import get_profitability_analytics
from app.services.report_service import export_to_csv, export_to_excel, export_to_pdf
from app.models.sale import Sale
from app.models.purchase import Purchase
from app.models.product import Product
from app.utils.permissions import admin_required

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/')
@login_required
def index():
    """Menu central de relatórios operacionais e financeiros."""
    return render_template('reports/index.html', is_admin=current_user.is_admin)


@reports_bp.route('/vendas')
@login_required
def sales_report():
    """Relatório detalhado de vendas por período."""
    period = request.args.get('period', 'month')
    fmt = request.args.get('format', 'view')
    start_date, end_date = get_period_dates(period)

    sales = Sale.query.filter(
        Sale.sale_date >= start_date,
        Sale.sale_date <= end_date,
        Sale.status.in_(['confirmed', 'partial', 'paid']),
        Sale.sale_type == 'sale'
    ).order_by(Sale.sale_date.desc()).all()

    headers = ["Nº Venda", "Data", "Cliente", "Total (MT)", "Pago (MT)", "Pendente (MT)", "Estado"]
    rows = [
        [
            s.sale_number,
            s.sale_date.strftime('%d/%m/%Y'),
            s.customer.name if s.customer else "Consumidor Final",
            f"{s.total_amount:.2f}",
            f"{s.paid_amount:.2f}",
            f"{s.pending_amount:.2f}",
            s.status
        ]
        for s in sales
    ]

    title = f"Vendas de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"

    if fmt == 'csv':
        buffer = export_to_csv(headers, rows)
        return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name=f"vendas_{period}.csv")
    elif fmt == 'excel':
        buffer = export_to_excel(title, headers, rows)
        return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"vendas_{period}.xlsx")
    elif fmt == 'pdf':
        buffer = export_to_pdf(title, headers, rows)
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f"vendas_{period}.pdf")

    return render_template('reports/sales.html', sales=sales, period=period, start_date=start_date, end_date=end_date)


@reports_bp.route('/stock')
@login_required
def stock_report():
    """Relatório de inventário físico e valorização."""
    fmt = request.args.get('format', 'view')
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    headers = ["SKU", "Produto", "Qtd Stock", "Stock Mínimo", "Preço Venda (MT)", "Custo Médio (MT)", "Estado"]
    rows = [
        [
            p.sku,
            p.name,
            f"{float(p.stock_quantity or 0):.2f}",
            f"{float(p.minimum_stock or 0):.2f}",
            f"{float(p.selling_price or 0):.2f}",
            f"{float(p.average_cost or 0):.2f}" if current_user.is_admin else "—",
            "Esgotado" if p.is_out_of_stock else ("Baixo" if p.is_below_minimum_stock else "Normal")
        ]
        for p in products
    ]

    title = f"Posição Geral de Stock ({date.today().strftime('%d/%m/%Y')})"

    if fmt == 'csv':
        buffer = export_to_csv(headers, rows)
        return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name="stock.csv")
    elif fmt == 'excel':
        buffer = export_to_excel(title, headers, rows)
        return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name="stock.xlsx")
    elif fmt == 'pdf':
        buffer = export_to_pdf(title, headers, rows)
        return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name="stock.pdf")

    return render_template('reports/stock.html', products=products)


@reports_bp.route('/rentabilidade')
@login_required
@admin_required
def profitability_report():
    """Relatório executivo de rentabilidade e margens por produto/serviço."""
    period = request.args.get('period', 'month')
    start_date, end_date = get_period_dates(period)
    data = get_profitability_analytics(start_date, end_date, limit=50)

    return render_template(
        'reports/profitability.html',
        data=data,
        period=period,
        start_date=start_date,
        end_date=end_date
    )
