"""
tests/test_services_and_orders.py — Testes Unitários de Serviços Técnicos e Ordens de Serviço (OS)

Valida:
1. Criação de Ordem de Serviço com registo de equipamento e defeito.
2. Transições de estado (received -> diagnosing -> in_progress -> completed -> delivered).
3. Histórico auditável de mudanças de estado.
4. Consumo de peças do stock da empresa com baixa física e custeio real.
5. Apuração de Lucro Bruto da OS (Preço acordado - Mão de obra - Peças - Outros).
6. Bloqueio de alteração em ordens já concluídas ou canceladas.
"""

from decimal import Decimal
from datetime import date
import pytest
from app.extensions import db
from app.models.service import Service, ServiceOrder, ServiceOrderStatusHistory
from app.models.employee import Employee
from app.services.service_order_service import (
    create_service_order, update_order_status, add_material_to_order, ServiceOrderError
)


def test_create_service_order_and_status_progression(app, sample_data, admin_user):
    """Testa o ciclo de vida de uma Ordem de Serviço Técnica."""
    cust = sample_data['customer']

    # 1. Cria técnico
    tech = Employee(
        name="Mário Cumbane - Técnico Informático",
        email="mario.cumbane@technexus.co.mz",
        role="Técnico de Hardware",
        status="active"
    )
    db.session.add(tech)
    db.session.flush()

    # 2. Abrir Ordem de Serviço
    order = create_service_order(
        user_id=admin_user.id,
        customer_id=cust.id,
        problem_description="Portátil aquece em demasia e desliga ao fim de 15 minutos",
        equipment_type="Laptop",
        equipment_brand="Dell",
        equipment_model="Latitude 5420",
        equipment_serial="DELL-TAG-8822",
        technician_id=tech.id,
        agreed_price=Decimal('3500.00'),
        labor_cost=Decimal('500.00'),
        other_costs=Decimal('100.00'),
        notes="Cliente tem urgência"
    )
    db.session.commit()

    assert order.status == 'received'
    assert order.order_number.startswith('OS-')
    assert order.agreed_price == Decimal('3500.00')

    # Histórico inicial
    history = ServiceOrderStatusHistory.query.filter_by(service_order_id=order.id).all()
    assert len(history) == 1
    assert history[0].new_status == 'received'

    # 3. Transição: Em Diagnóstico
    update_order_status(order.id, 'diagnosing', admin_user.id, "Em bancada para testes de temperatura")
    db.session.commit()
    assert order.status == 'diagnosing'

    # 4. Transição: Em Execução
    update_order_status(order.id, 'in_progress', admin_user.id, "A desmontar para limpeza e substituição de pasta térmica")
    db.session.commit()
    assert order.status == 'in_progress'

    # 5. Transição: Concluído
    update_order_status(order.id, 'completed', admin_user.id, "Testes de carga de 2 horas efetuados com sucesso (máx 65ºC)")
    db.session.commit()
    assert order.status == 'completed'
    assert order.actual_completion_date is not None

    # 6. Transição: Entregue ao Cliente
    update_order_status(order.id, 'delivered', admin_user.id, "Equipamento levantado pelo cliente")
    db.session.commit()
    assert order.status == 'delivered'
    assert order.delivery_date is not None


def test_service_order_material_consumption_and_profitability(app, sample_data, admin_user):
    """Testa consumo de materiais do inventário e apuração rigorosa de lucro da OS."""
    cust = sample_data['customer']
    prod = sample_data['product']  # 10 unid @ custo 20.000 MT

    order = create_service_order(
        user_id=admin_user.id,
        customer_id=cust.id,
        problem_description="Substituição de ecrã avariado",
        equipment_type="Laptop",
        agreed_price=Decimal('25000.00'),
        labor_cost=Decimal('2000.00'),
        other_costs=Decimal('500.00')
    )
    db.session.commit()

    # Consumir 1 peça de stock na OS
    mat = add_material_to_order(
        order_id=order.id,
        user_id=admin_user.id,
        product_id=prod.id,
        quantity=1
    )
    db.session.commit()

    # O stock do produto deve ter reduzido de 10 para 9
    assert prod.stock_quantity == Decimal('9')
    assert mat.stock_deducted is True
    assert mat.unit_cost == Decimal('20000.00')

    # Custo de materiais da OS = 20.000 MT
    assert order.materials_cost == Decimal('20000.00')
    # Custo total da OS = Mão de obra (2.000) + Materiais (20.000) + Outros (500) = 22.500 MT
    assert order.total_cost == Decimal('22500.00')
    # Lucro Bruto da OS = Preço Acordado (25.000) - Custo Total (22.500) = 2.500 MT
    assert order.gross_profit == Decimal('2500.00')
    # Margem Bruta = 2.500 / 25.000 = 10%
    assert float(order.profit_margin) == 10.0


def test_cannot_add_materials_to_completed_or_cancelled_order(app, sample_data, admin_user):
    """Garante que não se pode adicionar peças a ordens já finalizadas."""
    cust = sample_data['customer']
    prod = sample_data['product']

    order = create_service_order(
        user_id=admin_user.id,
        customer_id=cust.id,
        problem_description="Instalação de software"
    )
    update_order_status(order.id, 'completed', admin_user.id)
    db.session.commit()

    with pytest.raises(ServiceOrderError) as exc_info:
        add_material_to_order(
            order_id=order.id,
            user_id=admin_user.id,
            product_id=prod.id,
            quantity=1
        )
    assert "Não é possível adicionar materiais" in str(exc_info.value)
