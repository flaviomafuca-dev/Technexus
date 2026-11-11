"""
tests/test_financial_calculations.py — Testes Unitários de Cálculos Financeiros

Valida rigorosamente:
1. Receita Reconhecida vs Recebimentos em Caixa
2. Custo dos Produtos Vendidos (CPV) via Custo Médio Ponderado Móvel
3. Lucro Bruto e Margem Bruta
4. Despesas Operacionais e Resultado Líquido
5. Fluxo de Caixa (Entradas, Saídas e Neutralidade de Transferências Internas)
6. Dívidas de Clientes e Fornecedores (Aging)
7. Ponto de Equilíbrio (Break-even Analysis)
"""

from decimal import Decimal
from datetime import date, timedelta
import pytest
from app.extensions import db
from app.models.sale import Sale, SaleItem
from app.models.purchase import Purchase, PurchaseItem
from app.models.payment import Payment
from app.models.finance import Expense, ExpenseCategory, FinancialAccount, FinancialMovement
from app.services.financial_calculations import (
    calculate_revenue, calculate_collections, calculate_cost_of_goods_sold,
    calculate_gross_profit, calculate_operating_expenses, calculate_operating_result,
    calculate_cash_flow, calculate_accounts_receivable, calculate_accounts_payable,
    calculate_break_even, get_period_dates, to_decimal, round_money
)


def test_round_money_and_decimal_precision():
    """Garante que operações monetárias utilizam Decimal com arredondamento preciso."""
    val = Decimal('100.555')
    assert round_money(val) == Decimal('100.56')
    assert to_decimal(None) == Decimal('0')
    assert to_decimal('150.75') == Decimal('150.75')


def test_calculate_revenue_and_collections(app, sample_data, admin_user):
    """Testa a separação estrita entre Receita Reconhecida e Recebimentos de Caixa."""
    today = date.today()
    cust = sample_data['customer']
    prod = sample_data['product']
    acc = sample_data['account_cash']

    # Venda 1: 30.000 MT a pronto (100% paga)
    s1 = Sale(
        sale_number="VND-TEST-001",
        customer_id=cust.id,
        sale_date=today,
        status='paid',
        subtotal=Decimal('30000.00'),
        total_amount=Decimal('30000.00'),
        paid_amount=Decimal('30000.00'),
        total_cost=Decimal('20000.00'),
        registered_by=admin_user.id
    )
    db.session.add(s1)
    db.session.flush()

    p1 = Payment(
        payment_date=today,
        amount=Decimal('30000.00'),
        payment_method='cash',
        sale_id=s1.id,
        account_id=acc.id,
        direction='in',
        created_by=admin_user.id
    )
    db.session.add(p1)

    # Venda 2: 60.000 MT a crédito (apenas 20.000 MT recebidos de entrada)
    s2 = Sale(
        sale_number="VND-TEST-002",
        customer_id=cust.id,
        sale_date=today,
        status='partial',
        subtotal=Decimal('60000.00'),
        total_amount=Decimal('60000.00'),
        paid_amount=Decimal('20000.00'),
        total_cost=Decimal('40000.00'),
        registered_by=admin_user.id
    )
    db.session.add(s2)
    db.session.flush()

    p2 = Payment(
        payment_date=today,
        amount=Decimal('20000.00'),
        payment_method='cash',
        sale_id=s2.id,
        account_id=acc.id,
        direction='in',
        created_by=admin_user.id
    )
    db.session.add(p2)
    db.session.commit()

    # Receita reconhecida total = 30.000 + 60.000 = 90.000 MT
    revenue = calculate_revenue(today, today)
    assert revenue == 90000.00

    # Recebimentos em dinheiro (base de caixa) = 30.000 + 20.000 = 50.000 MT
    collections = calculate_collections(today, today)
    assert collections == 50000.00


def test_calculate_cost_of_goods_sold_and_gross_profit(app, sample_data, admin_user):
    """Testa apuração do CPV e do Lucro Bruto real."""
    today = date.today()
    cust = sample_data['customer']

    # Venda com total 50.000 MT e CPV real de 35.000 MT
    sale = Sale(
        sale_number="VND-TEST-003",
        customer_id=cust.id,
        sale_date=today,
        status='confirmed',
        subtotal=Decimal('50000.00'),
        total_amount=Decimal('50000.00'),
        paid_amount=Decimal('0.00'),
        total_cost=Decimal('35000.00'),
        registered_by=admin_user.id
    )
    db.session.add(sale)
    db.session.commit()

    cogs = calculate_cost_of_goods_sold(today, today)
    assert cogs == 35000.00

    gross = calculate_gross_profit(today, today)
    assert gross['total_revenue'] == 50000.00
    assert gross['total_cogs'] == 35000.00
    assert gross['gross_profit'] == 15000.00
    assert gross['gross_margin_percent'] == 30.0  # (15000 / 50000) * 100


