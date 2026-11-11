"""
app/models/customer.py — Modelo de Cliente

Define a estrutura da tabela de clientes.
Suporta clientes individuais e empresas.
"""

from datetime import datetime, timezone
from app.extensions import db


class Customer(db.Model):
    """
    Modelo de cliente do TechNexus.
    
    Tipos de cliente:
    - individual: Pessoa singular
    - company: Empresa ou pessoa colectiva
    """
    
    __tablename__ = 'customers'
    
    # ==========================================
    # Identificação
    # ==========================================
    id = db.Column(db.Integer, primary_key=True)
    
    # Tipo de cliente: 'individual' ou 'company'
    customer_type = db.Column(db.String(20), nullable=False, default='individual')
    
    # Nome completo (pessoa) ou nome da empresa
    name = db.Column(db.String(150), nullable=False, index=True)
    
    # Nome comercial (para empresas)
    trade_name = db.Column(db.String(150), nullable=True)
    
    # ==========================================
    # Contactos
    # ==========================================
    phone = db.Column(db.String(30), nullable=True)
    phone2 = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True, index=True)
    
    # ==========================================
    # Localização
    # ==========================================
    address = db.Column(db.String(250), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    province = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=False, default='Moçambique')
    
    # ==========================================
    # Dados fiscais
    # ==========================================
    # NUIT — Número Único de Identificação Tributária
    nuit = db.Column(db.String(20), nullable=True, unique=True, index=True)
    
    # ==========================================
    # Estado e informações adicionais
    # ==========================================
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    # Limite de crédito permitido (em MZN)
    credit_limit = db.Column(db.Numeric(15, 2), nullable=True, default=0)
    
    # ==========================================
    # Auditoria
    # ==========================================
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # ==========================================
    # Relacionamentos
    # ==========================================
    sales = db.relationship('Sale', backref='customer', lazy='dynamic',
                            foreign_keys='Sale.customer_id')
    
    service_orders = db.relationship('ServiceOrder', backref='customer', lazy='dynamic',
                                     foreign_keys='ServiceOrder.customer_id')
    
    contracts = db.relationship('Contract', backref='customer', lazy='dynamic',
                                foreign_keys='Contract.customer_id')
    
    def __repr__(self):
        return f'<Customer {self.name}>'
    
    def get_display_name(self):
        """Retorna o nome de apresentação do cliente."""
        if self.trade_name:
            return f"{self.name} ({self.trade_name})"
        return self.name
    
    def get_total_debt(self):
        """
        Calcula o total da dívida actual do cliente.
        Soma os saldos pendentes de todas as vendas e ordens de serviço.
        """
        from sqlalchemy import func
        total_sales_debt = db.session.query(
            func.coalesce(func.sum(Sale.total_amount - Sale.paid_amount), 0)
        ).filter(
            Sale.customer_id == self.id,
            Sale.status.in_(['confirmed', 'partial'])
        ).scalar()
        
        return float(total_sales_debt or 0)
    
    def to_dict(self):
        """Serializa o cliente para dicionário."""
        return {
            'id': self.id,
            'customer_type': self.customer_type,
            'name': self.name,
            'trade_name': self.trade_name,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'city': self.city,
            'nuit': self.nuit,
            'is_active': self.is_active,
            'credit_limit': float(self.credit_limit or 0),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# Importação necessária para o método get_total_debt
from app.models.sale import Sale  # noqa: E402
