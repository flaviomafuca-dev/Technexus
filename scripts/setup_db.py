"""
scripts/setup_db.py — Script de Inicialização da Base de Dados e Dados Iniciais

Executa:
1. Criação de todas as tabelas do TechNexus.
2. Criação do primeiro utilizador Administrador se ainda não existir.
3. Criação de contas financeiras essenciais para o contexto de Moçambique (Caixa, BIM, M-Pesa).
4. Criação de categorias base de produtos e despesas.
5. Registo de serviços técnicos padrão.
"""

import sys
import os
from decimal import Decimal
from datetime import date, datetime, timezone

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.finance import FinancialAccount, ExpenseCategory
from app.models.product import Category, Brand
from app.models.service import Service, ServiceCategory


def init_database():
    app = create_app()
    with app.app_context():
        print("[CONFIG] A criar tabelas na base de dados...")
        db.create_all()
        print("[OK] Tabelas criadas com sucesso.")

        # 1. Primeiro Administrador
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin_user = os.environ.get('INITIAL_ADMIN_USER', 'admin')
            admin_email = os.environ.get('INITIAL_ADMIN_EMAIL', 'admin@technexus.co.mz')
            admin_pass = os.environ.get('INITIAL_ADMIN_PASSWORD', 'Admin@TechNexus2026!')
            
            admin = User(
                full_name="Administrador do Sistema",
                username=admin_user,
                email=admin_email,
                role='admin',
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            admin.set_password(admin_pass)
            db.session.add(admin)
            print(f"[ADMIN] Administrador inicial criado: {admin_user} / {admin_email}")
        else:
            print("[INFO] Administrador ja existente na base de dados.")

        # 2. Contas Financeiras Padrao de Mocambique
        if FinancialAccount.query.count() == 0:
            accounts = [
                ("Caixa Geral em Especie", "cash", Decimal('5000.00')),
                ("Conta Millennium BIM", "bank", Decimal('50000.00')),
                ("M-Pesa Empresarial", "mpesa", Decimal('15000.00')),
                ("e-Mola Empresarial", "emola", Decimal('5000.00'))
            ]
            for name, acc_type, bal in accounts:
                acc = FinancialAccount(
                    name=name,
                    account_type=acc_type,
                    opening_balance=bal,
                    opening_date=date.today(),
                    is_active=True
                )
                db.session.add(acc)
            print("[FINANCE] Contas financeiras iniciais criadas (Caixa, BIM, M-Pesa, e-Mola).")

        # 3. Categorias de Despesas Padrao
        if ExpenseCategory.query.count() == 0:
            expense_cats = [
                "Renda do Escritorio e Armazem",
                "Salarios e Remuneracoes",
                "Energia Eletrica (EDM Credelec)",
                "Agua e Saneamento",
                "Internet e Comunicacoes (Vodacom/Movitel)",
                "Combustivel e Manutencao de Viaturas",
                "Material de Limpeza e Escritorio",
                "Alimentacao da Equipa",
                "Taxas, Impostos e Licencas",
                "Marketing e Publicidade"
            ]
            for ec in expense_cats:
                db.session.add(ExpenseCategory(name=ec, is_active=True))
            print("[DESPESAS] Categorias de despesas operacionais criadas.")

        # 4. Categorias de Produtos
        if Category.query.count() == 0:
            prod_cats = [
                "Computadores Portateis (Laptops)",
                "Computadores de Secretaria (Desktops)",
                "Servidores & Armazenamento",
                "Monitores & Displays",
                "Impressoras & Consumiveis (Toners)",
                "Redes & Conetividade (Routers/Switches)",
                "Componentes (RAM, SSD, Fontes)",
                "Acessorios (Teclados, Ratos, Cabos)",
                "Seguranca Eletronica & CFTV"
            ]
            for pc in prod_cats:
                db.session.add(Category(name=pc, is_active=True))
            print("[PRODUTOS] Categorias de produtos informaticos criadas.")

        # 5. Marcas Padrao
        if Brand.query.count() == 0:
            brands = ["HP", "Dell", "Lenovo", "Asus", "Acer", "Cisco", "TP-Link", "Epson", "Canon", "Hikvision", "Kingston"]
            for b in brands:
                db.session.add(Brand(name=b, is_active=True))
            print("[MARCAS] Marcas de tecnologia criadas.")

        # 6. Servicos Tecnicos de Referencia
        if Service.query.count() == 0:
            services = [
                ("Diagnostico & Orcamento Tecnico", Decimal('500.00'), Decimal('100.00'), 1.0),
                ("Formatacao & Instalacao de Sistema Operativo", Decimal('1500.00'), Decimal('300.00'), 2.0),
                ("Limpeza Interna & Troca de Massa Termica", Decimal('1200.00'), Decimal('250.00'), 1.5),
                ("Substituicao de Ecra / Teclado de Portatil", Decimal('2000.00'), Decimal('400.00'), 2.0),
                ("Reparacao Eletronica de Motherboard", Decimal('3500.00'), Decimal('800.00'), 3.0),
                ("Instalacao & Configuracao de Rede Wi-Fi / LAN", Decimal('4500.00'), Decimal('1000.00'), 4.0),
                ("Instalacao de Sistema de Camaras CFTV (4 Pontos)", Decimal('8000.00'), Decimal('2000.00'), 6.0)
            ]
            for sname, sref, scost, shours in services:
                db.session.add(Service(
                    name=sname,
                    reference_price=sref,
                    estimated_cost=scost,
                    estimated_hours=shours,
                    is_active=True
                ))
            print("[SERVICOS] Catalogo de servicos de assistencia tecnica inicializado.")

        db.session.commit()
        print("\n[SUCESSO] Base de dados inicializada e pronta para operacao no TechNexus!")


if __name__ == '__main__':
    init_database()
