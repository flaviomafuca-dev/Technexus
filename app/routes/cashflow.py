"""
app/routes/cashflow.py — Gestão de Caixa, Bancos, Carteiras Móveis e Fluxo de Caixa Real
"""

from decimal import Decimal
from datetime import datetime, date, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.finance import FinancialAccount, FinancialMovement
from app.services.financial_calculations import calculate_cash_flow, get_period_dates
from app.utils.permissions import admin_required
from app.utils.audit import log_action

cashflow_bp = Blueprint('cashflow', __name__)


@cashflow_bp.route('/')
@login_required
@admin_required
def index():
    """Painel de contas financeiras, saldos reais e conciliação de fluxo de caixa."""
    period = request.args.get('period', 'month')
    start_date, end_date = get_period_dates(period)

    accounts = FinancialAccount.query.filter_by(is_active=True).all()
    accounts_data = []
    total_liquidity = 0

    for acc in accounts:
        bal = acc.get_current_balance()
        total_liquidity += bal
        accounts_data.append({
            'account': acc,
            'current_balance': bal
        })

    flow = calculate_cash_flow(start_date, end_date)

    recent_movements = FinancialMovement.query.filter_by(
        is_cancelled=False
    ).order_by(FinancialMovement.movement_date.desc(), FinancialMovement.id.desc()).limit(20).all()

    return render_template(
        'cashflow/index.html',
        accounts_data=accounts_data,
        total_liquidity=total_liquidity,
        flow=flow,
        recent_movements=recent_movements,
        period=period,
        start_date=start_date,
        end_date=end_date
    )


@cashflow_bp.route('/conta/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def create_account():
    """Cria uma nova conta financeira (Caixa, Banco, M-Pesa, e-Mola)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        account_type = request.form.get('account_type', 'cash')
        opening_balance = Decimal(request.form.get('opening_balance', '0') or '0')
        notes = request.form.get('notes', '').strip()

        if not name:
            flash("O nome da conta é obrigatório.", "warning")
            return redirect(url_for('cashflow.create_account'))

        account = FinancialAccount(
            name=name,
            account_type=account_type,
            opening_balance=opening_balance,
            opening_date=date.today(),
            notes=notes,
            is_active=True,
            created_by=current_user.id
        )
        db.session.add(account)
        db.session.commit()

        log_action(
            action="create_financial_account",
            description=f"Conta financeira '{account.name}' criada com saldo inicial de {opening_balance:.2f} MT",
            user_id=current_user.id,
            entity_type="FinancialAccount",
            entity_id=account.id
        )

        flash(f"Conta '{name}' criada com sucesso!", "success")
        return redirect(url_for('cashflow.index'))

    return render_template('cashflow/account_form.html')


@cashflow_bp.route('/transferencia', methods=['GET', 'POST'])
@login_required
@admin_required
def transfer():
    """
    Efetua transferência de dinheiro entre contas da própria empresa.
    Gera movimento de saída na conta de origem e entrada na conta de destino.
    NÃO afeta o lucro nem gera receita ou despesa operacional.
    """
    if request.method == 'POST':
        source_id = request.form.get('source_account_id', type=int)
        target_id = request.form.get('target_account_id', type=int)
        amount = Decimal(request.form.get('amount', '0') or '0')
        notes = request.form.get('notes', '').strip()

        if not source_id or not target_id or source_id == target_id:
            flash("Selecione contas de origem e destino distintas.", "warning")
            return redirect(url_for('cashflow.transfer'))

        if amount <= Decimal('0'):
            flash("O montante de transferência deve ser superior a zero.", "warning")
            return redirect(url_for('cashflow.transfer'))

        source_acc = FinancialAccount.query.get_or_404(source_id)
        target_acc = FinancialAccount.query.get_or_404(target_id)

        source_bal = Decimal(str(source_acc.get_current_balance()))
        if amount > source_bal:
            flash(f"Saldo insuficiente na conta de origem '{source_acc.name}' ({source_bal:.2f} MT).", "danger")
            return redirect(url_for('cashflow.transfer'))

        today_dt = date.today()

        # 1. Movimento de saída na origem
        mov_out = FinancialMovement(
            account_id=source_acc.id,
            movement_type='out',
            amount=amount,
            movement_date=today_dt,
            category='internal_transfer',
            description=f"Transferência enviada para '{target_acc.name}'",
            transfer_account_id=target_acc.id,
            is_transfer=True,
            created_by=current_user.id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(mov_out)
        db.session.flush()

        # 2. Movimento de entrada no destino
        mov_in = FinancialMovement(
            account_id=target_acc.id,
            movement_type='in',
            amount=amount,
            movement_date=today_dt,
            category='internal_transfer',
            description=f"Transferência recebida de '{source_acc.name}'",
            transfer_account_id=source_acc.id,
            paired_movement_id=mov_out.id,
            is_transfer=True,
            created_by=current_user.id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(mov_in)
        db.session.flush()

        mov_out.paired_movement_id = mov_in.id
        db.session.commit()

        log_action(
            action="transfer_between_accounts",
            description=f"Transferência interna de {amount:.2f} MT de '{source_acc.name}' para '{target_acc.name}'",
            user_id=current_user.id,
            entity_type="FinancialMovement",
            entity_id=mov_out.id,
            reason=notes
        )

        flash(f"Transferência de {amount:.2f} MT concluída com sucesso!", "success")
        return redirect(url_for('cashflow.index'))

    accounts = FinancialAccount.query.filter_by(is_active=True).all()
    return render_template('cashflow/transfer.html', accounts=accounts)
