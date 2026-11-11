"""
app/services/inventory_service.py — Serviço de Gestão de Stock e Inventário

Implementa as regras de negócio de movimentação de stock:
- Custo médio ponderado móvel
- Bloqueio de stock negativo (salvo configuração explícita)
- Registo atómico de movimentações com histórico detalhado
- Gestão de unidades com número de série
"""

from decimal import Decimal
from datetime import datetime, timezone
from app.extensions import db
from app.models.product import Product, StockMovement, ProductSerialNumber
from app.utils.audit import log_action


class InventoryError(Exception):
    """Exceção base para erros operacionais de inventário."""
    pass


def register_stock_movement(product_id, movement_type, quantity, user_id,
                            unit_cost=None, sale_id=None, purchase_id=None,
                            service_order_id=None, reason=None, notes=None,
                            allow_negative=False):
    """
    Regista uma movimentação física de stock para um determinado produto.

    Tipos suportados:
    - purchase_in (entrada por compra de fornecedor)
    - sale_out (saída por venda a cliente)
    - service_out (saída por material consumido em OS)
    - return_in (entrada por devolução de cliente)
    - return_out (saída por devolução a fornecedor)
    - adjustment_in (ajuste positivo de contagem)
    - adjustment_out (ajuste negativo de contagem)
    - damaged (perda por produto danificado ou defeito)

    Parâmetros:
        product_id: ID do produto
        movement_type: Tipo de movimento
        quantity: Quantidade (valor positivo)
        user_id: ID do utilizador responsável
        unit_cost: Custo unitário no momento
        allow_negative: Se permite saldo final negativo
    """
    qty = Decimal(str(quantity))
    if qty <= Decimal('0'):
        raise InventoryError("A quantidade do movimento deve ser estritamente superior a zero.")

    product = Product.query.with_for_update().get(product_id)
    if not product:
        raise InventoryError(f"Produto ID {product_id} não encontrado.")

    stock_before = Decimal(str(product.stock_quantity or 0))

    # Determinar se o movimento soma ou subtrai do saldo
    inflow_types = {'purchase_in', 'return_in', 'adjustment_in', 'transfer_in'}
    outflow_types = {'sale_out', 'service_out', 'return_out', 'adjustment_out', 'damaged', 'transfer_out'}

    if movement_type in inflow_types:
        stock_after = stock_before + qty
        # Atualiza o custo médio ponderado móvel quando há entrada por compra
        if movement_type == 'purchase_in' and unit_cost is not None:
            product.update_average_cost(new_quantity=qty, new_cost=Decimal(str(unit_cost)))
    elif movement_type in outflow_types:
        stock_after = stock_before - qty
        if stock_after < Decimal('0') and not allow_negative:
            raise InventoryError(
                f"Stock insuficiente para '{product.name}'. "
                f"Disponível: {stock_before:.2f}, Solicitado: {qty:.2f}."
            )
        # Se unit_cost não for especificado na saída, usar o custo médio atual
        if unit_cost is None:
            unit_cost = product.average_cost
    else:
        raise InventoryError(f"Tipo de movimentação desconhecido: '{movement_type}'.")

    # Atualiza o produto
    product.stock_quantity = stock_after

    # Cria o registo de movimentação
    movement = StockMovement(
        product_id=product.id,
        movement_type=movement_type,
        quantity=qty,
        unit_cost=Decimal(str(unit_cost)) if unit_cost is not None else Decimal('0'),
        stock_before=stock_before,
        stock_after=stock_after,
        sale_id=sale_id,
        purchase_id=purchase_id,
        service_order_id=service_order_id,
        reason=reason,
        notes=notes,
        created_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(movement)

    # Regista na auditoria
    log_action(
        action=f"stock_{movement_type}",
        description=f"Movimentação {movement_type}: {qty} unidades de '{product.name}' (Saldo: {stock_before} -> {stock_after})",
        user_id=user_id,
        entity_type='Product',
        entity_id=product.id,
        reason=reason
    )

    return movement


def register_serial_number(product_id, serial_number, purchase_item_id=None):
    """
    Cadastra um número de série único para uma unidade em stock.
    Evita duplicações.
    """
    clean_serial = str(serial_number).strip()
    if not clean_serial:
        raise InventoryError("Número de série não pode ser vazio.")

    existing = ProductSerialNumber.query.filter_by(
        product_id=product_id,
        serial_number=clean_serial
    ).first()

    if existing:
        raise InventoryError(f"O número de série '{clean_serial}' já se encontra registado para este produto.")

    item = ProductSerialNumber(
        product_id=product_id,
        serial_number=clean_serial,
        status='in_stock',
        purchase_item_id=purchase_item_id
    )
    db.session.add(item)
    return item


def mark_serial_sold(product_id, serial_number, sale_item_id):
    """Marca uma unidade com número de série como vendida."""
    clean_serial = str(serial_number).strip()
    unit = ProductSerialNumber.query.filter_by(
        product_id=product_id,
        serial_number=clean_serial,
        status='in_stock'
    ).first()

    if not unit:
        raise InventoryError(f"Unidade com número de série '{clean_serial}' não encontrada ou já indisponível.")

    unit.status = 'sold'
    unit.sale_item_id = sale_item_id
    return unit


def manual_stock_adjustment(product_id, new_quantity, user_id, reason):
    """
    Realiza um ajuste de inventário manual (inventário físico).
    Calcula a diferença e gera a movimentação correspondente.
    """
    product = Product.query.with_for_update().get(product_id)
    if not product:
        raise InventoryError("Produto não encontrado.")

    current_qty = Decimal(str(product.stock_quantity or 0))
    target_qty = Decimal(str(new_quantity))

    if target_qty < Decimal('0'):
        raise InventoryError("A quantidade do inventário não pode ser negativa.")

    diff = target_qty - current_qty
    if diff == Decimal('0'):
        return None  # Nenhuma alteração necessária

    if diff > Decimal('0'):
        movement_type = 'adjustment_in'
        qty = diff
    else:
        movement_type = 'adjustment_out'
        qty = abs(diff)

    return register_stock_movement(
        product_id=product.id,
        movement_type=movement_type,
        quantity=qty,
        user_id=user_id,
        unit_cost=product.average_cost,
        reason=reason or "Ajuste manual de contagem física",
        notes=f"Contagem anterior: {current_qty}, Nova contagem: {target_qty}"
    )
