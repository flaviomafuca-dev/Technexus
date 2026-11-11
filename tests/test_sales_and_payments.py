"""
tests/test_sales_and_payments.py — Testes Unitários e de Integração de Vendas e Pagamentos

Valida:
1. Criação de venda e abate atómico de stock.
2. Registo de CPV exato e cálculo de Lucro Bruto da venda.
3. Pagamento total (pronto pagamento) com geração de movimento em caixa.
4. Venda a crédito com pagamento parcial e dívida pendente.
5. Bloqueio de pagamento superior ao valor da dívida.
6. Cancelamento de venda com reposição de stock e anulação de pagamentos.
7. Conversão de orçamento (Quote) em venda formal confirmada.
"""

from decimal import Decimal
from datetime import date
import pytest
from app.extensions import db
from app.models.sale import Sale
from app.models.payment import Payment
from app.models.finance import FinancialMovement
from app.services.sales_service import (
    create_sale_or_quote, confirm_sale, cancel_sale, convert_quote_to_sale, SaleError
)
from app.services.payment_service import register_payment, cancel_payment, PaymentError


def test_create_and_confirm_sale_with_immediate_payment(app, sample_data, admin_user):
    """Testa o fluxo completo de uma venda a pronto com baixa de stock e movimento de caixa."""
    prod = sample_data['product']  # Stock: 10, Custo: 20.000, Venda: 30.000 MT
    cust = sample_data['customer']
    acc = sample_data['account_cash']

    # 1. Criar a venda (2 unidades = 60.000 MT)
    items = [{
        'product_id': prod.id,
        'quantity': 2,
        'unit_price': Decimal('30000.00'),
        'description': "Portátil HP 15s"
    }]
    sale = create_sale_or_quote(
        user_id=admin_user.id,
        customer_id=cust.id,
        sale_type='sale',
        items_data=items
    )
    db.session.commit()

    assert sale.status == 'draft'
    assert sale.total_amount == Decimal('60000.00')
    # Stock ainda não deve ter sido mexido no rascunho
    assert prod.stock_quantity == Decimal('10')

    # 2. Confirmar a venda com pagamento imediato de 60.000 MT no Caixa
    payment_info = {
        'amount': Decimal('60000.00'),
        'payment_method': 'cash',
        'account_id': acc.id,
        'reference': 'REC-DINHEIRO-001'
    }
    confirmed = confirm_sale(sale.id, admin_user.id, initial_payment=payment_info)
    db.session.commit()

    assert confirmed.status == 'paid'
    assert confirmed.paid_amount == Decimal('60000.00')
    assert confirmed.balance_due == Decimal('0.00')
    # Stock baixou de 10 para 8
    assert prod.stock_quantity == Decimal('8')
    # CPV = 2 * 20.000 = 40.000 MT
    assert confirmed.total_cost == Decimal('40000.00')
    # Lucro Bruto = 60.000 - 40.000 = 20.000 MT
    assert confirmed.gross_profit == Decimal('20000.00')

    # Movimento financeiro gerado
    mov = FinancialMovement.query.filter_by(sale_id=sale.id).first()
    assert mov is not None
    assert mov.amount == Decimal('60000.00')
    assert mov.movement_type == 'in'


