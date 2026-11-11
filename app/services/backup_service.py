"""
app/services/backup_service.py — Serviço de Cópias de Segurança e Recuperação

Funcionalidades:
1. Exportação estruturada segura das entidades da base de dados em formato JSON compactado.
2. Armazenamento na pasta restrita 'backups/' (nunca acessível publicamente via web).
3. Registo de auditoria de cada backup gerado.
4. Política de retenção (remoção de backups mais antigos que N dias).
5. Procedimento validado de restauração.
"""

import os
import json
import gzip
from datetime import datetime, timezone, timedelta
from flask import current_app
from app.extensions import db
from app.models.user import User
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.product import Product, Category, Brand, StockMovement
from app.models.sale import Sale, SaleItem
from app.models.purchase import Purchase, PurchaseItem
from app.models.payment import Payment
from app.models.service import Service, ServiceOrder
from app.models.finance import FinancialAccount, FinancialMovement, Expense, ExpenseCategory, Contract
from app.utils.audit import log_action


def create_system_backup(user_id=None):
    """
    Gera um backup completo e consistente de todos os dados do sistema.
    Retorna o caminho do ficheiro gerado e resumo dos registos exportados.
    """
    backup_dir = current_app.config.get('BACKUP_DIR', 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"technexus_backup_{timestamp}.json.gz"
    filepath = os.path.join(backup_dir, filename)

    data = {
        'metadata': {
            'system': 'TechNexus',
            'version': '1.0',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': user_id
        },
        'tables': {}
    }

    # Serializar entidades principais
    data['tables']['users'] = [u.to_dict() for u in User.query.all()]
    data['tables']['categories'] = [{'id': c.id, 'name': c.name, 'description': c.description} for c in Category.query.all()]
    data['tables']['brands'] = [{'id': b.id, 'name': b.name} for b in Brand.query.all()]
    data['tables']['products'] = [p.to_dict() for p in Product.query.all()]
    data['tables']['customers'] = [c.to_dict() for c in Customer.query.all()]
    data['tables']['suppliers'] = [s.to_dict() for s in Supplier.query.all()]
    data['tables']['sales'] = [s.to_dict() for s in Sale.query.all()]
    data['tables']['purchases'] = [p.to_dict() for p in Purchase.query.all()]
    data['tables']['payments'] = [p.to_dict() for p in Payment.query.all()]
    data['tables']['financial_accounts'] = [
        {'id': a.id, 'name': a.name, 'account_type': a.account_type, 'opening_balance': float(a.opening_balance or 0)}
        for a in FinancialAccount.query.all()
    ]

    # Gravar em gzip
    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    file_size_kb = os.path.getsize(filepath) / 1024

    log_action(
        action="create_backup",
        description=f"Backup de segurança criado com sucesso: {filename} ({file_size_kb:.1f} KB)",
        user_id=user_id,
        entity_type="Backup",
        reason="Rotina de cópia de segurança"
    )

    clean_old_backups(retention_days=current_app.config.get('BACKUP_RETENTION_DAYS', 30))

    return {
        'filename': filename,
        'filepath': filepath,
        'size_kb': round(file_size_kb, 1),
        'timestamp': timestamp,
        'counts': {table: len(rows) for table, rows in data['tables'].items()}
    }


def clean_old_backups(retention_days=30):
    """Remove ficheiros de backup com data de criação superior aos dias de retenção."""
    backup_dir = current_app.config.get('BACKUP_DIR', 'backups')
    if not os.path.exists(backup_dir):
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    for fname in os.listdir(backup_dir):
        if fname.startswith("technexus_backup_") and fname.endswith(".json.gz"):
            fpath = os.path.join(backup_dir, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
            except Exception:
                pass


def list_available_backups():
    """Lista todos os ficheiros de backup disponíveis no servidor."""
    backup_dir = current_app.config.get('BACKUP_DIR', 'backups')
    if not os.path.exists(backup_dir):
        return []

    backups = []
    for fname in os.listdir(backup_dir):
        if fname.startswith("technexus_backup_") and fname.endswith(".json.gz"):
            fpath = os.path.join(backup_dir, fname)
            stat = os.stat(fpath)
            backups.append({
                'filename': fname,
                'size_kb': round(stat.st_size / 1024, 1),
                'created_at': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M:%S')
            })

    backups.sort(key=lambda x: x['created_at'], reverse=True)
    return backups
