"""
app/models/employee.py — Modelo de Funcionário
"""

from datetime import datetime, timezone
from app.extensions import db


class Employee(db.Model):
    """Funcionário da empresa."""
    
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    
    # Função/cargo
    role = db.Column(db.String(100), nullable=True)
    
    # Conta de utilizador associada (se existir)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, unique=True)
    
    hire_date = db.Column(db.Date, nullable=True)
    
    # 'active', 'inactive', 'terminated'
    status = db.Column(db.String(20), nullable=False, default='active')
    
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relacionamentos
    service_orders = db.relationship('ServiceOrder', backref='technician', lazy='dynamic',
                                     foreign_keys='ServiceOrder.technician_id')
    
    def __repr__(self):
        return f'<Employee {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'role': self.role,
            'status': self.status,
        }
