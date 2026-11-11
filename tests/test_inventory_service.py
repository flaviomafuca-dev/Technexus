"""
tests/test_inventory_service.py — Testes Unitários e de Integração de Gestão de Stock

Valida:
1. Entrada de stock e recálculo do Custo Médio Ponderado Móvel.
2. Saída de stock com atualização de saldo físico.
3. Bloqueio imperativo de stock negativo (salvo override explícito).
4. Ajustes manuais de contagem física (positivos e negativos).
5. Abate de produtos avariados / perdas.
6. Registo de números de série e transição para vendido.
"""

from decimal import Decimal
import pytest
from app.extensions import db
from app.models.product import Product, StockMovement, ProductSerialNumber
from app.services.inventory_service import (
    register_stock_movement, manual_stock_adjustment,
    register_serial_number, mark_serial_sold, InventoryError
)


def test_stock_inflow_and_weighted_average_cost(app, sample_data, admin_user):
    """
    Testa a fórmula do Custo Médio Ponderado Móvel:
    Novo Custo = (Saldo Atual * Custo Atual + Nova Quantidade * Novo Custo) / (Saldo Atual + Nova Quantidade)
    """
    prod = sample_data['product']
    # Inicialmente: 10 unidades @ 20.000 MT = 200.000 MT
    assert prod.stock_quantity == Decimal('10')
    assert prod.average_cost == Decimal('20000.00')

    # Entrada de 10 unidades a 25.000 MT:
    # Novo custo = (10 * 20.000 + 10 * 25.000) / 20 = 450.000 / 20 = 22.500 MT
    mov = register_stock_movement(
        product_id=prod.id,
        movement_type='purchase_in',
        quantity=10,
        unit_cost=Decimal('25000.00'),
        user_id=admin_user.id,
        reason="Recebimento de compra"
    )
    db.session.commit()

    assert prod.stock_quantity == Decimal('20')
    assert prod.average_cost == Decimal('22500.00')
    assert mov.stock_before == Decimal('10')
    assert mov.stock_after == Decimal('20')


def test_stock_outflow_decreases_quantity(app, sample_data, admin_user):
    """Testa se saída de stock diminui saldo e preserva custo médio."""
    prod = sample_data['product']
    initial_cost = prod.average_cost

    mov = register_stock_movement(
        product_id=prod.id,
        movement_type='sale_out',
        quantity=3,
        user_id=admin_user.id,
        reason="Venda ao balcão"
    )
    db.session.commit()

    assert prod.stock_quantity == Decimal('7')
    assert prod.average_cost == initial_cost
    assert mov.quantity == Decimal('3')
    assert mov.stock_after == Decimal('7')


def test_negative_stock_prevention(app, sample_data, admin_user):
    """Garante que tentativa de vender mais que o saldo disponível lança InventoryError."""
    prod = sample_data['product']
    # Saldo atual = 10 unidades

    with pytest.raises(InventoryError) as exc_info:
        register_stock_movement(
            product_id=prod.id,
            movement_type='sale_out',
            quantity=15,  # Excede 10
            user_id=admin_user.id,
            allow_negative=False
        )

    assert "Stock insuficiente" in str(exc_info.value)
    # Garante que o stock não foi alterado
    assert prod.stock_quantity == Decimal('10')


def test_manual_stock_adjustment(app, sample_data, admin_user):
    """Testa inventário físico com retificação para mais e para menos."""
    prod = sample_data['product']

    # Ajuste de 10 para 12 (ajuste positivo de +2)
    mov_in = manual_stock_adjustment(
        product_id=prod.id,
        new_quantity=12,
        user_id=admin_user.id,
        reason="Inventário trimestral - sobra física"
    )
    db.session.commit()
    assert prod.stock_quantity == Decimal('12')
    assert mov_in.movement_type == 'adjustment_in'
    assert mov_in.quantity == Decimal('2')

    # Ajuste de 12 para 8 (ajuste negativo de -4)
    mov_out = manual_stock_adjustment(
        product_id=prod.id,
        new_quantity=8,
        user_id=admin_user.id,
        reason="Inventário trimestral - quebra de stock"
    )
    db.session.commit()
    assert prod.stock_quantity == Decimal('8')
    assert mov_out.movement_type == 'adjustment_out'
    assert mov_out.quantity == Decimal('4')


def test_damaged_goods_write_off(app, sample_data, admin_user):
    """Testa abate de produto danificado."""
    prod = sample_data['product']

    mov = register_stock_movement(
        product_id=prod.id,
        movement_type='damaged',
        quantity=1,
        user_id=admin_user.id,
        reason="Portátil caiu na bancada de trabalho"
    )
    db.session.commit()

    assert prod.stock_quantity == Decimal('9')
    assert mov.movement_type == 'damaged'
    assert mov.quantity == Decimal('1')


def test_serial_number_lifecycle(app, sample_data, admin_user):
    """Testa registo de número de série único e alteração de estado para vendido."""
    prod = sample_data['product']

    # 1. Registo de série
    sn = register_serial_number(prod.id, "HP-SN-998877")
    db.session.commit()
    assert sn.status == 'in_stock'
    assert sn.serial_number == "HP-SN-998877"

    # 2. Tentativa de duplicar o mesmo número de série deve falhar
    with pytest.raises(InventoryError) as exc_info:
        register_serial_number(prod.id, "HP-SN-998877")
    assert "já se encontra registado" in str(exc_info.value)

    # 3. Marcar como vendido
    sold_sn = mark_serial_sold(prod.id, "HP-SN-998877", sale_item_id=1)
    db.session.commit()
    assert sold_sn.status == 'sold'
    assert sold_sn.sale_item_id == 1
