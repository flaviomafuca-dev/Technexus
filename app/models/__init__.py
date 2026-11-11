"""
app/models/__init__.py — Exportação centralizada de todos os modelos

Importa todos os modelos para que o Flask-Migrate os detecte
e possa gerar as migrações correctas.
"""

# Utilizadores e autenticação
from app.models.user import User

# Entidades comerciais
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.employee import Employee

# Produtos e stock
from app.models.product import (
    Category,
    Brand,
    Product,
    ProductSerialNumber,
    StockMovement
)

# Operações comerciais
from app.models.sale import Sale, SaleItem
from app.models.purchase import Purchase, PurchaseItem
from app.models.payment import Payment

# Serviços técnicos
from app.models.service import (
    ServiceCategory,
    Service,
    ServiceOrder,
    ServiceOrderMaterial,
    ServiceOrderStatusHistory
)

# Finanças
from app.models.finance import (
    FinancialAccount,
    FinancialMovement,
    ExpenseCategory,
    Expense,
    RecurringExpense,
    Contract
)

# Sistema
from app.models.notification import (
    Notification,
    AuditLog,
    AppSettings,
    AIConversation
)

# Lista de todos os modelos (útil para scripts de inicialização)
__all__ = [
    'User',
    'Customer',
    'Supplier', 
    'Employee',
    'Category',
    'Brand',
    'Product',
    'ProductSerialNumber',
    'StockMovement',
    'Sale',
    'SaleItem',
    'Purchase',
    'PurchaseItem',
    'Payment',
    'ServiceCategory',
    'Service',
    'ServiceOrder',
    'ServiceOrderMaterial',
    'ServiceOrderStatusHistory',
    'FinancialAccount',
    'FinancialMovement',
    'ExpenseCategory',
    'Expense',
    'RecurringExpense',
    'Contract',
    'Notification',
    'AuditLog',
    'AppSettings',
    'AIConversation',
]
