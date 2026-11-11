"""
app/models/purchase.py — Modelos de Compra e Itens de Compra
"""

from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class Purchase(db.Model):
    """
    Modelo de compra ao fornecedor.
    
    Estados:
    - draft: Rascunho
    - confirmed: Confirmada (mas não recebida)
    - received: Recebida (stock actualizado)
    - partial: Parcialmente paga
    - paid: Totalmente paga
    - cancelled: Cancelada
    """
    
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    
    # Número do documento do fornecedor (factura, nota de entrega, etc.)
    supplier_document = db.Column(db.String(50), nullable=True)
    
    purchase_date = db.Column(db.Date, nullable=False, index=True)
    expected_delivery_date = db.Column(db.Date, nullable=True)
    received_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    
    status = db.Column(db.String(20), nullable=False, default='draft', index=True)
    
    # Valores financeiros
    subtotal = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    shipping_cost = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    paid_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    notes = db.Column(db.Text, nullable=True)
    
    # Auditoria
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    received_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Evita confirmação duplicada (idempotência)
    confirmation_token = db.Column(db.String(50), unique=True, nullable=True)
    stock_updated = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relacionamentos
    items = db.relationship('PurchaseItem', backref='purchase', lazy='joined',
                            cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='purchase', lazy='dynamic',
                               foreign_keys='Payment.purchase_id')
    stock_movements = db.relationship('StockMovement', backref='purchase', lazy='dynamic',
                                      foreign_keys='StockMovement.purchase_id')
    
    def __repr__(self):
        return f'<Purchase {self.purchase_number}>'
    
    @property
    def pending_amount(self):
        """Valor ainda por pagar ao fornecedor."""
        total = Decimal(str(self.total_amount or 0))
        paid = Decimal(str(self.paid_amount or 0))
        return float(total - paid)
    
    @property
    def is_overdue(self):
        """Verifica se a compra a crédito está vencida."""
        if self.due_date and self.pending_amount > 0:
            from datetime import date
            return date.today() > self.due_date
        return False
    
    def recalculate_totals(self):
        """Recalcula os totais com base nos itens."""
        subtotal = sum(
            Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
            for item in self.items
        )
        self.subtotal = subtotal
        self.total_amount = (
            subtotal
            - Decimal(str(self.discount_amount or 0))
            + Decimal(str(self.tax_amount or 0))
            + Decimal(str(self.shipping_cost or 0))
        )
    
    def to_dict(self):
        return {
            'id': self.id,
            'purchase_number': self.purchase_number,
            'supplier_id': self.supplier_id,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'status': self.status,
            'total_amount': float(self.total_amount or 0),
            'paid_amount': float(self.paid_amount or 0),
            'pending_amount': self.pending_amount,
        }


class PurchaseItem(db.Model):
    """Linha de item de uma compra."""
    
    __tablename__ = 'purchase_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    description = db.Column(db.String(250), nullable=True)
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    unit_price = db.Column(db.Numeric(15, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # Quantidade já recebida (para recepção parcial)
    received_quantity = db.Column(db.Numeric(15, 3), nullable=False, default=0)
    
    @property
    def line_total(self):
        qty = Decimal(str(self.quantity or 0))
        price = Decimal(str(self.unit_price or 0))
        discount = Decimal(str(self.discount_amount or 0))
        return float(qty * price - discount)
    
    def __repr__(self):
        return f'<PurchaseItem product_id={self.product_id} qty={self.quantity}>'
