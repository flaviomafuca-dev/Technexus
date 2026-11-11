"""
app/services/analytics_service.py — TechNexus Intelligence (Business Intelligence)

Módulo de análise automática baseada em dados reais:
- Análise de Crescimento (comparações entre períodos equivalentes sem percentagens enganadoras)
- Análise de Rentabilidade Real (produtos e serviços mais rentáveis vs produtos deficitários)
- Análise de Despesas por Categoria e Variações
- Diagnóstico de Stock e Rotatividade
- Recomendações Empresariais Acionáveis com fundamentação e limitações
"""

from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import func, and_, desc
from app.extensions import db
from app.models.sale import Sale, SaleItem
from app.models.product import Product
from app.models.service import Service, ServiceOrder
from app.models.finance import Expense, ExpenseCategory, Contract
from app.services.financial_calculations import (
    calculate_revenue, calculate_gross_profit, calculate_operating_expenses,
    get_period_dates, get_previous_period
)
from app.utils.formatting import calculate_percentage_change


def get_growth_analytics(period='month'):
    """
    Calcula as taxas de crescimento do negócio comparando com o período anterior equivalente.
    """
    start_date, end_date = get_period_dates(period)
    prev_start, prev_end = get_previous_period(start_date, end_date)

    # Período actual
    curr_rev = calculate_revenue(start_date, end_date)
    curr_gross = calculate_gross_profit(start_date, end_date)
    curr_exp = calculate_operating_expenses(start_date, end_date)

    # Período anterior
    prev_rev = calculate_revenue(prev_start, prev_end)
    prev_gross = calculate_gross_profit(prev_start, prev_end)
    prev_exp = calculate_operating_expenses(prev_start, prev_end)

    # Vendas e clientes
    curr_sales_count = Sale.query.filter(
        Sale.sale_date >= start_date,
        Sale.sale_date <= end_date,
        Sale.status.in_(['confirmed', 'partial', 'paid']),
        Sale.sale_type == 'sale'
    ).count()

    prev_sales_count = Sale.query.filter(
        Sale.sale_date >= prev_start,
        Sale.sale_date <= prev_end,
        Sale.status.in_(['confirmed', 'partial', 'paid']),
        Sale.sale_type == 'sale'
    ).count()

    return {
        'period_current': {'start': start_date, 'end': end_date},
        'period_previous': {'start': prev_start, 'end': prev_end},
        'metrics': {
            'revenue': {
                'current': curr_rev,
                'previous': prev_rev,
                'change_percent': calculate_percentage_change(curr_rev, prev_rev)
            },
            'gross_profit': {
                'current': curr_gross['gross_profit'],
                'previous': prev_gross['gross_profit'],
                'change_percent': calculate_percentage_change(curr_gross['gross_profit'], prev_gross['gross_profit'])
            },
            'expenses': {
                'current': curr_exp,
                'previous': prev_exp,
                'change_percent': calculate_percentage_change(curr_exp, prev_exp)
            },
            'sales_count': {
                'current': curr_sales_count,
                'previous': prev_sales_count,
                'change_percent': calculate_percentage_change(curr_sales_count, prev_sales_count)
            }
        }
    }


def get_profitability_analytics(start_date, end_date, limit=10):
    """
    Identifica os produtos e serviços mais e menos rentáveis no período com base em dados reais.
    """
    # 1. Produtos com maior lucro bruto acumulado
    top_products_query = db.session.query(
        Product.id,
        Product.name,
        Product.sku,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.quantity * SaleItem.unit_price - SaleItem.discount_amount).label('total_revenue'),
        func.sum(SaleItem.quantity * SaleItem.unit_cost).label('total_cost'),
        func.sum(
            (SaleItem.quantity * SaleItem.unit_price - SaleItem.discount_amount) - (SaleItem.quantity * SaleItem.unit_cost)
        ).label('total_profit')
    ).join(Sale, Sale.id == SaleItem.sale_id).join(Product, Product.id == SaleItem.product_id).filter(
        Sale.sale_date >= start_date,
        Sale.sale_date <= end_date,
        Sale.status.in_(['confirmed', 'partial', 'paid']),
        Sale.sale_type == 'sale'
    ).group_by(Product.id, Product.name, Product.sku).order_by(desc('total_profit')).limit(limit).all()

    top_products = []
    for row in top_products_query:
        rev = float(row.total_revenue or 0)
        profit = float(row.total_profit or 0)
        margin = (profit / rev * 100) if rev > 0 else 0
        top_products.append({
            'id': row.id,
            'name': row.name,
            'sku': row.sku,
            'qty_sold': float(row.total_qty or 0),
            'revenue': rev,
            'cost': float(row.total_cost or 0),
            'gross_profit': profit,
            'margin_percent': margin
        })

    # 2. Produtos vendidos com margem muito baixa ou abaixo do custo
    low_margin_products = []
    for tp in top_products:
        if tp['margin_percent'] < 10.0:
            low_margin_products.append(tp)

    # 3. Rentabilidade de Ordens de Serviço
    completed_orders = ServiceOrder.query.filter(
        ServiceOrder.actual_completion_date >= start_date,
        ServiceOrder.actual_completion_date <= end_date,
        ServiceOrder.status.in_(['completed', 'delivered'])
    ).all()

    services_summary = {}
    for o in completed_orders:
        s_name = o.service.name if o.service else (o.equipment_type or "Geral")
        if s_name not in services_summary:
            services_summary[s_name] = {'count': 0, 'revenue': 0, 'cost': 0, 'profit': 0}
        rev = float(o.agreed_price or 0)
        cost = o.total_cost
        profit = rev - cost
        services_summary[s_name]['count'] += 1
        services_summary[s_name]['revenue'] += rev
        services_summary[s_name]['cost'] += cost
        services_summary[s_name]['profit'] += profit

    top_services = []
    for s_name, data in services_summary.items():
        margin = (data['profit'] / data['revenue'] * 100) if data['revenue'] > 0 else 0
        top_services.append({
            'service_name': s_name,
            'count': data['count'],
            'revenue': data['revenue'],
            'cost': data['cost'],
            'gross_profit': data['profit'],
            'margin_percent': margin
        })
    top_services.sort(key=lambda x: x['gross_profit'], reverse=True)

    return {
        'top_products': top_products,
        'low_margin_products': low_margin_products,
        'top_services': top_services[:limit]
    }


