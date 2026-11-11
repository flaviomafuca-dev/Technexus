"""
tests/test_auth_and_permissions.py — Testes de Autenticação, Perfis de Utilizador e RBAC

Valida:
1. Hash seguro de palavras-passe (sem texto simples na base de dados).
2. Bloqueio automático de conta após tentativas de autenticação falhadas consecutivas.
3. Proteção RBAC no servidor:
   - Gerente/Vendedor é bloqueado (403 Forbidden) em rotas financeiras restritas e gestão de utilizadores.
   - Administrador tem acesso pleno a todas as áreas operacionais e estratégicas.
   - Utilizador anónimo é redirecionado para a página de login.
4. Salvaguarda crítica: impede a desativação do último Administrador ativo.
5. Fecho definitivo da rota de setup inicial (/auth/setup-admin) assim que o sistema tem utilizadores.
"""

from decimal import Decimal
import pytest
from flask import url_for
from app.extensions import db
from app.models.user import User


def test_password_hashing_security():
    """Garante que palavras-passe são protegidas por hash e nunca salvas em texto simples."""
    user = User(username="seguranca_teste", email="seg@technexus.co.mz")
    raw_pass = "SegredoForte@2026!"
    user.set_password(raw_pass)

    assert user.password_hash != raw_pass
    assert user.password_hash.startswith(('scrypt:', 'pbkdf2:'))
    assert user.check_password(raw_pass) is True
    assert user.check_password("SenhaErrada123") is False


def test_failed_login_lockout(app, db_session):
    """Testa bloqueio temporário após 5 tentativas de login com senha incorreta."""
    user = User(
        full_name="Utilizador Lockout Teste",
        username="lockout_user",
        email="lock@technexus.co.mz",
        role="manager"
    )
    user.set_password("SenhaCorreta123")
    db_session.add(user)
    db_session.commit()

    assert user.is_locked() is False
    assert user.failed_login_attempts == 0

    # 4 falhas consecutivas: ainda não bloqueado
    for _ in range(4):
        user.increment_failed_login(max_attempts=5, lockout_minutes=15)
    db_session.commit()
    assert user.is_locked() is False
    assert user.failed_login_attempts == 4

    # 5ª falha: atinge o limiar e bloqueia
    user.increment_failed_login(max_attempts=5, lockout_minutes=15)
    db_session.commit()
    assert user.is_locked() is True
    assert user.locked_until is not None

    # Registo de login bem sucedido reinicia o contador
    user.record_login(ip_address="127.0.0.1")
    db_session.commit()
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


def test_unauthenticated_user_redirected_to_login(client):
    """Garante que utilizadores não autenticados são barrados em rotas protegidas."""
    response = client.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']

    resp_fin = client.get('/financas/', follow_redirects=False)
    assert resp_fin.status_code == 302
    assert '/auth/login' in resp_fin.headers['Location']


def login_as(client, username, password):
    """Autentica um utilizador através da rota de login."""
    return client.post('/auth/login', data={
        'username': username,
        'password': password
    }, follow_redirects=True)


def test_manager_rbac_restrictions(client, manager_user):
    """
    Regra de Negócio TechNexus:
    O Gerente/Vendedor NÃO pode aceder a relatórios financeiros globais,
    lucro da empresa, nem gestão de utilizadores (deve retornar HTTP 403).
    """
    login_as(client, manager_user.username, "ManagerPass123!")

    # 1. Tentativa de aceder à gestão de utilizadores -> 403 Forbidden
    resp_users = client.get('/utilizadores/')
    assert resp_users.status_code == 403

    # 2. Tentativa de aceder ao módulo financeiro restrito -> 403 Forbidden
    resp_fin = client.get('/financas/')
    assert resp_fin.status_code == 403

    # 3. Tentativa de aceder a despesas recorrentes e confidenciais -> 403 Forbidden
    resp_rec = client.get('/despesas/recorrentes')
    assert resp_rec.status_code == 403

    # 4. Operações permitidas ao gerente (Vendas, Produtos, Clientes) -> 200 OK
    resp_sales = client.get('/vendas/')
    assert resp_sales.status_code == 200

    resp_prods = client.get('/produtos/')
    assert resp_prods.status_code == 200

    resp_custs = client.get('/clientes/')
    assert resp_custs.status_code == 200


def test_admin_full_access(client, admin_user):
    """Administrador possui acesso irrestrito às áreas de gestão e finanças."""
    login_as(client, admin_user.username, "AdminPass123!")

    resp_fin = client.get('/financas/')
    assert resp_fin.status_code == 200

    resp_users = client.get('/utilizadores/')
    assert resp_users.status_code == 200

    resp_settings = client.get('/configuracoes/')
    assert resp_settings.status_code == 200


def test_cannot_deactivate_last_active_admin(client, admin_user, db_session):
    """Regra de Segurança: O sistema não permite a desativação do único administrador ativo."""
    login_as(client, admin_user.username, "AdminPass123!")

    # Tenta desativar o admin_user (único admin)
    response = client.post(f'/utilizadores/{admin_user.id}/estado', follow_redirects=True)
    assert response.status_code == 200
    assert "Não é permitido desativar o único Administrador ativo" in response.get_data(as_text=True)

    # O admin continua ativo
    db_session.refresh(admin_user)
    assert admin_user.is_active is True


def test_setup_admin_disabled_when_users_exist(client, admin_user):
    """Garante que a rota de setup inicial é fechada quando já existe utilizador no sistema."""
    response = client.get('/auth/setup-admin', follow_redirects=False)
    # Deve redirecionar para a página de login com aviso
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']
