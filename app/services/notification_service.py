"""
app/services/notification_service.py — Serviço de Notificações e Alertas Automáticos

Gera e gere notificações internas no sistema:
- Stock baixo ou esgotado
- Dívidas vencidas de clientes
- Pagamentos a fornecedores próximos ou em atraso
- Ordens de serviço em atraso
- Contratos de manutenção próximos do fim
- Evita duplicação de notificações ativas
"""

from datetime import datetime, date, timedelta, timezone
from app.extensions import db
from app.models.notification import Notification
from app.models.product import Product
from app.models.sale import Sale
from app.models.purchase import Purchase
from app.models.service import ServiceOrder
from app.models.finance import Contract, Expense
from app.models.user import User


def get_unread_count(user_id):
    """Retorna o número de notificações não lidas para o utilizador."""
    if not user_id:
        return 0
    return Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).count()


def create_notification(user_id, notification_type, title, message,
                        priority='medium', link_url=None, reference_type=None,
                        reference_id=None):
    """
    Cria uma notificação caso ainda não exista uma notificação recente não lida
    para a mesma referência.
    """
    if reference_type and reference_id:
        existing = Notification.query.filter_by(
            user_id=user_id,
            notification_type=notification_type,
            reference_type=reference_type,
            reference_id=reference_id,
            is_read=False
        ).first()
        if existing:
            return existing

    notif = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        link_url=link_url,
        reference_type=reference_type,
        reference_id=reference_id,
        is_read=False,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(notif)
    return notif


def check_and_generate_system_alerts():
    """
    Varre o sistema e gera alertas proativos para todos os utilizadores administradores.
    """
    admins = User.query.filter_by(role='admin', is_active=True).all()
    if not admins:
        return 0

    today = date.today()
    generated_count = 0

    # 1. Alertas de Stock Baixo ou Esgotado
    low_stock_products = Product.query.filter(
        Product.is_active == True,
        Product.stock_quantity <= Product.minimum_stock
    ).all()

    for p in low_stock_products:
        is_zero = float(p.stock_quantity or 0) <= 0
        ntype = 'stock_out' if is_zero else 'stock_low'
        prio = 'critical' if is_zero else 'high'
        title = f"{'Stock Esgotado' if is_zero else 'Stock Baixo'}: {p.name}"
        msg = f"O produto '{p.name}' (SKU: {p.sku}) tem {float(p.stock_quantity or 0):.2f} unidades em stock (Mínimo: {float(p.minimum_stock or 0):.2f})."
        
        for admin in admins:
            n = create_notification(
                user_id=admin.id,
                notification_type=ntype,
                title=title,
                message=msg,
                priority=prio,
                link_url=f"/produtos/{p.id}",
                reference_type='Product',
                reference_id=p.id
            )
            if n:
                generated_count += 1

    # 2. Dívidas de Clientes Vencidas
    overdue_sales = Sale.query.filter(
        Sale.status.in_(['confirmed', 'partial']),
        Sale.due_date.isnot(None),
        Sale.due_date < today
    ).all()

    for s in overdue_sales:
        pend = s.pending_amount
        if pend > 0:
            for admin in admins:
                create_notification(
                    user_id=admin.id,
                    notification_type='debt_overdue',
                    title=f"Dívida Vencida: Venda {s.sale_number}",
                    message=f"A venda {s.sale_number} venceu a {s.due_date.strftime('%d/%m/%Y')} com saldo pendente de {pend:.2f} MT.",
                    priority='high',
                    link_url=f"/vendas/{s.id}",
                    reference_type='Sale',
                    reference_id=s.id
                )
                generated_count += 1

    # 3. Ordens de Serviço Atrasadas
    overdue_orders = ServiceOrder.query.filter(
        ServiceOrder.status.in_(['received', 'diagnosing', 'waiting_approval', 'waiting_parts', 'in_progress']),
        ServiceOrder.estimated_completion_date.isnot(None),
        ServiceOrder.estimated_completion_date < today
    ).all()

    for o in overdue_orders:
        for admin in admins:
            create_notification(
                user_id=admin.id,
                notification_type='service_overdue',
                title=f"OS Atrasada: {o.order_number}",
                message=f"A Ordem de Serviço {o.order_number} ultrapassou o prazo de conclusão ({o.estimated_completion_date.strftime('%d/%m/%Y')}).",
                priority='high',
                link_url=f"/ordens-servico/{o.id}",
                reference_type='ServiceOrder',
                reference_id=o.id
            )
            generated_count += 1

    # 4. Contratos Próximos do Fim
    near_contracts = Contract.query.filter(
        Contract.status == 'active',
        Contract.end_date.isnot(None),
        Contract.end_date <= today + timedelta(days=30)
    ).all()

    for c in near_contracts:
        for admin in admins:
            create_notification(
                user_id=admin.id,
                notification_type='contract_expiring',
                title=f"Contrato a Expirar: {c.contract_number}",
                message=f"O contrato '{c.title}' com o cliente vence a {c.end_date.strftime('%d/%m/%Y')}.",
                priority='medium',
                link_url=f"/contratos/{c.id}",
                reference_type='Contract',
                reference_id=c.id
            )
            generated_count += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return generated_count
