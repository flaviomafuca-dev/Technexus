"""
app/models/service.py — Modelos de Serviço e Ordem de Serviço
"""

from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class ServiceCategory(db.Model):
    """Categoria de serviços técnicos."""
    
    __tablename__ = 'service_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(250), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    services = db.relationship('Service', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<ServiceCategory {self.name}>'


class Service(db.Model):
    """
    Catálogo de serviços técnicos disponíveis.
    Ex: Reparação, Manutenção, Instalação, etc.
    """
    
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('service_categories.id'), nullable=True)
    
    # Preço de referência (pode ser ajustado em cada ordem de serviço)
    reference_price = db.Column(db.Numeric(15, 2), nullable=True, default=0)
    
    # Custo estimado de execução
    estimated_cost = db.Column(db.Numeric(15, 2), nullable=True, default=0)
    
    # Tempo estimado em horas
    estimated_hours = db.Column(db.Numeric(8, 2), nullable=True)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relacionamentos
    sale_items = db.relationship('SaleItem', backref='service', lazy='dynamic',
                                 foreign_keys='SaleItem.service_id')
    service_orders = db.relationship('ServiceOrder', backref='service', lazy='dynamic',
                                     foreign_keys='ServiceOrder.service_id')
    
    def __repr__(self):
        return f'<Service {self.name}>'


class ServiceOrder(db.Model):
    """
    Ordem de Serviço (OS) — registo completo de um trabalho técnico.
    
    Estados possíveis:
    - received: Recebido (equipamento na loja)
    - diagnosing: Em diagnóstico
    - waiting_approval: Aguardando aprovação do cliente
    - waiting_parts: Aguardando peças/materiais
    - in_progress: Em execução
    - completed: Concluído (aguardando entrega)
    - delivered: Entregue ao cliente
    - cancelled: Cancelado
    """
    
    __tablename__ = 'service_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Dados do cliente e equipamento
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    
    # Informações do equipamento
    equipment_type = db.Column(db.String(100), nullable=True)
    equipment_brand = db.Column(db.String(100), nullable=True)
    equipment_model = db.Column(db.String(100), nullable=True)
    equipment_serial = db.Column(db.String(100), nullable=True)
    
    # Descrição do problema e diagnóstico
    problem_description = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, nullable=True)
    solution = db.Column(db.Text, nullable=True)
    
    # Estado actual
    status = db.Column(db.String(30), nullable=False, default='received', index=True)
    
    # Datas
    received_date = db.Column(db.Date, nullable=False, index=True)
    estimated_completion_date = db.Column(db.Date, nullable=True)
    actual_completion_date = db.Column(db.Date, nullable=True)
    delivery_date = db.Column(db.Date, nullable=True)
    
    # Técnico responsável
    technician_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Valores financeiros
    labor_cost = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    materials_cost = db.Column(db.Numeric(15, 2), nullable=False, default=0)  # Auto calculado
    other_costs = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    agreed_price = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # Pagamentos
    paid_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # Associação a uma venda (quando a OS é faturada)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    
    notes = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    
    # Auditoria
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relacionamentos
    materials = db.relationship('ServiceOrderMaterial', backref='service_order', lazy='joined',
                                cascade='all, delete-orphan')
    status_history = db.relationship('ServiceOrderStatusHistory', backref='service_order',
                                     lazy='dynamic', order_by='ServiceOrderStatusHistory.created_at')
    payments = db.relationship('Payment', backref='service_order_rel', lazy='dynamic',
                               foreign_keys='Payment.service_order_id')
    
    def __repr__(self):
        return f'<ServiceOrder {self.order_number}>'
    
    @property
    def total_cost(self):
        """Custo total real da ordem de serviço."""
        labor = Decimal(str(self.labor_cost or 0))
        materials = Decimal(str(self.materials_cost or 0))
        other = Decimal(str(self.other_costs or 0))
        return float(labor + materials + other)
    
    @property
    def gross_profit(self):
        """Lucro bruto da ordem de serviço."""
        price = Decimal(str(self.agreed_price or 0))
        cost = Decimal(str(self.total_cost))
        return float(price - cost)
    
    @property
    def pending_amount(self):
        """Valor ainda por receber."""
        price = Decimal(str(self.agreed_price or 0))
        paid = Decimal(str(self.paid_amount or 0))
        return float(price - paid)
    
    @property
    def is_overdue(self):
        """Verifica se a OS está atrasada."""
        if self.estimated_completion_date and self.status not in ('completed', 'delivered', 'cancelled'):
            from datetime import date
            return date.today() > self.estimated_completion_date
        return False

    @property
    def profit_margin(self):
        """Margem bruta em percentagem."""
        price = Decimal(str(self.agreed_price or 0))
        if price == 0:
            return 0.0
        profit = Decimal(str(self.gross_profit))
        return float(profit / price * 100)
    
    def update_materials_cost(self):
        """Recalcula o custo dos materiais com base nos itens usados."""
        mats = ServiceOrderMaterial.query.filter_by(service_order_id=self.id).all()
        if not mats and self.materials:
            mats = self.materials
        total = sum(
            Decimal(str(m.quantity)) * Decimal(str(m.unit_cost or 0))
            for m in mats
        )
        self.materials_cost = total
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'customer_id': self.customer_id,
            'status': self.status,
            'received_date': self.received_date.isoformat() if self.received_date else None,
            'estimated_completion_date': self.estimated_completion_date.isoformat() if self.estimated_completion_date else None,
            'agreed_price': float(self.agreed_price or 0),
            'paid_amount': float(self.paid_amount or 0),
            'total_cost': self.total_cost,
            'gross_profit': self.gross_profit,
        }


class ServiceOrderMaterial(db.Model):
    """Materiais utilizados numa ordem de serviço (saída de stock)."""
    
    __tablename__ = 'service_order_materials'
    
    id = db.Column(db.Integer, primary_key=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey('service_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    
    description = db.Column(db.String(250), nullable=False)
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    unit_cost = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Indica se este material já saiu do stock
    stock_deducted = db.Column(db.Boolean, default=False, nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    @property
    def line_total(self):
        return float(Decimal(str(self.quantity)) * Decimal(str(self.unit_cost)))
    
    def __repr__(self):
        return f'<ServiceOrderMaterial {self.description}>'


class ServiceOrderStatusHistory(db.Model):
    """Histórico de alterações de estado de uma ordem de serviço."""
    
    __tablename__ = 'service_order_status_history'
    
    id = db.Column(db.Integer, primary_key=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey('service_orders.id'), nullable=False)
    
    previous_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    def __repr__(self):
        return f'<StatusHistory {self.previous_status} → {self.new_status}>'
