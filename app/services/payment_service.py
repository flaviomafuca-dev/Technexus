"""
app/services/payment_service.py — Serviço Central de Pagamentos e Liquidações

Garante que pagamentos para Vendas, Compras e Despesas:
- Atualizam atómicamente o valor pago e o saldo pendente.
- Geram o movimento correspondente na conta financeira (Caixa, Banco, M-Pesa, e-Mola).
- Validam limites (o pagamento não pode exceder o montante pendente).
- Suportam anulação controlada com reversão do fluxo de caixa e registo de auditoria.
"""

from decimal import Decimal
from datetime import datetime, date, timezone
from app.extensions import db
from app.models.payment import Payment
from app.models.finance import FinancialAccount, FinancialMovement
from app.models.sale import Sale
from app.models.purchase import Purchase
from app.models.finance import Expense
from app.utils.audit import log_action


class PaymentError(Exception):
    """Exceção para erros de validação ou processamento de pagamentos."""
    pass


def register_payment(amount, payment_method, account_id, user_id,
                     sale_id=None, purchase_id=None, expense_id=None,
                     service_order_id=None, reference=None, payment_date=None, notes=None):
    """
    Regista um pagamento atómico no sistema.

    Parâmetros:
        amount: Valor monetário do pagamento
        payment_method: 'cash', 'bank_transfer', 'mpesa', 'emola', 'pos'
        account_id: ID da conta financeira de destino/origem
        user_id: ID do utilizador que processou a operação
        sale_id: ID da venda (recebimento de cliente)
        purchase_id: ID da compra (pagamento a fornecedor)
        expense_id: ID da despesa operacional
        service_order_id: ID da ordem de serviço
        reference: Código de transação M-Pesa / borderô / talão
        payment_date: Data do pagamento (predefinido para hoje)
    """
    pay_amount = Decimal(str(amount))
    if pay_amount <= Decimal('0'):
        raise PaymentError("O montante do pagamento deve ser estritamente positivo.")

    if not payment_date:
        payment_date = date.today()

    account = FinancialAccount.query.get(account_id)
    if not account or not account.is_active:
        raise PaymentError("Conta financeira inválida ou inativa.")

    # 1. Recebimento de Venda
    if sale_id:
        sale = Sale.query.with_for_update().get(sale_id)
        if not sale:
            raise PaymentError(f"Venda ID {sale_id} não encontrada.")
        if sale.status in ('draft', 'cancelled'):
            raise PaymentError(f"Não é possível registar pagamentos numa venda com estado '{sale.status}'.")

        pending = Decimal(str(sale.total_amount)) - Decimal(str(sale.paid_amount or 0))
        if pay_amount > pending:
            raise PaymentError(
                f"O valor de {pay_amount:.2f} MT excede o saldo em dívida da venda ({pending:.2f} MT)."
            )

        sale.paid_amount = Decimal(str(sale.paid_amount or 0)) + pay_amount
        if sale.paid_amount >= Decimal(str(sale.total_amount)):
            sale.status = 'paid'
        else:
            sale.status = 'partial'

        direction = 'in'
        desc = f"Recebimento de Venda {sale.sale_number}"

    # 2. Pagamento de Compra ao Fornecedor
    elif purchase_id:
        purchase = Purchase.query.with_for_update().get(purchase_id)
        if not purchase:
            raise PaymentError(f"Compra ID {purchase_id} não encontrada.")
        if purchase.status in ('draft', 'cancelled'):
            raise PaymentError(f"Não é possível registar pagamentos numa compra com estado '{purchase.status}'.")

        pending = Decimal(str(purchase.total_amount)) - Decimal(str(purchase.paid_amount or 0))
        if pay_amount > pending:
            raise PaymentError(
                f"O valor de {pay_amount:.2f} MT excede o saldo a pagar da compra ({pending:.2f} MT)."
            )

        purchase.paid_amount = Decimal(str(purchase.paid_amount or 0)) + pay_amount
        if purchase.paid_amount >= Decimal(str(purchase.total_amount)):
            purchase.status = 'paid'
        else:
            purchase.status = 'partial'

        direction = 'out'
        desc = f"Pagamento a Fornecedor - Compra {purchase.purchase_number}"

    # 3. Pagamento de Despesa
    elif expense_id:
        expense = Expense.query.with_for_update().get(expense_id)
        if not expense:
            raise PaymentError(f"Despesa ID {expense_id} não encontrada.")
        if expense.status == 'cancelled':
            raise PaymentError("Não é possível registar pagamentos numa despesa cancelada.")

        pending = Decimal(str(expense.amount)) - Decimal(str(expense.paid_amount or 0))
        if pay_amount > pending:
            raise PaymentError(
                f"O valor de {pay_amount:.2f} MT excede o montante pendente da despesa ({pending:.2f} MT)."
            )

        expense.paid_amount = Decimal(str(expense.paid_amount or 0)) + pay_amount
        if expense.paid_amount >= Decimal(str(expense.amount)):
            expense.status = 'paid'

        direction = 'out'
        desc = f"Pagamento de Despesa: {expense.description}"

    else:
        raise PaymentError("O pagamento deve estar associado a uma venda, compra ou despesa.")

    # Criar o registo do pagamento
    payment = Payment(
        reference=reference,
        payment_date=payment_date,
        amount=pay_amount,
        payment_method=payment_method,
        sale_id=sale_id,
        purchase_id=purchase_id,
        expense_id=expense_id,
        service_order_id=service_order_id,
        account_id=account.id,
        direction=direction,
        notes=notes,
        created_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(payment)
    db.session.flush()  # Obtém payment.id

    # Criar o movimento financeiro na conta
    fin_movement = FinancialMovement(
        account_id=account.id,
        movement_type=direction,
        amount=pay_amount,
        movement_date=payment_date,
        category='sale_receipt' if direction == 'in' else 'payment_out',
        description=desc,
        payment_id=payment.id,
        sale_id=sale_id,
        purchase_id=purchase_id,
        expense_id=expense_id,
        is_transfer=False,
        created_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(fin_movement)
    db.session.flush()

    payment.financial_movement_id = fin_movement.id

    log_action(
        action="register_payment",
        description=f"Pagamento registado: {pay_amount:.2f} MT ({direction.upper()}) na conta '{account.name}'",
        user_id=user_id,
        entity_type="Payment",
        entity_id=payment.id
    )

    return payment


def cancel_payment(payment_id, user_id, cancellation_reason):
    """
    Anula de forma controlada um pagamento registado.
    Reverte o montante no documento associado (venda/compra/despesa) e anula o movimento na conta financeira.
    """
    if not cancellation_reason or len(cancellation_reason.strip()) < 5:
        raise PaymentError("Deve especificar um motivo detalhado para a anulação do pagamento.")

    payment = Payment.query.with_for_update().get(payment_id)
    if not payment:
        raise PaymentError("Pagamento não encontrado.")
    if payment.is_cancelled:
        raise PaymentError("Este pagamento já se encontra anulado.")

    pay_amount = Decimal(str(payment.amount))

    # Reverter na Venda
    if payment.sale_id:
        sale = Sale.query.with_for_update().get(payment.sale_id)
        if sale:
            sale.paid_amount = max(Decimal('0'), Decimal(str(sale.paid_amount or 0)) - pay_amount)
            if sale.paid_amount <= Decimal('0'):
                sale.status = 'confirmed'
            else:
                sale.status = 'partial'

    # Reverter na Compra
    elif payment.purchase_id:
        purchase = Purchase.query.with_for_update().get(payment.purchase_id)
        if purchase:
            purchase.paid_amount = max(Decimal('0'), Decimal(str(purchase.paid_amount or 0)) - pay_amount)
            if purchase.paid_amount <= Decimal('0'):
                purchase.status = 'received' if purchase.stock_updated else 'confirmed'
            else:
                purchase.status = 'partial'

    # Reverter na Despesa
    elif payment.expense_id:
        expense = Expense.query.with_for_update().get(payment.expense_id)
        if expense:
            expense.paid_amount = max(Decimal('0'), Decimal(str(expense.paid_amount or 0)) - pay_amount)
            expense.status = 'pending'

    # Anula o pagamento
    payment.is_cancelled = True
    payment.cancelled_at = datetime.now(timezone.utc)
    payment.cancelled_by = user_id
    payment.cancellation_reason = cancellation_reason

    # Anula o movimento financeiro
    if payment.financial_movement_id:
        fin_mov = FinancialMovement.query.get(payment.financial_movement_id)
        if fin_mov:
            fin_mov.is_cancelled = True
            fin_mov.cancelled_at = datetime.now(timezone.utc)
            fin_mov.cancelled_by = user_id
            fin_mov.cancellation_reason = f"Pagamento anulado: {cancellation_reason}"

    log_action(
        action="cancel_payment",
        description=f"Pagamento ID {payment.id} de {pay_amount:.2f} MT anulado",
        user_id=user_id,
        entity_type="Payment",
        entity_id=payment.id,
        reason=cancellation_reason
    )

    return payment
