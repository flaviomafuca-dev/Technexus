# TechNexus — Sistema Inteligente de Gestão Empresarial

> **Solução Integral de Gestão Comercial, Serviços Técnicos, Finanças Estratégicas e Inteligência Artificial para Pequenas e Médias Empresas em Moçambique.**

---

## 1. Visão Geral

O **TechNexus** é uma aplicação web empresarial completa, desenvolvida especificamente para empresas do setor tecnológico que comercializam materiais e equipamentos informáticos e prestam assistência técnica e consultoria.

Diferente de protótipos estáticos ou dashboards ilustrativos, o TechNexus opera com **regras financeiras e contabilísticas reais**:
- **Custo Médio Ponderado Móvel (CMPM)** para custeio rigoroso de saídas de stock e determinação exata do CPV (Custo dos Produtos Vendidos).
- **Separação estrita** entre **Receita Reconhecida** (Regime de Competência) e **Recebimentos Reais** (Regime de Caixa).
- **Neutralidade de Fluxo de Caixa**: Transferências entre contas internas da empresa (ex.: Caixa Geral para Millennium BIM ou M-Pesa) preservam o resultado líquido sem inflacionar entradas ou saídas.
- **Rastreabilidade por Número de Série**: Controlo individual de equipamentos e componentes informáticos de alto valor.
- **Ordens de Serviço Técnicas com Custeio Integrado**: Consumo atómico de peças em stock, mão-de-obra e custos acessórios com apuração de margem real por serviço.
- **Assistente Inteligente TechNexus AI**: Integração no backend com a **Google Gemini API** (`gemini-2.0-flash`), munido de fallback local determinístico baseado em inteligência de dados caso a API externa esteja indisponível ou desativada.
- **Segurança e RBAC Server-Side**: Perfis diferenciados para **Administrador** (acesso integral) e **Gerente/Vendedor** (operações de balcão e assistência, sem acesso a margens globais da empresa, relatórios confidenciais ou administração de utilizadores).

---

## 2. Tecnologias Utilizadas

### Backend
- **Python 3.12+**
- **Flask 3.1+** (Application Factory, Blueprints modulares)
- **SQLAlchemy 2.x** & **Flask-SQLAlchemy** (ORM com transações atómicas)
- **Flask-Migrate** / **Alembic** (Gestão de migrações estruturais de base de dados)
- **Flask-Login** (Gestão de sessões com cookies HttpOnly e proteção de força bruta)
- **Flask-WTF** (Validação de formulários e tokens CSRF)
- **Flask-Limiter** (Proteção contra brute-force e rate limiting)
- **Google GenAI SDK** (`google-genai` para assistente Gemini 2.0 Flash)
- **ReportLab** (Geração de relatórios e faturas em PDF de alta qualidade)
- **openpyxl** (Exportação analítica em planilhas Excel `.xlsx`)
- **Pytest** & **pytest-flask** (Conjunto exaustivo de testes automatizados)

### Frontend
- **HTML5 & CSS3** com variáveis CSS personalizadas
- **Bootstrap 5.3** (Design responsivo adaptado para Desktop, Tablet e Telemóvel)
- **Bootstrap Icons**
- **Chart.js** (Gráficos dinâmicos de fluxo de caixa, rentabilidade e tendências)
- **Vanilla JavaScript** (Sem frameworks pesados, foco em desempenho e estabilidade)

### Base de Dados
- **PostgreSQL 15+** (Alojado em **Supabase** para produção)
- **SQLite local** (Fallback transparente em desenvolvimento e testes em memória)

---

## 3. Contexto Empresarial Moçambicano

O sistema está configurado de raiz para a realidade de Moçambique:
- **Moeda Principal**: Metical Moçambicano (`MZN` / `MT`).
- **Formatação Monetária**: `125 000,00 MT` (conforme padrão local).
- **Fuso Horário**: `Africa/Maputo` (CAT - UTC+2).
- **Identificação Fiscal**: Validação e registo de NUIT (Número Único de Identificação Tributária) em Clientes e Fornecedores.
- **Canais Financeiros Nativos**: Suporte a Caixas em numerário, Contas Bancárias (Millennium BIM, BCI, Standard Bank, Absa, Moza Banco) e Carteiras Móveis (**M-Pesa**, **e-Mola**).

---

## 4. Estrutura do Projeto

