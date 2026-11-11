"""
app/routes/employees.py — Gestão de Funcionários e Produtividade Técnica
"""

from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.employee import Employee
from app.models.user import User
from app.utils.permissions import admin_required
from app.utils.audit import log_action

employees_bp = Blueprint('employees', __name__)


@employees_bp.route('/')
@login_required
def index():
    """Listagem de funcionários e técnicos."""
    employees_list = Employee.query.order_by(Employee.name).all()
    return render_template('employees/index.html', employees=employees_list, is_admin=current_user.is_admin)


@employees_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Registo de novo funcionário/técnico."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        role = request.form.get('role', 'Técnico de Informática').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        hire_date_str = request.form.get('hire_date')
        hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date() if hire_date_str else date.today()
        user_id = request.form.get('user_id', type=int)
        notes = request.form.get('notes', '').strip()

        if not name:
            flash("O nome do funcionário é obrigatório.", "warning")
            return redirect(url_for('employees.create'))

        emp = Employee(
            name=name,
            role=role,
            phone=phone,
            email=email if email else None,
            hire_date=hire_date,
            user_id=user_id if user_id else None,
            notes=notes,
            status='active',
            created_by=current_user.id
        )
        db.session.add(emp)
        db.session.commit()

        log_action(
            action="create_employee",
            description=f"Funcionário '{emp.name}' cadastrado ({role})",
            user_id=current_user.id,
            entity_type="Employee",
            entity_id=emp.id
        )

        flash(f"Funcionário '{emp.name}' registado com sucesso!", "success")
        return redirect(url_for('employees.index'))

    users = User.query.filter_by(is_active=True).all()
    return render_template('employees/form.html', employee=None, users=users)


@employees_bp.route('/<int:employee_id>')
@login_required
def view(employee_id):
    """Consulta de produtividade e ordens de serviço atribuídas ao funcionário."""
    employee = Employee.query.get_or_404(employee_id)
    orders = employee.service_orders.order_by(db.desc('received_date')).all()

    completed_count = sum(1 for o in orders if o.status in ('completed', 'delivered'))
    pending_count = len(orders) - completed_count

    return render_template(
        'employees/view.html',
        employee=employee,
        orders=orders,
        completed_count=completed_count,
        pending_count=pending_count
    )