def test_operating_expenses_and_operating_result(app, sample_data, admin_user):
    """Testa despesas operacionais e resultado líquido operacional."""
    today = date.today()
    cat = ExpenseCategory(name="Renda", is_active=True)
    db.session.add(cat)
    db.session.flush()

    # Despesa normal: 5.000 MT
    e1 = Expense(
        description="Renda Armazém",
        category_id=cat.id,
        amount=Decimal('5000.00'),
        expense_date=today,
        status='pending',
        is_confidential=False,
        created_by=admin_user.id
    )
    # Despesa confidencial: 2.000 MT
    e2 = Expense(
        description="Honorários Confidenciais",
        category_id=cat.id,
        amount=Decimal('2000.00'),
        expense_date=today,
        status='paid',
        is_confidential=True,
        created_by=admin_user.id
    )
    db.session.add_all([e1, e2])
    db.session.commit()

    # Total geral com confidenciais
    assert calculate_operating_expenses(today, today, include_confidential=True) == 7000.00
    # Apenas públicas
    assert calculate_operating_expenses(today, today, include_confidential=False) == 5000.00


def test_internal_transfers_do_not_affect_cash_flow_liquidity(app, sample_data, admin_user):
    """
    Regra Contabilística Fundamental:
    Transferências internas entre contas da empresa não alteram o fluxo líquido global.
    """
    today = date.today()
    c_acc = sample_data['account_cash']  # 10.000 MT
    b_acc = sample_data['account_bank']  # 50.000 MT

    # Transferir 5.000 MT do Caixa para o Banco
    mov_out = FinancialMovement(
        account_id=c_acc.id,
        movement_type='out',
        amount=Decimal('5000.00'),
        movement_date=today,
        category='internal_transfer',
        description="Transferência de Caixa para Banco (Saída)",
        is_transfer=True,
        created_by=admin_user.id
    )
    mov_in = FinancialMovement(
        account_id=b_acc.id,
        movement_type='in',
        amount=Decimal('5000.00'),
        movement_date=today,
        category='internal_transfer',
        description="Transferência de Caixa para Banco (Entrada)",
        is_transfer=True,
        created_by=admin_user.id
    )
    db.session.add_all([mov_out, mov_in])
    db.session.commit()

    # Saldo global inicial: 10.000 + 50.000 = 60.000 MT
    flow = calculate_cash_flow(today, today)
    assert flow['net_flow'] == 0.00
    assert flow['final_balance'] == 60000.00


def test_accounts_receivable_and_payable(app, sample_data, admin_user):
    """Testa cálculo de contas a receber e contas a pagar com deteção de vencidos."""
    today = date.today()
    yesterday = today - timedelta(days=5)
    tomorrow = today + timedelta(days=10)

    cust = sample_data['customer']
    sup = sample_data['supplier']

    # Venda vencida: 10.000 MT, pago 2.000 MT -> 8.000 MT vencidos
    s_overdue = Sale(
        sale_number="VND-OVERDUE",
        customer_id=cust.id,
        sale_date=yesterday,
        due_date=yesterday,
        status='partial',
        subtotal=Decimal('10000.00'),
        total_amount=Decimal('10000.00'),
        paid_amount=Decimal('2000.00'),
        registered_by=admin_user.id
    )
    # Venda a vencer: 20.000 MT, pago 0 MT -> 20.000 MT em prazo regular
    s_current = Sale(
        sale_number="VND-CURRENT",
        customer_id=cust.id,
        sale_date=today,
        due_date=tomorrow,
        status='confirmed',
        subtotal=Decimal('20000.00'),
        total_amount=Decimal('20000.00'),
        paid_amount=Decimal('0.00'),
        registered_by=admin_user.id
    )
    db.session.add_all([s_overdue, s_current])

    # Compra a pagar vencida: 15.000 MT, pago 5.000 MT -> 10.000 MT vencidos
    p_overdue = Purchase(
        purchase_number="CMP-OVERDUE",
        supplier_id=sup.id,
        purchase_date=yesterday,
        due_date=yesterday,
        status='partial',
        subtotal=Decimal('15000.00'),
        total_amount=Decimal('15000.00'),
        paid_amount=Decimal('5000.00'),
        created_by=admin_user.id
    )
    db.session.add(p_overdue)
    db.session.commit()

    rec = calculate_accounts_receivable()
    assert rec['total'] == 28000.00
    assert rec['overdue'] == 8000.00
    assert rec['current'] == 20000.00

    pay = calculate_accounts_payable()
    assert pay['total'] == 10000.00
    assert pay['overdue'] == 10000.00


def test_break_even_calculation():
    """Testa a fórmula do Ponto de Equilíbrio (Custos Fixos / Margem de Contribuição)."""
    fixed_costs = 50000.00  # 50.000 MT de despesas fixas
    margin_percent = 25.0   # 25% de margem bruta

    res = calculate_break_even(fixed_costs, margin_percent)
    # Ponto de equilíbrio: 50.000 / 0.25 = 200.000 MT
    assert res['break_even_revenue'] == 200000.00

    # Margem zero ou negativa deve retornar erro amigável sem crash
    err_res = calculate_break_even(fixed_costs, 0)
    assert err_res['break_even_revenue'] is None
    assert err_res['error'] is not None