```text
techNexus/
│
├── app/
│   ├── __init__.py                 # Application Factory (create_app)
│   ├── extensions.py               # Extensões Flask (db, login_manager, csrf, limiter)
│   │
│   ├── models/                     # Modelos relacionais SQLAlchemy
│   │   ├── user.py                 # Utilizadores, credenciais, bloqueio e RBAC
│   │   ├── customer.py             # Clientes e histórico comercial
│   │   ├── supplier.py             # Fornecedores e histórico de compras
│   │   ├── product.py              # Produtos, Categorias, Marcas, Stock e Números de Série
│   │   ├── sale.py                 # Vendas, Orçamentos e Linhas de Venda
│   │   ├── purchase.py             # Compras a Fornecedores e Linhas de Compra
│   │   ├── payment.py              # Pagamentos e Liquidações
│   │   ├── service.py              # Serviços Técnicos, Ordens de Serviço e Materiais
│   │   ├── finance.py              # Contas Financeiras, Movimentos, Despesas e Contratos
│   │   ├── employee.py             # Funcionários e Técnicos
│   │   ├── notification.py         # Notificações e Alertas do Sistema
│   │   └── audit.py                # Histórico de Auditoria
│   │
│   ├── routes/                     # Controladores e Endpoints HTTP
│   │   ├── auth.py                 # Autenticação, perfil e primeiro setup
│   │   ├── dashboard.py            # Dashboard principal com KPIs e gráficos
│   │   ├── products.py             # Gestão de catálogo, categorias e marcas
│   │   ├── inventory.py            # Controlo de inventário e contagens físicas
│   │   ├── customers.py            # Gestão de clientes e débitos
│   │   ├── suppliers.py            # Gestão de fornecedores e compromissos
│   │   ├── sales.py                # Vendas, faturação, balcão e orçamentos
│   │   ├── purchases.py            # Compras e entrada em armazém
│   │   ├── services.py             # Catálogo de serviços técnicos
│   │   ├── service_orders.py       # Ordens de Serviço (OS) e diagnóstico
│   │   ├── finance.py              # DRE simplificado, contas a receber e a pagar
│   │   ├── expenses.py             # Despesas correntes e compromissos fixos
│   │   ├── cashflow.py             # Fluxo de caixa e transferências bancárias
│   │   ├── reports.py              # Central de relatórios e exportações (PDF/Excel)
│   │   ├── contracts.py            # Contratos recorrentes e garantias
│   │   ├── employees.py            # Colaboradores e folha técnica
│   │   ├── ai_assistant.py         # Assistente Executivo TechNexus AI
│   │   ├── settings.py             # Configurações do sistema e alertas
│   │   └── users.py                # Gestão de acessos de utilizadores
│   │
│   ├── services/                   # Lógica Empresarial Pura
│   │   ├── financial_calculations.py # CPV, Lucro Bruto, Ponto de Equilíbrio, DRE
│   │   ├── inventory_service.py    # Movimentações de stock, CMPM e bloqueio negativo
│   │   ├── sales_service.py        # Processamento de vendas e conversão de orçamentos
│   │   ├── purchase_service.py     # Entrada física de compras e recalculo de custo médio
│   │   ├── payment_service.py      # Gestão atómica de pagamentos e reconciliação
│   │   ├── service_order_service.py# Ciclo de vida da assistência técnica e peças
│   │   ├── report_service.py       # Exportações analíticas (PDF, Excel, CSV)
│   │   ├── analytics_service.py    # Business Intelligence e recomendações operacionais
│   │   ├── ai_service.py           # Integração Gemini API e motor de fallback local
│   │   ├── notification_service.py # Verificação e disparo automático de alertas
│   │   └── backup_service.py       # Cópias de segurança JSON gzipped e retenção
│   │
│   ├── templates/                  # Templates Jinja2 organizados por módulo
│   ├── static/                     # Folhas de estilo CSS, scripts JS e ícones
│   └── utils/                      # Formatação, validações e controlo de permissões
│
├── migrations/                     # Scripts de migração de esquema Alembic
├── tests/                          # Suíte de testes automatizados Pytest
├── scripts/                        # Scripts de automação e seed inicial
├── config.py                       # Configurações de ambiente (Dev, Test, Prod)
├── run.py                          # Ponto de entrada da aplicação
└── requirements.txt                # Dependências Python fixadas
```

---

## 5. Instalação e Execução Local

### Pré-requisitos
- **Python 3.12+** instalado.
- Ambiente virtual Python (`venv`).

### Passo 1: Clonar e entrar no diretório
```bash
cd c:\Users\ADMIN\Desktop\techNexus
```

