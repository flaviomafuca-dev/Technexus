"""
app/services/purchase_service.py — Serviço de Compras a Fornecedores

Garante que:
1. Uma compra em rascunho pode ser editada livremente.
2. A confirmação da compra valida os produtos e custos.
3. A entrada física em stock só acontece no momento da RECEPÇÃO da mercadoria.
4. A recepção de produtos recalcula o Custo Médio Ponderado Móvel.
5. Operações de recepção são idempotentes (protegidas contra duplicação de stock).
6. Gera a obrigação a pagar (contas a pagar a fornecedores).
"""

from decimal import Decimal
from datetime import datetime, date, timezone
import uuid
from app.extensions import db
from app.models.purchase import Purchase, PurchaseItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_service import register_stock_movement, register_serial_number
from app.services.payment_service import register_payment
from app.utils.audit import log_action


class PurchaseError(Exception):
    """Exceção para erros de compras e fornecedores."""
    pass


def generate_purchase_number():
    """Gera número sequencial único para a compra."""
    year = date.today().year
    count = Purchase.query.count() + 1
    return f"CMP-{year}-{count:05d}"


def create_purchase(user_id, supplier_id, purchase_date=None, due_date=None,
                    expected_delivery_date=None, supplier_document=None,
                    discount_amount=0, tax_amount=0, shipping_cost=0,
                    notes=None, items_data=None):
    """
    Cria uma nova ordem de compra em estado 'draft'.
    """
    if not items_data:
        raise PurchaseError("A compra deve conter pelo menos um produto.")

    supplier = Supplier.query.get(supplier_id)
    if not supplier or not supplier.is_active:
        raise PurchaseError("Fornecedor inválido ou inativo.")

    if not purchase_date:
        purchase_date = date.today()

    purchase_num = generate_purchase_number()

    purchase = Purchase(
        purchase_number=purchase_num,
        supplier_id=supplier_id,
        supplier_document=supplier_document,
        purchase_date=purchase_date,
        due_date=due_date,
        expected_delivery_date=expected_delivery_date,
        status='draft',
        discount_amount=Decimal(str(discount_amount or 0)),
        tax_amount=Decimal(str(tax_amount or 0)),
        shipping_cost=Decimal(str(shipping_cost or 0)),
        notes=notes,
        created_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(purchase)
    db.session.flush()

    for it in items_data:
        prod_id = it.get('product_id')
        qty = Decimal(str(it.get('quantity', 1)))
        unit_price = Decimal(str(it.get('unit_price', 0)))
        disc = Decimal(str(it.get('discount_amount', 0)))
        desc = it.get('description')

        prod = Product.query.get(prod_id)
        if not prod:
            raise PurchaseError(f"Produto ID {prod_id} não encontrado.")
        if not desc:
            desc = prod.name

        item = PurchaseItem(
            purchase_id=purchase.id,
            product_id=prod.id,
            description=desc,
            quantity=qty,
            unit_price=unit_price,
            discount_amount=disc,
            received_quantity=Decimal('0')
        )
        db.session.add(item)

    db.session.flush()
    purchase.recalculate_totals()

    log_action(
        action="create_purchase",
        description=f"Compra {purchase.purchase_number} criada para o fornecedor '{supplier.name}' no valor de {purchase.total_amount:.2f} MT",
        user_id=user_id,
        entity_type="Purchase",
        entity_id=purchase.id
    )

    return purchase


def confirm_purchase(purchase_id, user_id):
    """
    Confirma a compra perante o fornecedor (gera a obrigação formal).
    Atenção: A confirmação NÃO introduz mercadorias em stock até à recepção.
    """
    purchase = Purchase.query.with_for_update().get(purchase_id)
    if not purchase:
        raise PurchaseError("Compra não encontrada.")
    if purchase.status != 'draft':
        raise PurchaseError(f"Esta compra já está no estado '{purchase.status}'.")

    purchase.status = 'confirmed'
    purchase.confirmed_at = datetime.now(timezone.utc)

    log_action(
        action="confirm_purchase",
        description=f"Compra {purchase.purchase_number} confirmada.",
        user_id=user_id,
        entity_type="Purchase",
        entity_id=purchase.id
    )

    return purchase


def receive_purchase(purchase_id, user_id, serial_numbers_map=None):
    """
    Regista o recebimento físico dos produtos comprados.
    
    Regras estritas:
    1. Operação atómica e idempotente: se stock_updated for True, não duplica.
    2. Dá entrada de stock (movement_type 'purchase_in').
    3. Atualiza o custo médio ponderado de cada produto.
    4. Se houver controlo por número de série, cadastra cada unidade física.
    """
    purchase = Purchase.query.with_for_update().get(purchase_id)
    if not purchase:
        raise PurchaseError("Compra não encontrada.")
    if purchase.status == 'cancelled':
        raise PurchaseError("Não é possível receber uma compra cancelada.")
    if purchase.stock_updated:
        raise PurchaseError("Esta compra já teve a entrada de stock processada anteriormente.")

    serial_numbers_map = serial_numbers_map or {}

    for item in purchase.items:
        product = Product.query.with_for_update().get(item.product_id)
        if not product:
            continue

        # Entrada no stock com atualização do custo médio ponderado
        register_stock_movement(
            product_id=product.id,
            movement_type='purchase_in',
            quantity=item.quantity,
            user_id=user_id,
            unit_cost=item.unit_price,
            purchase_id=purchase.id,
            reason=f"Recepção da Compra {purchase.purchase_number}"
        )

        item.received_quantity = item.quantity

        # Registar números de série caso o produto tenha essa exigência
        if product.has_serial_number and str(product.id) in serial_numbers_map:
            serials = serial_numbers_map[str(product.id)]
            for sn in serials:
                if sn.strip():
                    register_serial_number(
                        product_id=product.id,
                        serial_number=sn.strip(),
                        purchase_item_id=item.id
                    )

    purchase.stock_updated = True
    purchase.received_at = datetime.now(timezone.utc)
    purchase.received_date = date.today()

    if purchase.paid_amount >= purchase.total_amount:
        purchase.status = 'paid'
    elif purchase.paid_amount > Decimal('0'):
        purchase.status = 'partial'
    else:
        purchase.status = 'received'

    log_action(
        action="receive_purchase",
        description=f"Mercadorias da Compra {purchase.purchase_number} recebidas e introduzidas no stock com recálculo de custo médio.",
        user_id=user_id,
        entity_type="Purchase",
        entity_id=purchase.id
    )

    return purchase