def test_credit_sale_and_partial_payment(app, sample_data, admin_user):
    """Testa venda a crédito com pagamento de sinal e posterior liquidação."""
    prod = sample_data['product']
    cust = sample_data['customer']
    acc = sample_data['account_bank']

    items = [{
        'product_id': prod.id,
        'quantity': 1,
        'unit_price': Decimal('30000.00'),
        'description': "Portátil HP 15s"
    }]
    sale = create_sale_or_quote(
        user_id=admin_user.id,
        customer_id=cust.id,
        sale_type='sale',
        due_date=date.today(),
        items_data=items
    )
    db.session.commit()

    # Confirmação com sinal de 10.000 MT
    confirm_sale(sale.id, admin_user.id, initial_payment={
        'amount': Decimal('10000.00'),
        'payment_method': 'bank_transfer',
        'account_id': acc.id
    })
    db.session.commit()

    assert sale.status == 'partial'
    assert sale.paid_amount == Decimal('10000.00')
    assert sale.balance_due == Decimal('20000.00')

    # Tentativa de pagar mais do que a dívida (ex: 25.000 MT quando resta 20.000 MT)
    with pytest.raises(PaymentError) as exc_info:
        register_payment(
            amount=Decimal('25000.00'),
            payment_method='bank_transfer',
            account_id=acc.id,
            user_id=admin_user.id,
            sale_id=sale.id
        )
    assert "excede o saldo em dívida" in str(exc_info.value)

    # Segundo pagamento regular de 20.000 MT
    register_payment(
        amount=Decimal('20000.00'),
        payment_method='bank_transfer',
        account_id=acc.id,
        user_id=admin_user.id,
        sale_id=sale.id
    )
    db.session.commit()

    assert sale.status == 'paid'
    assert sale.paid_amount == Decimal('30000.00')
    assert sale.balance_due == Decimal('0.00')


def test_sale_cancellation_restores_stock_and_voids_payments(app, sample_data, admin_user):
    """Testa cancelamento de venda: restituição ao stock e anulação do fluxo de caixa."""
    prod = sample_data['product']
    cust = sample_data['customer']
    acc = sample_data['account_cash']

    # Venda de 2 unidades
    sale = create_sale_or_quote(
        user_id=admin_user.id,
        customer_id=cust.id,
        items_data=[{
            'product_id': prod.id,
            'quantity': 2,
            'unit_price': Decimal('30000.00')
        }]
    )
    confirm_sale(sale.id, admin_user.id, initial_payment={
        'amount': Decimal('60000.00'),
        'payment_method': 'cash',
        'account_id': acc.id
    })
    db.session.commit()

    assert prod.stock_quantity == Decimal('8')

    # Cancelar venda
    cancel_sale(sale.id, admin_user.id, "Cliente desistiu da compra por mudança de planos")
    db.session.commit()

    assert sale.status == 'cancelled'
    # Stock restaurado de 8 para 10
    assert prod.stock_quantity == Decimal('10')

    # Pagamento associado deve estar anulado
    pay = Payment.query.filter_by(sale_id=sale.id).first()
    assert pay.is_cancelled is True
    assert pay.cancellation_reason is not None

    # Movimento financeiro também anulado
    mov = FinancialMovement.query.filter_by(payment_id=pay.id).first()
    assert mov.is_cancelled is True


def test_quote_conversion_to_confirmed_sale(app, sample_data, admin_user):
    """Testa conversão de Orçamento aprovado em Venda formal com baixa de stock."""
    prod = sample_data['product']
    cust = sample_data['customer']
    acc = sample_data['account_bank']

    # 1. Cria Orçamento
    quote = create_sale_or_quote(
        user_id=admin_user.id,
        customer_id=cust.id,
        sale_type='quote',
        items_data=[{
            'product_id': prod.id,
            'quantity': 3,
            'unit_price': Decimal('28000.00'),
            'description': "Proposta com desconto por volume"
        }]
    )
    db.session.commit()

    assert quote.sale_type == 'quote'
    assert quote.total_amount == Decimal('84000.00')
    assert prod.stock_quantity == Decimal('10')  # Orçamento não altera stock

    # 2. Converte orçamento em venda com pagamento integral
    sale = convert_quote_to_sale(
        quote_id=quote.id,
        user_id=admin_user.id,
        initial_payment={
            'amount': Decimal('84000.00'),
            'payment_method': 'bank_transfer',
            'account_id': acc.id
        }
    )
    db.session.commit()

    assert quote.status == 'converted'
    assert sale.sale_type == 'sale'
    assert sale.status == 'paid'
    assert sale.converted_from_quote_id == quote.id
    # Stock abatido de 10 para 7
    assert prod.stock_quantity == Decimal('7')
