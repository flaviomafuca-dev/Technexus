"""
app/services/financial_calculations.py — Serviço Central de Cálculos Financeiros

TODAS as fórmulas financeiras do TechNexus estão centralizadas aqui.
Nunca duplicar lógica financeira noutros módulos.

Utiliza DECIMAL para todos os cálculos — nunca FLOAT para valores monetários.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime, date, timezone, timedelta
from sqlalchemy import func, and_, or_
from app.extensions import db


# ==========================================
# Funções auxiliares de conversão segura
# ==========================================

def to_decimal(value, default=Decimal('0')):
    """
    Converte um valor para Decimal de forma segura.
    Evita erros de arredondamento de ponto flutuante.
    """
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def round_money(value):
    """Arredonda para 2 casas decimais (padrão monetário)."""
    return to_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ==========================================
# Períodos de análise
# ==========================================

def get_period_dates(period='month'):
    """
    Retorna as datas de início e fim para um período predefinido.
    
    Parâmetros:
        period: 'today', 'week', 'month', 'last_month', 
                '30days', 'year', ou datas personalizadas.
    
    Retorna:
        Tuple (start_date, end_date) em objecto date.
    """
    today = date.today()
    
    if period == 'today':
        return today, today
    
    elif period == 'week':
        # Últimos 7 dias
        return today - timedelta(days=6), today
    
    elif period == 'month':
        # Mês actual
        start = today.replace(day=1)
        return start, today
    
    elif period == 'last_month':
        # Mês anterior completo
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    
    elif period == '30days':
        return today - timedelta(days=29), today
    
    elif period == 'year':
        return today.replace(month=1, day=1), today
    
    else:
        return today.replace(day=1), today  # Default: mês actual


def get_previous_period(start_date, end_date):
    """
    Calcula o período anterior equivalente para comparações.
    
    O período anterior tem a mesma duração que o período actual.
    
    Parâmetros:
        start_date: Data de início do período actual.
        end_date: Data de fim do período actual.
    
    Retorna:
        Tuple (prev_start, prev_end) com o período anterior equivalente.
    """
    duration = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=duration - 1)
    return prev_start, prev_end


# ==========================================
# Faturação e Receitas
# ==========================================

def calculate_revenue(start_date, end_date):
    """
    Calcula a receita reconhecida no período.
    
    NOTA: Receita ≠ Recebimentos.
    Aqui contabilizamos vendas confirmadas (independentemente do pagamento).
    
    Parâmetros:
        start_date: Data de início.
        end_date: Data de fim.
    
    Retorna:
        Float com o total de receita reconhecida.
    """
    from app.models.sale import Sale
    
    result = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(
        Sale.sale_date >= start_date,
        Sale.sale_date <= end_date,
        Sale.status.in_(['confirmed', 'partial', 'paid']),
        Sale.sale_type == 'sale'  # Exclui orçamentos
    ).scalar()
    
    return float(to_decimal(result))


def calculate_collections(start_date, end_date):
    """
    Calcula os recebimentos efectivos (dinheiro realmente recebido) no período.
    
    Recebimentos ≠ Receita.
    
    Parâmetros:
        start_date: Data de início.
        end_date: Data de fim.
    
    Retorna:
        Float com o total recebido em dinheiro.
    """
    from app.models.payment import Payment
    
    result = db.session.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date,
        Payment.direction == 'in',
        Payment.is_cancelled == False,  # noqa: E712
        Payment.sale_id.isnot(None)  # Apenas recebimentos de vendas
    ).scalar()
    
    return float(to_decimal(result))


def calculate_service_revenue(start_date, end_date):
    """
    Calcula a receita de ordens de serviço concluídas no período.
    """
    from app.models.service import ServiceOrder
    
    result = db.session.query(
        func.coalesce(func.sum(ServiceOrder.agreed_price), 0)
    ).filter(
        ServiceOrder.actual_completion_date >= start_date,
        ServiceOrder.actual_completion_date <= end_date,
        ServiceOrder.status.in_(['completed', 'delivered'])
    ).scalar()
    
    return float(to_decimal(result))


# ==========================================
# Custo dos Produtos Vendidos (CPV / COGS)
# ==========================================

def calculate_cost_of_goods_sold(start_date, end_date):
    """
    Calcula o Custo dos Produtos Vendidos (CPV) no período.
    
    MÉTODO: Custo médio ponderado móvel.
    O custo de cada item vendido é o custo médio no momento da venda
    (guardado em SaleItem.unit_cost no momento da venda).
    
    NOTA IMPORTANTE: Não utilizamos o total de compras do período.
    O CPV é calculado com base nos custos dos itens efectivamente vendidos.
    
    Parâmetros:
        start_date: Data de início.
        end_date: Data de fim.
    
    Retorna:
        Float com o CPV do período.
    """
    from app.models.sale import Sale, SaleItem
    
    result = db.session.query(
        func.coalesce(func.sum(Sale.total_cost), 0)
    ).filter(
        Sale.sale_date >= start_date,
        Sale.sale_date <= end_date,
        Sale.status.in_(['confirmed', 'partial', 'paid']),
        Sale.sale_type == 'sale'
    ).scalar()
    
    return float(to_decimal(result))


# ==========================================
# Lucro Bruto
# ==========================================

def calculate_gross_profit(start_date, end_date):
    """
    Calcula o lucro bruto do período.
    
    Fórmula: Receita - Custo dos Produtos Vendidos
    
    Parâmetros:
        start_date: Data de início.
        end_date: Data de fim.
    
    Retorna:
        Dicionário com revenue, cogs, gross_profit e gross_margin_percent.
    """
    revenue = to_decimal(calculate_revenue(start_date, end_date))
    cogs = to_decimal(calculate_cost_of_goods_sold(start_date, end_date))
    service_revenue = to_decimal(calculate_service_revenue(start_date, end_date))
    
    # Custo directo dos serviços
    service_cost = to_decimal(calculate_service_costs(start_date, end_date))
    
    total_revenue = revenue + service_revenue
    total_cogs = cogs + service_cost
    gross_profit = total_revenue - total_cogs
    
    # Margem bruta — evita divisão por zero
    if total_revenue > 0:
        gross_margin_percent = float(gross_profit / total_revenue * 100)
    else:
        gross_margin_percent = None  # Sem receita, sem margem calculável
    
    return {
        'revenue': float(revenue),
        'service_revenue': float(service_revenue),
        'total_revenue': float(total_revenue),
        'cogs': float(cogs),
        'service_cost': float(service_cost),
        'total_cogs': float(total_cogs),
        'gross_profit': float(gross_profit),
        'gross_margin_percent': gross_margin_percent
    }


def calculate_service_costs(start_date, end_date):
    """Calcula os custos directos dos serviços concluídos no período."""
    from app.models.service import ServiceOrder
    from sqlalchemy import case
    
    # Custo total = mão de obra + materiais + outros
    result = db.session.query(
        func.coalesce(
            func.sum(
                ServiceOrder.labor_cost + 
                ServiceOrder.materials_cost + 
                ServiceOrder.other_costs
            ), 0
        )
    ).filter(
        ServiceOrder.actual_completion_date >= start_date,
        ServiceOrder.actual_completion_date <= end_date,
        ServiceOrder.status.in_(['completed', 'delivered'])
    ).scalar()
    
    return float(to_decimal(result))


# ==========================================
# Despesas Operacionais
# ==========================================

def calculate_operating_expenses(start_date, end_date, include_confidential=True):
    """
    Calcula as despesas operacionais reconhecidas no período.
    
    NOTA: Distingue despesas registadas de despesas pagas.
    Aqui calculamos despesas com data no período (base de acréscimo simplificada).
    
    Parâmetros:
        start_date: Data de início.
        end_date: Data de fim.
        include_confidential: Se False, exclui despesas confidenciais.
    
    Retorna:
        Float com o total de despesas.
    """
    from app.models.finance import Expense
    
    query = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date,
        Expense.status != 'cancelled'
    )
    
    if not include_confidential:
        query = query.filter(Expense.is_confidential == False)  # noqa: E712
    
    result = query.scalar()
    return float(to_decimal(result))


def calculate_expenses_by_category(start_date, end_date):
    """
    Calcula despesas agrupadas por categoria no período.
    
    Retorna:
        Lista de dicionários com category_name, total, count.
    """
    from app.models.finance import Expense, ExpenseCategory
    
    results = db.session.query(
        ExpenseCategory.name,
        func.coalesce(func.sum(Expense.amount), 0).label('total'),
        func.count(Expense.id).label('count')
    ).outerjoin(
        Expense, and_(
            Expense.category_id == ExpenseCategory.id,
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
            Expense.status != 'cancelled'
        )
    ).group_by(ExpenseCategory.name).all()
    
    return [
        {
            'category': r.name,
            'total': float(to_decimal(r.total)),
            'count': r.count
        }
        for r in results if float(to_decimal(r.total)) > 0
    ]


# ==========================================
# Resultado Operacional e Líquido
# ==========================================

def calculate_operating_result(start_date, end_date):
    """
    Calcula o resultado operacional do período.
    
    Fórmula: Lucro Bruto - Despesas Operacionais
    
    Parâmetros:
        start_date: Data de início.
        end_date: Data de fim.
    
    Retorna:
        Dicionário com todos os componentes.
    """
    gross = calculate_gross_profit(start_date, end_date)
    expenses = to_decimal(calculate_operating_expenses(start_date, end_date))
    
    gross_profit = to_decimal(gross['gross_profit'])
    operating_result = gross_profit - expenses
    
    total_revenue = to_decimal(gross['total_revenue'])
    
    # Margem operacional — evita divisão por zero
    if total_revenue > 0:
        operating_margin_percent = float(operating_result / total_revenue * 100)
    else:
        operating_margin_percent = None
    
    return {
        **gross,
        'operating_expenses': float(expenses),
        'operating_result': float(operating_result),
        'operating_margin_percent': operating_margin_percent
    }


# ==========================================
# Fluxo de Caixa
# ==========================================

def calculate_cash_flow(start_date, end_date, account_id=None):
    """
    Calcula o fluxo de caixa efectivo no período.
    
    Base de caixa: considera apenas movimentos efectivos de dinheiro.
    Transferências entre contas próprias NÃO afectam o fluxo total.
    
    Saldo final = Saldo inicial + Entradas - Saídas
    
    Parâmetros:
        start_date: Data de início.
        end_date: Data de fim.
        account_id: Se fornecido, calcula só para essa conta.
    
    Retorna:
        Dicionário com saldo_inicial, entradas, saidas, saldo_final.
    """
    from app.models.finance import FinancialMovement, FinancialAccount
    
    # Filtro base
    base_filter = [
        FinancialMovement.is_cancelled == False,  # noqa: E712
        FinancialMovement.is_transfer == False  # Exclui transferências internas
    ]
    
    if account_id:
        base_filter.append(FinancialMovement.account_id == account_id)
    
    # Entradas no período
    inflows = db.session.query(
        func.coalesce(func.sum(FinancialMovement.amount), 0)
    ).filter(
        *base_filter,
        FinancialMovement.movement_date >= start_date,
        FinancialMovement.movement_date <= end_date,
        FinancialMovement.movement_type == 'in'
    ).scalar()
    
    # Saídas no período
    outflows = db.session.query(
        func.coalesce(func.sum(FinancialMovement.amount), 0)
    ).filter(
        *base_filter,
        FinancialMovement.movement_date >= start_date,
        FinancialMovement.movement_date <= end_date,
        FinancialMovement.movement_type == 'out'
    ).scalar()
    
    # Saldo inicial (antes do período)
    opening_inflows = db.session.query(
        func.coalesce(func.sum(FinancialMovement.amount), 0)
    ).filter(
        *base_filter,
        FinancialMovement.movement_date < start_date,
        FinancialMovement.movement_type == 'in'
    ).scalar()
    
    opening_outflows = db.session.query(
        func.coalesce(func.sum(FinancialMovement.amount), 0)
    ).filter(
        *base_filter,
        FinancialMovement.movement_date < start_date,
        FinancialMovement.movement_type == 'out'
    ).scalar()
    
    # Saldo inicial das contas
    if account_id:
        account = FinancialAccount.query.get(account_id)
        opening_balance = to_decimal(account.opening_balance if account else 0)
    else:
        opening_balance = db.session.query(
            func.coalesce(func.sum(FinancialAccount.opening_balance), 0)
        ).filter(FinancialAccount.is_active == True).scalar()  # noqa: E712
        opening_balance = to_decimal(opening_balance)
    
    initial_balance = (
        opening_balance 
        + to_decimal(opening_inflows) 
        - to_decimal(opening_outflows)
    )
    
    period_inflows = to_decimal(inflows)
    period_outflows = to_decimal(outflows)
    final_balance = initial_balance + period_inflows - period_outflows
    
    return {
        'initial_balance': float(initial_balance),
        'inflows': float(period_inflows),
        'outflows': float(period_outflows),
        'net_flow': float(period_inflows - period_outflows),
        'final_balance': float(final_balance)
    }


# ==========================================
# Dívidas de Clientes e Fornecedores
# ==========================================

def calculate_accounts_receivable():
    """
    Calcula o total de dívidas de clientes (contas a receber).
    
    Fórmula: total das vendas - pagamentos recebidos
    
    Retorna:
        Dicionário com total, vencido, a_vencer.
    """
    from app.models.sale import Sale
    
    today = date.today()
    
    # Total geral a receber
    total = db.session.query(
        func.coalesce(
            func.sum(Sale.total_amount - Sale.paid_amount), 0
        )
    ).filter(
        Sale.status.in_(['confirmed', 'partial']),
        Sale.sale_type == 'sale'
    ).scalar()
    
    # Valor vencido (data de vencimento ultrapassada)
    overdue = db.session.query(
        func.coalesce(
            func.sum(Sale.total_amount - Sale.paid_amount), 0
        )
    ).filter(
        Sale.status.in_(['confirmed', 'partial']),
        Sale.sale_type == 'sale',
        Sale.due_date.isnot(None),
        Sale.due_date < today
    ).scalar()
    
    total_val = float(to_decimal(total))
    overdue_val = float(to_decimal(overdue))
    
    return {
        'total': total_val,
        'overdue': overdue_val,
        'current': total_val - overdue_val
    }


def calculate_accounts_payable():
    """
    Calcula o total de dívidas a fornecedores (contas a pagar).
    
    Retorna:
        Dicionário com total, vencido, a_vencer.
    """
    from app.models.purchase import Purchase
    
    today = date.today()
    
    total = db.session.query(
        func.coalesce(
            func.sum(Purchase.total_amount - Purchase.paid_amount), 0
        )
    ).filter(
        Purchase.status.in_(['confirmed', 'received', 'partial'])
    ).scalar()
    
    overdue = db.session.query(
        func.coalesce(
            func.sum(Purchase.total_amount - Purchase.paid_amount), 0
        )
    ).filter(
        Purchase.status.in_(['confirmed', 'received', 'partial']),
        Purchase.due_date.isnot(None),
        Purchase.due_date < today
    ).scalar()
    
    total_val = float(to_decimal(total))
    overdue_val = float(to_decimal(overdue))
    
    return {
        'total': total_val,
        'overdue': overdue_val,
        'current': total_val - overdue_val
    }


# ==========================================
# Ponto de Equilíbrio
# ==========================================

def calculate_break_even(fixed_costs, gross_margin_percent):
    """
    Calcula o ponto de equilíbrio (break-even).
    
    Fórmula: Custos Fixos / Margem de Contribuição (em %)
    
    NOTA: A hipótese utilizada é que a margem de contribuição
    é igual à margem bruta média do período. Isto é uma simplificação
    adequada para uma empresa com mix de produtos variado.
    O administrador deve compreender esta limitação.
    
    Parâmetros:
        fixed_costs: Total dos custos fixos mensais.
        gross_margin_percent: Margem bruta média em %.
    
    Retorna:
        Dicionário com break_even_revenue e hipóteses utilizadas.
    """
    fixed = to_decimal(fixed_costs)
    margin = to_decimal(gross_margin_percent)
    
    if margin <= 0:
        return {
            'break_even_revenue': None,
            'error': 'Margem bruta zero ou negativa — impossível calcular ponto de equilíbrio.',
            'assumptions': 'Margem bruta como proxy da margem de contribuição'
        }
    
    # Ponto de equilíbrio em receita
    break_even = fixed / (margin / 100)
    
    return {
        'break_even_revenue': float(break_even),
        'fixed_costs': float(fixed),
        'gross_margin_percent': float(margin),
        'assumptions': (
            'Hipótese: margem bruta média utilizada como margem de contribuição. '
            'Válido para empresas com mix de produtos relativamente estável. '
            'Resultado aproximado.'
        ),
        'error': None
    }


# ==========================================
# Dashboard — Indicadores principais
# ==========================================

def get_dashboard_indicators(start_date, end_date):
    """
    Reúne todos os indicadores para o dashboard executivo.
    Todos os dados provêm da base de dados — sem valores estáticos.
    
    Parâmetros:
        start_date: Data de início do período.
        end_date: Data de fim do período.
    
    Retorna:
        Dicionário com todos os indicadores.
    """
    # Calcula o período anterior equivalente para comparações
    prev_start, prev_end = get_previous_period(start_date, end_date)
    
    # Resultados do período actual
    current = calculate_operating_result(start_date, end_date)
    
    # Resultados do período anterior
    prev_revenue = calculate_revenue(prev_start, prev_end)
    prev_gross = calculate_gross_profit(prev_start, prev_end)
    
    # Recebimentos efectivos (base de caixa)
    collections = calculate_collections(start_date, end_date)
    
    # Dívidas
    receivable = calculate_accounts_receivable()
    payable = calculate_accounts_payable()
    
    # Contagens operacionais
    from app.models.sale import Sale
    from app.models.service import ServiceOrder
    from app.models.product import Product
    
    today = date.today()
    
    sales_count = Sale.query.filter(
        Sale.sale_date >= start_date,
        Sale.sale_date <= end_date,
        Sale.status != 'cancelled',
        Sale.sale_type == 'sale'
    ).count()
    
    pending_services = ServiceOrder.query.filter(
        ServiceOrder.status.in_(['received', 'diagnosing', 'waiting_approval', 
                                  'waiting_parts', 'in_progress'])
    ).count()
    
    low_stock_count = Product.query.filter(
        Product.is_active == True,  # noqa: E712
        Product.stock_quantity <= Product.minimum_stock
    ).count()
    
    quotes_pending = Sale.query.filter(
        Sale.sale_type == 'quote',
        Sale.status == 'draft',
        or_(Sale.quote_expires_at.is_(None), Sale.quote_expires_at >= today)
    ).count()
    
    # Variações percentuais
    from app.utils.formatting import calculate_percentage_change
    
    revenue_change = calculate_percentage_change(
        current['total_revenue'], prev_revenue
    )
    profit_change = calculate_percentage_change(
        current['gross_profit'], prev_gross['gross_profit']
    )
    
    return {
        # Receitas e custos
        'revenue': current['total_revenue'],
        'cogs': current['total_cogs'],
        'gross_profit': current['gross_profit'],
        'gross_margin_percent': current['gross_margin_percent'],
        'operating_expenses': current['operating_expenses'],
        'operating_result': current['operating_result'],
        'operating_margin_percent': current['operating_margin_percent'],
        
        # Recebimentos (base de caixa)
        'collections': collections,
        
        # Dívidas
        'accounts_receivable': receivable['total'],
        'accounts_receivable_overdue': receivable['overdue'],
        'accounts_payable': payable['total'],
        'accounts_payable_overdue': payable['overdue'],
        
        # Contagens operacionais
        'sales_count': sales_count,
        'pending_services': pending_services,
        'low_stock_count': low_stock_count,
        'quotes_pending': quotes_pending,
        
        # Variações
        'revenue_change_percent': revenue_change,
        'profit_change_percent': profit_change,
        
        # Período
        'period_start': start_date.isoformat(),
        'period_end': end_date.isoformat(),
    }