### Passo 2: Criar e ativar o ambiente virtual
```bash
# No Windows PowerShell:
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Passo 3: Instalar as dependências
```bash
pip install -r requirements.txt
```

### Passo 4: Configurar as Variáveis de Ambiente
Copia o ficheiro de exemplo `.env.example` para `.env`:
```bash
cp .env.example .env
```
Gera uma chave secreta e edita o ficheiro `.env`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Preenche os valores no `.env`:
```ini
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=tua_chave_secreta_gerada_acima

# Para desenvolvimento local, podes deixar DATABASE_URL comentado para usar SQLite:
# DATABASE_URL=postgresql://postgres:senha@db.exemplo.supabase.co:5432/postgres

# Chave Google Gemini API (para o assistente inteligente):
GEMINI_API_KEY=tua_chave_gemini_aqui
```

### Passo 5: Inicializar a Base de Dados e Dados Iniciais
Executa o script de inicialização para criar todas as tabelas, categorias padrão de Moçambique, contas financeiras e o utilizador Administrador:
```bash
python scripts/setup_db.py
```

Credenciais padrão criadas:
- **Utilizador**: `admin`
- **Palavra-passe**: `Admin@TechNexus2026!`
- **E-mail**: `admin@technexus.co.mz`

*(Poderás alterar a palavra-passe diretamente na tua área de perfil após o primeiro acesso).*

### Passo 6: Iniciar o Servidor de Desenvolvimento
```bash
python run.py
```
Acede à aplicação no teu navegador em: **[http://localhost:5000](http://localhost:5000)**.

---

## 6. Configuração com Supabase (PostgreSQL em Produção)

Para ligar a aplicação ao PostgreSQL alojado no Supabase:
1. No painel do seu projeto Supabase, aceda a **Settings** -> **Database**.
2. Copie a string de ligação **URI** (modo Direct ou Transaction Pooler).
3. No seu `.env`, configure:
   ```ini
   DATABASE_URL=postgresql://postgres:[A_TUA_PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
   ```
4. Execute as migrações:
   ```bash
   flask db upgrade
   ```
   Ou execute `python scripts/setup_db.py` para criar tabelas e dados iniciais no PostgreSQL.

---

## 7. Execução dos Testes Automatizados

A suíte de testes do TechNexus foi desenvolvida com **Pytest** e valida os principais requisitos de integridade do sistema:
- Cálculos financeiros de CPV, Margem Bruta, Break-Even e Fluxo de Caixa.
- Regras de inventário, Custo Médio Ponderado Móvel e bloqueio de stock negativo.
- Vendas a pronto e a crédito, liquidações parciais e conversão de orçamentos.
- Ordens de Serviço, rastreio de estados e consumo de peças.
- Autenticação, bloqueio por força bruta e permissões RBAC no servidor.

Para correr a suíte de testes completa:
```bash
pytest -v
```

---

## 8. Perfis de Utilizador e Controlo de Acesso (RBAC)

O TechNexus implementa duas matrizes de acesso estritas verificadas no backend:

| Funcionalidade / Módulo | Administrador | Gerente / Vendedor |
| :--- | :---: | :---: |
| **Painel de Controlo (Dashboard Operacional)** | Sim | Sim (sem lucros globais) |
| **Vendas ao Balcão, Faturação e Orçamentos** | Sim | Sim |
| **Catálogo de Produtos e Consulta de Stock** | Sim | Sim |
| **Cadastro de Clientes** | Sim | Sim |
| **Ordens de Serviço e Assistência Técnica** | Sim | Sim |
| **Relatórios Operacionais de Vendas e Stock** | Sim | Sim |
| **Registo de Compras a Fornecedores** | Sim | Restrito / Não |
| **Gestão de Caixa e Transferências Bancárias** | Sim | Restrito / Não |
| **DRE Simplificado, Lucro Bruto e Margens** | Sim | **Não (Bloqueio 403)** |
| **Despesas Operacionais e Confidenciais** | Sim | **Não (Bloqueio 403)** |
| **Gestão de Utilizadores e Permissões** | Sim | **Não (Bloqueio 403)** |
| **Configurações Gerais e Cópias de Segurança** | Sim | **Não (Bloqueio 403)** |

---

## 9. Licença e Suporte

Desenvolvido para o ecossistema empresarial de Moçambique com os mais elevados padrões de fiabilidade e conformidade contabilística.
Para assistência e suporte técnico: `suporte@technexus.co.mz`.
