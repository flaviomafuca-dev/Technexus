"""
app/services/service_order_service.py — Serviço de Ordens de Serviço Técnicas

Regras de negócio:
1. Controlo de fluxo de assistência técnica (equipamento, diagnóstico, orçamento, execução, entrega).
2. Peças e materiais consumidos do stock com dedução física e registo de custo real (CPV).
3. Histórico auditável de todas as transições de estado.
4. Apuração rigorosa do lucro bruto da assistência técnica (Preço acordado - Mão de obra - Peças - Outros).
"""

from decimal import Decimal
from datetime import datetime, date, timezone
from app.extensions import db
from app.models.service import (
    ServiceOrder, ServiceOrderMaterial, ServiceOrderStatusHistory, Service
)
from app.models.product import Product
from app.models.customer import Customer
from app.models.employee import Employee
from app.services.inventory_service import register_stock_movement, InventoryError
from app.utils.audit import log_action


class ServiceOrderError(Exception):
    """Exceção para erros no fluxo de ordens de serviço."""
    pass


VALID_STATUSES = [
    'received',
    'diagnosing',
    'waiting_approval',
    'waiting_parts',
    'in_progress',
    'completed',
    'delivered',
    'cancelled'
]


def generate_order_number():
    """Gera um número sequencial único para a ordem de serviço."""
    year = date.today().year
    count = ServiceOrder.query.count() + 1
    return f"OS-{year}-{count:05d}"


def create_service_order(user_id, customer_id, problem_description,
                         equipment_type=None, equipment_brand=None,
                         equipment_model=None, equipment_serial=None,
                         service_id=None, technician_id=None,
                         agreed_price=0, labor_cost=0, other_costs=0,
                         estimated_completion_date=None, notes=None):
    """
    Cria uma nova Ordem de Serviço em estado inicial 'received'.
    """
    if not problem_description or len(problem_description.strip()) < 3:
        raise ServiceOrderError("A descrição do problema reportado é obrigatória.")

    customer = Customer.query.get(customer_id)
    if not customer:
        raise ServiceOrderError("Cliente inválido.")

    if technician_id:
        tech = Employee.query.get(technician_id)
        if not tech or tech.status != 'active':
            raise ServiceOrderError("Técnico responsável inválido ou inativo.")

    order_num = generate_order_number()

    order = ServiceOrder(
        order_number=order_num,
        customer_id=customer_id,
        service_id=service_id,
        equipment_type=equipment_type,
        equipment_brand=equipment_brand,
        equipment_model=equipment_model,
        equipment_serial=equipment_serial,
        problem_description=problem_description,
        status='received',
        received_date=date.today(),
        estimated_completion_date=estimated_completion_date,
        technician_id=technician_id,
        assigned_by=user_id,
        agreed_price=Decimal(str(agreed_price or 0)),
        labor_cost=Decimal(str(labor_cost or 0)),
        other_costs=Decimal(str(other_costs or 0)),
        notes=notes,
        created_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(order)
    db.session.flush()

    # Regista histórico inicial
    history = ServiceOrderStatusHistory(
        service_order_id=order.id,
        previous_status=None,
        new_status='received',
        notes="Equipamento recebido na assistência técnica.",
        changed_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(history)

    log_action(
        action="create_service_order",
        description=f"Ordem de Serviço {order.order_number} criada para '{customer.name}'",
        user_id=user_id,
        entity_type="ServiceOrder",
        entity_id=order.id
    )

    return order


def update_order_status(order_id, new_status, user_id, notes=None):
    """
    Atualiza o estado da ordem de serviço com validação e histórico.
    """
    if new_status not in VALID_STATUSES:
        raise ServiceOrderError(f"Estado '{new_status}' inválido para a ordem de serviço.")

    order = ServiceOrder.query.with_for_update().get(order_id)
    if not order:
        raise ServiceOrderError("Ordem de serviço não encontrada.")

    old_status = order.status
    if old_status == new_status:
        return order

    order.status = new_status

    if new_status == 'completed' and not order.actual_completion_date:
        order.actual_completion_date = date.today()
    elif new_status == 'delivered':
        order.delivery_date = date.today()
        if not order.actual_completion_date:
            order.actual_completion_date = date.today()

    history = ServiceOrderStatusHistory(
        service_order_id=order.id,
        previous_status=old_status,
        new_status=new_status,
        notes=notes,
        changed_by=user_id,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(history)

    log_action(
        action="update_service_order_status",
        description=f"Ordem de Serviço {order.order_number}: estado alterado de '{old_status}' para '{new_status}'",
        user_id=user_id,
        entity_type="ServiceOrder",
        entity_id=order.id
    )

    return order


def add_material_to_order(order_id, user_id, quantity, product_id=None,
                          description=None, unit_cost=None):
    """
    Adiciona uma peça ou material à ordem de serviço.
    Se product_id for fornecido, abate fisicamente o stock e captura o custo médio.
    """
    order = ServiceOrder.query.with_for_update().get(order_id)
    if not order:
        raise ServiceOrderError("Ordem de serviço não encontrada.")
    if order.status in ('completed', 'delivered', 'cancelled'):
        raise ServiceOrderError(f"Não é possível adicionar materiais a uma OS com estado '{order.status}'.")

    qty = Decimal(str(quantity))
    if qty <= Decimal('0'):
        raise ServiceOrderError("A quantidade de material deve ser superior a zero.")

    cost = Decimal('0')
    desc = description

    if product_id:
        product = Product.query.with_for_update().get(product_id)
        if not product:
            raise ServiceOrderError(f"Produto ID {product_id} não encontrado.")
        if not desc:
            desc = product.name

        # Abate no stock
        try:
            movement = register_stock_movement(
                product_id=product.id,
                movement_type='service_out',
                quantity=qty,
                user_id=user_id,
                service_order_id=order.id,
                reason=f"Material utilizado na Ordem de Serviço {order.order_number}"
            )
            cost = movement.unit_cost or product.average_cost
        except InventoryError as e:
            raise ServiceOrderError(str(e))
    else:
        if not desc:
            raise ServiceOrderError("Indique uma descrição para o material avulso.")
        cost = Decimal(str(unit_cost or 0))

    material = ServiceOrderMaterial(
        service_order_id=order.id,
        product_id=product_id,
        description=desc,
        quantity=qty,
        unit_cost=cost,
        stock_deducted=(product_id is not None),
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(material)
    db.session.flush()

    if material not in order.materials:
        order.materials.append(material)
    order.update_materials_cost()

    log_action(
        action="add_order_material",
        description=f"Material '{desc}' ({qty:.2f} unid.) adicionado à OS {order.order_number} com custo {cost:.2f} MT",
        user_id=user_id,
        entity_type="ServiceOrder",
        entity_id=order.id
    )

    return material
