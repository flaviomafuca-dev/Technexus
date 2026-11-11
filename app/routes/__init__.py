"""
app/routes/__init__.py — Registo e exportação dos Blueprints de rotas
"""

from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.customers import customers_bp
from app.routes.suppliers import suppliers_bp
from app.routes.products import products_bp
from app.routes.inventory import inventory_bp
from app.routes.sales import sales_bp
from app.routes.purchases import purchases_bp
from app.routes.services import services_bp
from app.routes.service_orders import service_orders_bp
from app.routes.finance import finance_bp
from app.routes.expenses import expenses_bp
from app.routes.cashflow import cashflow_bp
from app.routes.reports import reports_bp
from app.routes.contracts import contracts_bp
from app.routes.employees import employees_bp
from app.routes.ai_assistant import ai_bp
from app.routes.settings import settings_bp
from app.routes.users import users_bp
