"""
app/models/finance.py — Modelos Financeiros

Define contas financeiras, movimentos, despesas e contratos recorrentes.
"""

from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class FinancialAccount(db.Model):
    """
    Conta financeira (Caixa, Banco, M-Pesa, e-Mola, etc.).
    Representa um local físico ou virtual onde está o dinheiro.
    """
    
    __tablename__ = 'financial_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    
    # Tipo: 'cash', 'bank', 'mpesa', 'emola', 'other'
    account_type = db.Column(db.String(20), nullable=False, default='cash')
    
    # Saldo inicial (para reconciliação)
    opening_balance = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    opening_date = db.Column(db.Date, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relacionamentos
    movements = db.relationship('FinancialMovement', backref='account', lazy='dynamic',
                                foreign_keys='FinancialMovement.account_id')
    
    def __repr__(self):
        return f'<FinancialAccount {self.name}>'
    
    def get_current_balance(self):
        """
        Calcula o saldo actual da conta.
        Saldo = saldo inicial + entradas - saídas (movimentos não anulados)
        """
        from sqlalchemy import func
        
        total_in = db.session.query(
            func.coalesce(func.sum(FinancialMovement.amount), 0)
        ).filter(
            FinancialMovement.account_id == self.id,
            FinancialMovement.movement_type == 'in',
            FinancialMovement.is_cancelled == False  # noqa: E712
        ).scalar()
        
        total_out = db.session.query(
            func.coalesce(func.sum(FinancialMovement.amount), 0)
        ).filter(
            FinancialMovement.account_id == self.id,
            FinancialMovement.movement_type == 'out',
            FinancialMovement.is_cancelled == False  # noqa: E712
        ).scalar()
        
        opening = Decimal(str(self.opening_balance or 0))
        return float(opening + Decimal(str(total_in)) - Decimal(str(total_out)))


class FinancialMovement(db.Model):
    """
    Movimento financeiro numa conta.
    
    Toda a entrada ou saída de dinheiro deve ter um registo aqui.
    As transferências entre contas criam dois movimentos (saída + entrada).
    """
    
    __tablename__ = 'financial_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('financial_accounts.id'), nullable=False, index=True)
    
    # 'in' = entrada, 'out' = saída
    movement_type = db.Column(db.String(5), nullable=False, index=True)
    
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    movement_date = db.Column(db.Date, nullable=False, index=True)
    
    # Categoria do movimento
    category = db.Column(db.String(50), nullable=True)
    description = db.Column(db.String(250), nullable=False)
    
    # Referências às operações de origem
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=True)
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=True)
    
    # Para transferências entre contas
    transfer_account_id = db.Column(db.Integer, db.ForeignKey('financial_accounts.id'), nullable=True)
    is_transfer = db.Column(db.Boolean, default=False, nullable=False)
    # ID do movimento correspondente na conta destino
    paired_movement_id = db.Column(db.Integer, db.ForeignKey('financial_movements.id'), nullable=True)
    
    # Anulação
    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cancellation_reason = db.Column(db.String(250), nullable=True)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    def __repr__(self):
        return f'<FinancialMovement {self.movement_type} {self.amount} MT>'


class ExpenseCategory(db.Model):
    """Categoria de despesas (Renda, Salários, Internet, etc.)."""
    
    __tablename__ = 'expense_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(250), nullable=True)
    is_confidential = db.Column(db.Boolean, default=False, nullable=False)  # Visível só ao admin
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    expenses = db.relationship('Expense', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'


class Expense(db.Model):
    """
    Despesa operacional da empresa.
    
    Estados:
    - pending: Registada mas não paga
    - paid: Paga
    - overdue: Vencida sem pagamento
    - cancelled: Cancelada
    """
    
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(250), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    
    expense_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    paid_amount = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    payment_method = db.Column(db.String(30), nullable=True)
    
    # Beneficiário (fornecedor ou outra entidade)
    beneficiary = db.Column(db.String(150), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    
    # Comprovativo (nome do ficheiro)
    receipt_file = db.Column(db.String(250), nullable=True)
    
    # Indica se é confidencial (apenas admin pode ver)
    is_confidential = db.Column(db.Boolean, default=False, nullable=False)
    
    # Despesa recorrente associada
    recurring_expense_id = db.Column(db.Integer, db.ForeignKey('recurring_expenses.id'), nullable=True)
    
    notes = db.Column(db.Text, nullable=True)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relacionamentos
    payments = db.relationship('Payment', backref='expense', lazy='dynamic',
                               foreign_keys='Payment.expense_id')
    
    def __repr__(self):
        return f'<Expense {self.description} {self.amount} MT>'
    
    @property
    def pending_amount(self):
        """Valor ainda por pagar."""
        return float(Decimal(str(self.amount or 0)) - Decimal(str(self.paid_amount or 0)))
    
    @property
    def is_overdue(self):
        """Verifica se a despesa está vencida."""
        if self.due_date and self.status != 'paid':
            from datetime import date
            return date.today() > self.due_date
        return False


class RecurringExpense(db.Model):
    """
    Despesa recorrente (compromisso regular).
    Ex: Renda mensal, Internet, Salários.
    
    Periodicidades: daily, weekly, monthly, quarterly, annual
    """
    
    __tablename__ = 'recurring_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(250), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    
    expected_amount = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Periodicidade
    frequency = db.Column(db.String(20), nullable=False, default='monthly')
    
    # Dia do mês para vencimento (1-31)
    due_day = db.Column(db.Integer, nullable=True)
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    
    # Dias de antecedência para alerta
    alert_days_before = db.Column(db.Integer, nullable=False, default=7)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    beneficiary = db.Column(db.String(150), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Despesas geradas por este compromisso
    expenses = db.relationship('Expense', backref='recurring_expense', lazy='dynamic',
                               foreign_keys='Expense.recurring_expense_id')
    
    def __repr__(self):
        return f'<RecurringExpense {self.description} ({self.frequency})>'


class Contract(db.Model):
    """
    Contrato de serviços recorrentes com clientes.
    Ex: Manutenção, Suporte técnico, Gestão de redes.
    """
    
    __tablename__ = 'contracts'
    
    id = db.Column(db.Integer, primary_key=True)
    contract_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    value = db.Column(db.Numeric(15, 2), nullable=False)
    frequency = db.Column(db.String(20), nullable=False, default='monthly')
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    
    # 'active', 'expired', 'cancelled', 'pending'
    status = db.Column(db.String(20), nullable=False, default='active', index=True)
    
    terms = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    alert_days_before = db.Column(db.Integer, nullable=False, default=30)
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    def __repr__(self):
        return f'<Contract {self.contract_number}>'
    
    @property
    def is_near_expiry(self):
        """Verifica se o contrato está próximo do vencimento."""
        if self.end_date and self.status == 'active':
            from datetime import date, timedelta
            alert_date = self.end_date - timedelta(days=self.alert_days_before)
            return date.today() >= alert_date
        return False
