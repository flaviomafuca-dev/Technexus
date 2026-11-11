"""
app/models/payment.py — Modelo de Pagamento

Regista todos os pagamentos do sistema (vendas e compras).
Suporta pagamentos parciais e múltiplos métodos.
"""

from datetime import datetime, timezone
from app.extensions import db


class Payment(db.Model):
    """
    Modelo de pagamento do TechNexus.
    
    Aplica-se a:
    - Recebimentos de clientes (sale_id preenchido)
    - Pagamentos a fornecedores (purchase_id preenchido)
    - Despesas (expense_id preenchido)
    """
    
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=True, index=True)
    
    # Data efectiva do pagamento
    payment_date = db.Column(db.Date, nullable=False, index=True)
    
    # Valor do pagamento
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Método de pagamento
    payment_method = db.Column(db.String(30), nullable=False)
    
    # Referências às operações relacionadas
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True, index=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=True, index=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True, index=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey('service_orders.id'), nullable=True)
    
    # Conta financeira afectada
    account_id = db.Column(db.Integer, db.ForeignKey('financial_accounts.id'), nullable=True)
    
    # Direcção: 'in' (recebimento) ou 'out' (pagamento)
    direction = db.Column(db.String(5), nullable=False)
    
    notes = db.Column(db.Text, nullable=True)
    
    # Auditoria
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Anulação controlada
    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cancellation_reason = db.Column(db.String(250), nullable=True)
    
    # Relacionamento com o movimento financeiro correspondente
    financial_movement_id = db.Column(
        db.Integer,
        db.ForeignKey('financial_movements.id', use_alter=True, name='fk_payment_fin_movement'),
        nullable=True
    )
    
    def __repr__(self):
        return f'<Payment {self.reference} {self.amount} MT>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount or 0),
            'payment_method': self.payment_method,
            'direction': self.direction,
            'sale_id': self.sale_id,
            'purchase_id': self.purchase_id,
            'expense_id': self.expense_id,
            'is_cancelled': self.is_cancelled,
        }
