"""
app/models/sale.py — Modelos de Venda e Orçamento

Define vendas, linhas de venda e orçamentos.
Garante integridade financeira em todas as operações.
"""

from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class Sale(db.Model):
    """
    Modelo de venda do TechNexus.
    
    Estados possíveis:
    - draft: Rascunho (ainda não confirmada)
    - confirmed: Confirmada e stock actualizado
    - partial: Parcialmente paga
    - paid: Totalmente paga
    - cancelled: Cancelada (com registo de auditoria)
    - returned: Devolvida
    """
    
    __tablename__ = 'sales'
    
    # ==========================================
    # Identificação
    # ==========================================
    id = db.Column(db.Integer, primary_key=True)
    sale_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # ==========================================
    # Dados da venda
    # ==========================================
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    sale_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=True)  # Data de vencimento (crédito)
    
    # Tipo: 'sale' ou 'quote' (orçamento)
    sale_type = db.Column(db.String(10), nullable=False, default='sale')
    
    # Estado da operação
    status = db.Column(db.String(20), nullable=False, default='draft', index=True)
    
    # ==========================================
    # Valores financeiros (em NUMERIC para precisão)
    # ==========================================
    subtotal = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # Valores de pagamento
    paid_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # Custo total dos produtos (para calcular CPV e lucro bruto)
    total_cost = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # ==========================================
    # Pagamento
    # ==========================================
    payment_method = db.Column(db.String(30), nullable=True)
    
    # ==========================================
    # Informações adicionais
    # ==========================================
    notes = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    
    # Para orçamentos: data de expiração
    quote_expires_at = db.Column(db.Date, nullable=True)
    
    # ==========================================
    # Auditoria
    # ==========================================
    registered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Para cancelamentos
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cancellation_reason = db.Column(db.String(250), nullable=True)
    
    # Para conversão de orçamento em venda
    converted_from_quote_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    
    # ==========================================
    # Relacionamentos
    # ==========================================
    items = db.relationship('SaleItem', backref='sale', lazy='joined',
                            cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='sale', lazy='dynamic',
                               foreign_keys='Payment.sale_id')
    stock_movements = db.relationship('StockMovement', backref='sale', lazy='dynamic',
                                      foreign_keys='StockMovement.sale_id')
    
    def __repr__(self):
        return f'<Sale {self.sale_number}>'
    
    @property
    def pending_amount(self):
        """Valor ainda por receber."""
        total = Decimal(str(self.total_amount or 0))
        paid = Decimal(str(self.paid_amount or 0))
        return float(total - paid)

    @property
    def balance_due(self):
        """Saldo pendente em formato Decimal preciso."""
        total = Decimal(str(self.total_amount or 0))
        paid = Decimal(str(self.paid_amount or 0))
        return total - paid
    
    @property
    def gross_profit(self):
        """
        Lucro bruto da venda.
        Fórmula: total da venda - custo total dos produtos - descontos
        """
        total = Decimal(str(self.total_amount or 0))
        cost = Decimal(str(self.total_cost or 0))
        return total - cost
    
    @property
    def gross_margin_percent(self):
        """Margem bruta em percentagem."""
        total = Decimal(str(self.total_amount or 0))
        if total == 0:
            return None
        profit = Decimal(str(self.gross_profit))
        return float(profit / total * 100)
    
    @property
    def is_fully_paid(self):
        """Verifica se a venda está completamente paga."""
        return Decimal(str(self.paid_amount or 0)) >= Decimal(str(self.total_amount or 0))
    
    @property
    def is_overdue(self):
        """Verifica se a venda a crédito está vencida."""
        if self.due_date and not self.is_fully_paid:
            from datetime import date
            return date.today() > self.due_date
        return False
    
    def recalculate_totals(self):
        """
        Recalcula os totais da venda com base nos itens.
        Deve ser chamado sempre que os itens são alterados.
        """
        subtotal = Decimal('0')
        total_cost = Decimal('0')
        
        for item in self.items:
            subtotal += Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
            total_cost += Decimal(str(item.quantity)) * Decimal(str(item.unit_cost or 0))
        
        self.subtotal = subtotal
        self.total_cost = total_cost
        
        # Aplica desconto
        discount = Decimal(str(self.discount_amount or 0))
        if self.discount_percent and self.discount_percent > 0:
            discount = subtotal * Decimal(str(self.discount_percent)) / 100
            self.discount_amount = discount
        
        # Total final (sem IVA por defeito)
        self.total_amount = subtotal - discount + Decimal(str(self.tax_amount or 0))
    
    def to_dict(self):
        return {
            'id': self.id,
            'sale_number': self.sale_number,
            'customer_id': self.customer_id,
            'sale_date': self.sale_date.isoformat() if self.sale_date else None,
            'status': self.status,
            'total_amount': float(self.total_amount or 0),
            'paid_amount': float(self.paid_amount or 0),
            'pending_amount': self.pending_amount,
            'gross_profit': self.gross_profit,
        }


class SaleItem(db.Model):
    """Linha de item de uma venda (produto ou serviço)."""
    
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    
    # Produto (null se for serviço puro)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    
    # Serviço (null se for produto puro)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    
    # Descrição do item (pode ser diferente do nome do produto/serviço)
    description = db.Column(db.String(250), nullable=False)
    
    quantity = db.Column(db.Numeric(15, 3), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(15, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(15, 2), nullable=True, default=0)  # Para CPV
    discount_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    @property
    def line_total(self):
        """Total da linha: quantidade × preço unitário - desconto."""
        qty = Decimal(str(self.quantity or 0))
        price = Decimal(str(self.unit_price or 0))
        discount = Decimal(str(self.discount_amount or 0))
        return float(qty * price - discount)
    
    @property
    def line_cost(self):
        """Custo total da linha."""
        qty = Decimal(str(self.quantity or 0))
        cost = Decimal(str(self.unit_cost or 0))
        return float(qty * cost)
    
    def __repr__(self):
        return f'<SaleItem {self.description} × {self.quantity}>'
