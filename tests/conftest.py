"""
tests/conftest.py — Configuração de Testes Automatizados com Pytest
"""

import os
import sys

# Garante que a raiz do projeto está no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from decimal import Decimal
from datetime import date, datetime, timezone
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.finance import FinancialAccount, ExpenseCategory, Expense
from app.models.product import Product, Category, Brand
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.service import Service, ServiceOrder


@pytest.fixture
def app():
    """Cria a aplicação em modo de testes (TestingConfig com SQLite in-memory)."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente HTTP de teste."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Sessão de base de dados para testes."""
    return db.session


@pytest.fixture
def admin_user(db_session):
    """Cria e retorna um utilizador Administrador."""
    user = User(
        full_name="Administrador de Teste",
        username="admin_test",
        email="admin_test@technexus.co.mz",
        role="admin",
        is_active=True
    )
    user.set_password("AdminPass123!")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def manager_user(db_session):
    """Cria e retorna um utilizador Gerente/Vendedor."""
    user = User(
        full_name="Gerente de Teste",
        username="manager_test",
        email="manager_test@technexus.co.mz",
        role="manager",
        is_active=True
    )
    user.set_password("ManagerPass123!")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_data(db_session, admin_user):
    """Cria dados base para testes: contas, clientes, fornecedores e produtos."""
    account_cash = FinancialAccount(
        name="Caixa Teste",
        account_type="cash",
        opening_balance=Decimal('10000.00'),
        opening_date=date.today(),
        is_active=True
    )
    account_bank = FinancialAccount(
        name="Banco Teste",
        account_type="bank",
        opening_balance=Decimal('50000.00'),
        opening_date=date.today(),
        is_active=True
    )
    db_session.add_all([account_cash, account_bank])

    category = Category(name="Portáteis", is_active=True)
    brand = Brand(name="HP", is_active=True)
    db_session.add_all([category, brand])
    db_session.flush()

    customer = Customer(
        name="Cliente Corporativo Lda",
        customer_type="company",
        phone="+258 84 111 2222",
        nuit="400111222",
        is_active=True
    )
    supplier = Supplier(
        name="Distribuidor Oficial SA",
        phone="+258 21 333 4444",
        nuit="400333444",
        is_active=True
    )
    db_session.add_all([customer, supplier])
    db_session.flush()

    # Produto com stock inicial 10 unid @ custo 20.000, venda 30.000 MT
    product = Product(
        sku="LAP-HP-TEST",
        name="Portátil HP Teste 15s",
        category_id=category.id,
        brand_id=brand.id,
        supplier_id=supplier.id,
        purchase_price=Decimal('20000.00'),
        average_cost=Decimal('20000.00'),
        selling_price=Decimal('30000.00'),
        stock_quantity=Decimal('10'),
        minimum_stock=Decimal('3'),
        is_active=True,
        created_by=admin_user.id
    )
    db_session.add(product)
    db_session.commit()

    return {
        'account_cash': account_cash,
        'account_bank': account_bank,
        'customer': customer,
        'supplier': supplier,
        'product': product
    }
