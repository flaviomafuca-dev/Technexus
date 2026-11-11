"""
app/models/supplier.py — Modelo de Fornecedor
"""

from datetime import datetime, timezone
from app.extensions import db


class Supplier(db.Model):
    """Modelo de fornecedor de produtos e serviços."""
    
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    trade_name = db.Column(db.String(150), nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    phone2 = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(250), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=False, default='Moçambique')
    nuit = db.Column(db.String(20), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)  # Condições de pagamento
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relacionamentos
    purchases = db.relationship('Purchase', backref='supplier', lazy='dynamic',
                                foreign_keys='Purchase.supplier_id')
    products = db.relationship('Product', backref='main_supplier', lazy='dynamic',
                               foreign_keys='Product.supplier_id')
    
    def __repr__(self):
        return f'<Supplier {self.name}>'
    
    def get_total_debt(self):
        """Calcula o total devido ao fornecedor (compras por pagar)."""
        from sqlalchemy import func
        from app.models.purchase import Purchase
        total = db.session.query(
            func.coalesce(func.sum(Purchase.total_amount - Purchase.paid_amount), 0)
        ).filter(
            Purchase.supplier_id == self.id,
            Purchase.status.in_(['confirmed', 'received', 'partial'])
        ).scalar()
        return float(total or 0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'trade_name': self.trade_name,
            'phone': self.phone,
            'email': self.email,
            'nuit': self.nuit,
            'is_active': self.is_active,
        }