def generate_business_recommendations():
    """
    Gera recomendações empresariais concretas e acionáveis estritamente fundamentadas nos dados:
    1. O problema ou oportunidade identificado
    2. Os dados de sustentação
    3. A ação concreta recomendada
    4. O benefício esperado
    5. As limitações da análise
    """
    recommendations = []
    today = date.today()
    month_start = today.replace(day=1)

    # Análise 1: Produtos com stock crítico e procura comprovada
    critical_stock = Product.query.filter(
        Product.is_active == True,
        Product.stock_quantity <= Product.minimum_stock
    ).all()

    for p in critical_stock:
        # Verificar se houve vendas deste produto nos últimos 30 dias
        recent_sales = db.session.query(func.coalesce(func.sum(SaleItem.quantity), 0)).join(Sale).filter(
            SaleItem.product_id == p.id,
            Sale.sale_date >= today - timedelta(days=30),
            Sale.status.in_(['confirmed', 'partial', 'paid'])
        ).scalar()

        sold_qty = float(recent_sales or 0)
        if sold_qty > 0:
            recommendations.append({
                'category': 'stock',
                'priority': 'alta',
                'title': f"Reposição Prioritária: {p.name}",
                'issue': f"O produto tem apenas {float(p.stock_quantity or 0):.0f} unidades em stock (abaixo do mínimo de {float(p.minimum_stock or 0):.0f}), com vendas recentes ativas.",
                'evidence': f"Foram vendidas {sold_qty:.0f} unidades nos últimos 30 dias. Risco iminente de perda de vendas por rutura de stock.",
                'recommended_action': f"Emitir ordem de compra ao fornecedor para repor pelo menos {sold_qty:.0f} unidades de '{p.name}'.",
                'expected_benefit': f"Garantir continuidade de faturação e satisfação dos clientes em material com procura frequente.",
                'limitations': "A previsão baseia-se no histórico recente de 30 dias e assume estabilidade na procura."
            })

    # Análise 2: Produtos com preço de venda abaixo ou próximo do custo
    below_cost = Product.query.filter(
        Product.is_active == True,
        Product.selling_price < Product.average_cost,
        Product.selling_price > 0
    ).all()

    for p in below_cost:
        sell = float(p.selling_price or 0)
        cost = float(p.average_cost or 0)
        diff = cost - sell
        recommendations.append({
            'category': 'pricing',
            'priority': 'critica',
            'title': f"Preço de Venda Abaixo do Custo: {p.name}",
            'issue': f"O preço de venda fixado ({sell:.2f} MT) é inferior ao custo médio ponderado atual ({cost:.2f} MT).",
            'evidence': f"Cada unidade vendida gera um prejuízo direto estimado de {diff:.2f} MT.",
            'recommended_action': f"Ajustar imediatamente o preço de venda para pelo menos {cost * 1.25:.2f} MT (margem de 20%) ou renegociar custo com fornecedor.",
            'expected_benefit': f"Eliminação de margem negativa e recuperação da sustentabilidade operacional.",
            'limitations': "Não considera eventuais estratégias pontuais de liquidação voluntária de stock descontinuado."
        })

    # Análise 3: Contratos prestes a expirar
    near_contracts = Contract.query.filter(
        Contract.status == 'active',
        Contract.end_date.isnot(None),
        Contract.end_date <= today + timedelta(days=20)
    ).all()

    for c in near_contracts:
        recommendations.append({
            'category': 'commercial',
            'priority': 'media',
            'title': f"Renovação de Contrato: {c.title}",
            'issue': f"O contrato com o cliente '{c.customer.name}' termina a {c.end_date.strftime('%d/%m/%Y')}.",
            'evidence': f"Receita recorrente associada de {float(c.value or 0):.2f} MT ({c.frequency}).",
            'recommended_action': f"Contactar o cliente para apresentação de proposta de renovação contratual antes do término.",
            'expected_benefit': f"Retenção de cliente e salvaguarda de receita recorrente contratada.",
            'limitations': "Depende da intenção de renovação do cliente e da avaliação dos serviços prestados."
        })

    # Se não houver problemas críticos, emitir diagnóstico de conformidade
    if not recommendations:
        recommendations.append({
            'category': 'general',
            'priority': 'baixa',
            'title': "Operação Estável e em Conformidade",
            'issue': "Não foram detetadas ruturas críticas de stock nem margens negativas no catálogo ativo.",
            'evidence': "Todos os produtos comercializados possuem margens positivas e stock dentro dos parâmetros normais.",
            'recommended_action': "Manter o acompanhamento regular dos indicadores semanais e monitorizar despesas fixas.",
            'expected_benefit': "Manutenção da saúde financeira da empresa.",
            'limitations': "Análise baseada nos registos disponíveis até à data."
        })

    return recommendations
