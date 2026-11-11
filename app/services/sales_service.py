"""
app/services/sales_service.py — Serviço de Vendas e Orçamentos

Garante que toda a operação de venda:
1. Valida preços e stock disponível.
2. Atualiza o stock com movimento físico e CPV registado.
3. Calcula custos reais e margens.
4. Processa pagamentos iniciais e gera dívida a receber (se venda a crédito/parcial).
5. Opera em transação atómica de base de dados.
"""

from decimal import Decimal
from datetime import datetime, date, timezone
from app.extensions import db
from app.models.sale import Sale, SaleItem
from app.models.product import Product
from app.models.service import Service
from app.services.inventory_service import register_stock_movement, InventoryError
from app.services.payment_service import register_payment
from app.utils.audit import log_action


class SaleError(Exception):
    """Exceção para erros no processo de vendas."""
    pass


def generate_sale_number(is_quote=False):
    """Gera um número sequencial único para a venda ou orçamento."""
    prefix = "ORC" if is_quote else "VND"
    year = date.today().year
    count = Sale.query.filter(
        Sale.sale_type == ('quote' if is_quote else 'sale')
    ).count() + 1
    return f"{prefix}-{year}-{count:05d}"


def create_sale_or_quote(user_id, customer_id=None, sale_type='sale',
                         sale_date=None, due_date=None, discount_amount=0,
                         discount_percent=0, tax_amount=0, notes=None,
                         internal_notes=None, quote_expires_at=None,
                         items_data=None):
    """
    Cria uma nova venda ou orçamento com os seus respetivos itens.
    Se sale_type == 'quote', fica em estado 'draft'.
    Se sale_type == 'sale', é criado como rascunho até confirmação ou pode ser confirmado logo.
    """
    if not items_data:
        raise SaleError("A venda ou orçamento deve conter pelo menos um item.")

    sale_num = generate_sale_number(is_quote=(sale_type == 'quote'))
    if not sale_date:
        sale_date = date.today()

    sale = Sale(
        sale_number=sale_num,
        customer_id=customer_id,
        sale_date=sale_date,
        due_date=due_date,
        sale_type=sale_type,
        status='draft',
        discount_amount=Decimal(str(discount_amount or 0)),
        discount_percent=Decimal(str(discount_percent or 0)),
        tax_amount=Decimal(str(tax_amount or 0)),
        notes=notes,
        internal_notes=internal_notes,
        quote_expires_at=quote_expires_at,
        registered_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(sale)
    db.session.flush()

    # Adicionar itens
    for it in items_data:
        prod_id = it.get('product_id')
        serv_id = it.get('service_id')
        qty = Decimal(str(it.get('quantity', 1)))
        unit_price = Decimal(str(it.get('unit_price', 0)))
        disc_item = Decimal(str(it.get('discount_amount', 0)))
        desc = it.get('description', '')

        unit_cost = Decimal('0')
        if prod_id:
            prod = Product.query.get(prod_id)
            if not prod:
                raise SaleError(f"Produto ID {prod_id} não encontrado.")
            if not desc:
                desc = prod.name
            unit_cost = prod.average_cost or prod.purchase_price or Decimal('0')
        elif serv_id:
            serv = Service.query.get(serv_id)
            if not serv:
                raise SaleError(f"Serviço ID {serv_id} não encontrado.")
            if not desc:
                desc = serv.name
            unit_cost = serv.estimated_cost or Decimal('0')

        item = SaleItem(
            sale_id=sale.id,
            product_id=prod_id,
            service_id=serv_id,
            description=desc,
            quantity=qty,
            unit_price=unit_price,
            unit_cost=unit_cost,
            discount_amount=disc_item
        )
        db.session.add(item)

    db.session.flush()
    sale.recalculate_totals()

    log_action(
        action=f"create_{sale_type}",
        description=f"{'Orçamento' if sale_type == 'quote' else 'Venda'} {sale.sale_number} criado no valor de {sale.total_amount:.2f} MT",
        user_id=user_id,
        entity_type="Sale",
        entity_id=sale.id
    )

    return sale


def confirm_sale(sale_id, user_id, initial_payment=None):
    """
    Confirma uma venda de forma atómica:
    1. Valida e baixa o stock de cada produto vendido.
    2. Regista o custo exato da venda com base no custo médio do momento.
    3. Se houver pagamento inicial, processa via payment_service.
    4. Atualiza o status para 'paid' ou 'confirmed'/'partial'.
    """
    sale = Sale.query.with_for_update().get(sale_id)
    if not sale:
        raise SaleError("Venda não encontrada.")
    if sale.sale_type != 'sale':
        raise SaleError("Apenas registos de venda podem ser confirmados diretamente.")
    if sale.status != 'draft':
        raise SaleError(f"Esta venda já se encontra no estado '{sale.status}'.")

    # 1. Validar e abater stock
    total_cost = Decimal('0')
    for item in sale.items:
        if item.product_id:
            # Baixa de stock
            try:
                movement = register_stock_movement(
                    product_id=item.product_id,
                    movement_type='sale_out',
                    quantity=item.quantity,
                    user_id=user_id,
                    sale_id=sale.id,
                    reason=f"Venda confirmada: {sale.sale_number}"
                )
                # Guarda o custo unitário efectivo na linha de venda
                item.unit_cost = movement.unit_cost
                total_cost += Decimal(str(item.quantity)) * Decimal(str(movement.unit_cost or 0))
            except InventoryError as e:
                raise SaleError(str(e))
        else:
            total_cost += Decimal(str(item.quantity)) * Decimal(str(item.unit_cost or 0))

    sale.total_cost = total_cost
    sale.confirmed_at = datetime.now(timezone.utc)
    sale.confirmed_by = user_id
    sale.status = 'confirmed'

    # 2. Processar pagamento inicial se existir
    if initial_payment and initial_payment.get('amount'):
        pay_amt = Decimal(str(initial_payment['amount']))
        if pay_amt > Decimal('0'):
            register_payment(
                amount=pay_amt,
                payment_method=initial_payment.get('payment_method', 'cash'),
                account_id=initial_payment.get('account_id'),
                user_id=user_id,
                sale_id=sale.id,
                reference=initial_payment.get('reference'),
                notes="Pagamento no acto da venda"
            )

    # Status final
    if sale.paid_amount >= sale.total_amount:
        sale.status = 'paid'
    elif sale.paid_amount > Decimal('0'):
        sale.status = 'partial'

    log_action(
        action="confirm_sale",
        description=f"Venda {sale.sale_number} confirmada. Total: {sale.total_amount:.2f} MT, Custo: {sale.total_cost:.2f} MT, Lucro: {sale.gross_profit:.2f} MT",
        user_id=user_id,
        entity_type="Sale",
        entity_id=sale.id
    )

    return sale


def cancel_sale(sale_id, user_id, cancellation_reason):
    """
    Cancela uma venda confirmada:
    - Devolve os produtos ao stock (movement_type 'return_in').
    - Anula pagamentos associados.
    - Marca venda como 'cancelled'.
    """
    if not cancellation_reason or len(cancellation_reason.strip()) < 5:
        raise SaleError("É obrigatório indicar um motivo detalhado para o cancelamento.")

    sale = Sale.query.with_for_update().get(sale_id)
    if not sale:
        raise SaleError("Venda não encontrada.")
    if sale.status == 'cancelled':
        raise SaleError("A venda já se encontra cancelada.")

    was_confirmed = sale.status in ('confirmed', 'partial', 'paid')

    # Devolver stock se a venda tinha sido confirmada
    if was_confirmed:
        for item in sale.items:
            if item.product_id:
                register_stock_movement(
                    product_id=item.product_id,
                    movement_type='return_in',
                    quantity=item.quantity,
                    user_id=user_id,
                    sale_id=sale.id,
                    unit_cost=item.unit_cost,
                    reason=f"Devolução por cancelamento da venda {sale.sale_number}: {cancellation_reason}"
                )

    # Anular pagamentos activos
    for pay in sale.payments.filter_by(is_cancelled=False).all():
        from app.services.payment_service import cancel_payment
        cancel_payment(pay.id, user_id, f"Cancelamento da venda {sale.sale_number}: {cancellation_reason}")

    sale.status = 'cancelled'
    sale.cancelled_at = datetime.now(timezone.utc)
    sale.cancelled_by = user_id
    sale.cancellation_reason = cancellation_reason

    log_action(
        action="cancel_sale",
        description=f"Venda {sale.sale_number} cancelada. Motivo: {cancellation_reason}",
        user_id=user_id,
        entity_type="Sale",
        entity_id=sale.id,
        reason=cancellation_reason
    )

    return sale


def convert_quote_to_sale(quote_id, user_id, initial_payment=None):
    """
    Converte um orçamento aprovado numa venda formal e confirma a operação.
    Evita duplicação de dados.
    """
    quote = Sale.query.with_for_update().get(quote_id)
    if not quote or quote.sale_type != 'quote':
        raise SaleError("Orçamento não encontrado.")
    if quote.status == 'cancelled':
        raise SaleError("Não é possível aprovar um orçamento cancelado.")

    items_data = []
    for item in quote.items:
        items_data.append({
            'product_id': item.product_id,
            'service_id': item.service_id,
            'description': item.description,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'discount_amount': item.discount_amount
        })

    # Criar a venda formal
    sale = create_sale_or_quote(
        user_id=user_id,
        customer_id=quote.customer_id,
        sale_type='sale',
        sale_date=date.today(),
        due_date=quote.due_date,
        discount_amount=quote.discount_amount,
        discount_percent=quote.discount_percent,
        tax_amount=quote.tax_amount,
        notes=f"Convertido do Orçamento {quote.sale_number}. {quote.notes or ''}",
        items_data=items_data
    )
    sale.converted_from_quote_id = quote.id

    # Confirmar a venda
    confirmed_sale = confirm_sale(sale.id, user_id, initial_payment)

    # Marcar orçamento como aprovado/convertido
    quote.status = 'converted'

    log_action(
        action="convert_quote",
        description=f"Orçamento {quote.sale_number} convertido com sucesso na Venda {confirmed_sale.sale_number}",
        user_id=user_id,
        entity_type="Sale",
        entity_id=confirmed_sale.id
    )

    return confirmed_sale
