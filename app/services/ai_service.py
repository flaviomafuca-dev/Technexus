"""
app/services/ai_service.py — TechNexus AI: Consultor Empresarial Inteligente

Arquitetura de Inteligência Artificial:
1. Execução 100% no backend (segurança de chaves e dados).
2. Não executa SQL arbitrário do modelo.
3. Consulta exclusivamente dados reais e cálculos oficiais do sistema via funções autorizadas.
4. Constrói contexto objetivo em língua portuguesa com métricas fiáveis da empresa.
5. Se a Gemini API estiver desativada, sem chave ou com falha, utiliza o fallback inteligente
   baseado no motor TechNexus Intelligence sem interromper nenhuma operação.
"""

import os
import json
from datetime import date, datetime, timezone
from flask import current_app
from app.extensions import db
from app.models.notification import AIConversation
from app.services.financial_calculations import (
    calculate_revenue, calculate_gross_profit, calculate_operating_expenses,
    calculate_operating_result, calculate_accounts_receivable,
    calculate_accounts_payable, calculate_cash_flow, get_period_dates
)
from app.services.analytics_service import (
    get_growth_analytics, get_profitability_analytics, generate_business_recommendations
)
from app.models.product import Product
from app.models.sale import Sale
from app.models.service import ServiceOrder


def get_authorized_business_context():
    """
    Função autorizada que extrai métricas reais consolidadas da empresa
    para fornecer contexto fiel ao modelo, evitando alucinações matemáticas.
    """
    today = date.today()
    month_start, month_end = get_period_dates('month')
    last_month_start, last_month_end = get_period_dates('last_month')

    # Métricas do mês atual
    current_month_financials = calculate_operating_result(month_start, month_end)
    last_month_financials = calculate_operating_result(last_month_start, last_month_end)
    cash_flow_data = calculate_cash_flow(month_start, month_end)
    receivables = calculate_accounts_receivable()
    payables = calculate_accounts_payable()

    # Operacional
    low_stock = Product.query.filter(
        Product.is_active == True,
        Product.stock_quantity <= Product.minimum_stock
    ).count()

    pending_orders = ServiceOrder.query.filter(
        ServiceOrder.status.in_(['received', 'diagnosing', 'waiting_approval', 'waiting_parts', 'in_progress'])
    ).count()

    top_profitable = get_profitability_analytics(month_start, month_end, limit=5)

    context = {
        'data_atual': today.strftime('%d/%m/%Y'),
        'moeda': 'MZN (Meticais)',
        'mes_atual': {
            'periodo': f"{month_start.strftime('%d/%m/%Y')} até {month_end.strftime('%d/%m/%Y')}",
            'faturacao_total': f"{current_month_financials['total_revenue']:.2f} MT",
            'custo_mercadorias_vendidas': f"{current_month_financials['total_cogs']:.2f} MT",
            'lucro_bruto': f"{current_month_financials['gross_profit']:.2f} MT",
            'margem_bruta_percentual': f"{current_month_financials['gross_margin_percent']:.1f}%" if current_month_financials['gross_margin_percent'] is not None else "N/D",
            'despesas_operacionais': f"{current_month_financials['operating_expenses']:.2f} MT",
            'resultado_operacional_liquido': f"{current_month_financials['operating_result']:.2f} MT",
            'margem_operacional_percentual': f"{current_month_financials['operating_margin_percent']:.1f}%" if current_month_financials['operating_margin_percent'] is not None else "N/D"
        },
        'mes_anterior': {
            'faturacao_total': f"{last_month_financials['total_revenue']:.2f} MT",
            'lucro_bruto': f"{last_month_financials['gross_profit']:.2f} MT",
            'despesas_operacionais': f"{last_month_financials['operating_expenses']:.2f} MT",
            'resultado_operacional': f"{last_month_financials['operating_result']:.2f} MT"
        },
        'posicao_financeira_e_dividas': {
            'saldo_disponivel_caixa': f"{cash_flow_data['final_balance']:.2f} MT",
            'dividas_de_clientes_a_receber': f"{receivables['total']:.2f} MT (Vencido: {receivables['overdue']:.2f} MT)",
            'dividas_a_fornecedores_a_pagar': f"{payables['total']:.2f} MT (Vencido: {payables['overdue']:.2f} MT)"
        },
        'operacoes': {
            'produtos_com_stock_baixo_ou_esgotado': low_stock,
            'ordens_servico_em_aberto': pending_orders
        },
        'destaques_produtos_mais_lucrativos': [
            f"{p['name']} (Lucro: {p['gross_profit']:.2f} MT, Margem: {p['margin_percent']:.1f}%)"
            for p in top_profitable.get('top_products', [])[:3]
        ]
    }
    return context


def ask_business_assistant(user_id, question, session_id=None):
    """
    Processa a questão do administrador e gera uma resposta fundamentada.
    """
    if not question or not question.strip():
        return {
            'success': False,
            'answer': "Por favor, formule uma pergunta sobre o seu negócio.",
            'source': 'system'
        }

    clean_question = question.strip()
    session_id = session_id or f"sess_{user_id}_{date.today().strftime('%Y%m%d')}"

    # Salva a pergunta do utilizador no histórico
    user_conv = AIConversation(
        user_id=user_id,
        session_id=session_id,
        role='user',
        message=clean_question,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(user_conv)

    api_key = os.environ.get('GEMINI_API_KEY') or current_app.config.get('GEMINI_API_KEY')
    model_name = os.environ.get('GEMINI_MODEL') or current_app.config.get('GEMINI_MODEL', 'gemini-2.0-flash')
    enabled = current_app.config.get('GEMINI_ENABLED', True)

    business_data = get_authorized_business_context()

    # Se a API não estiver configurada ou estiver explicitamente desativada
    if not enabled or not api_key or api_key == 'A_TUA_CHAVE_GEMINI_API_AQUI':
        fallback_answer = generate_rule_based_response(clean_question, business_data)
        
        # Salva a resposta no histórico
        ai_conv = AIConversation(
            user_id=user_id,
            session_id=session_id,
            role='assistant',
            message=fallback_answer,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(ai_conv)
        db.session.commit()

        return {
            'success': True,
            'answer': fallback_answer,
            'source': 'local_engine',
            'model': 'TechNexus Intelligence (Regras Locais)'
        }

    # Chamada à Google Gemini API oficial
    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        system_instruction = (
            "Tu és o TechNexus AI — Consultor Empresarial Especialista, assistente inteligente "
            "de gestão para uma empresa de equipamentos informáticos e serviços técnicos em Moçambique. "
            "Responde em português de forma profissional, rigorosa, clara e direta. "
            "Usa SEMPRE meticais (MT / MZN) como moeda. "
            "NUNCA inventes números ou cálculos. Baseia as tuas respostas única e exclusivamente nos dados "
            "reais fornecidos abaixo. Quando te perguntarem sobre lucros, faturamento ou despesas, "
            "explica os números com base no contexto oficial."
        )

        prompt_content = (
            f"DADOS REAIS E ATUALIZADOS DA EMPRESA:\n"
            f"{json.dumps(business_data, indent=2, ensure_ascii=False)}\n\n"
            f"PERGUNTA DO ADMINISTRADOR:\n{clean_question}\n\n"
            f"Por favor, responde com uma análise concisa, objetiva e orientada a decisões executivas."
        )

        response = client.models.generate_content(
            model=model_name,
            contents=prompt_content,
            config={
                'system_instruction': system_instruction,
                'temperature': 0.2,
                'max_output_tokens': 1000
            }
        )

        ai_response_text = response.text if response and response.text else "Não foi possível obter uma resposta precisa."

        ai_conv = AIConversation(
            user_id=user_id,
            session_id=session_id,
            role='assistant',
            message=ai_response_text,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(ai_conv)
        db.session.commit()

        return {
            'success': True,
            'answer': ai_response_text,
            'source': 'gemini_api',
            'model': model_name
        }

    except Exception as e:
        # Em caso de falha de ligação, timeout ou limite na API Gemini, não deixa o utilizador sem resposta
        current_app.logger.warning(f"Gemini API indisponível ou com erro: {e}. A usar motor local.")
        fallback_answer = generate_rule_based_response(clean_question, business_data)

        ai_conv = AIConversation(
            user_id=user_id,
            session_id=session_id,
            role='assistant',
            message=fallback_answer,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(ai_conv)
        db.session.commit()

        return {
            'success': True,
            'answer': fallback_answer,
            'source': 'fallback_local',
            'model': 'TechNexus Intelligence (Fallback Local)'
        }


def generate_rule_based_response(question, data):
    """
    Motor local de resposta a perguntas frequentes de negócio.
    Garante que o administrador obtém sempre respostas reais mesmo sem Gemini API.
    """
    q = question.lower()
    m_atual = data['mes_atual']
    pos = data['posicao_financeira_e_dividas']
    ops = data['operacoes']

    if 'lucr' in q:
        return (
            f"📊 **Lucro da Empresa (Mês Atual)**:\n"
            f"- **Faturação Total**: {m_atual['faturacao_total']}\n"
            f"- **Custo das Mercadorias/Serviços (CPV)**: {m_atual['custo_mercadorias_vendidas']}\n"
            f"- **Lucro Bruto**: {m_atual['lucro_bruto']} (Margem Bruta: {m_atual['margem_bruta_percentual']})\n"
            f"- **Despesas Operacionais**: {m_atual['despesas_operacionais']}\n"
            f"- **Resultado Operacional Líquido**: {m_atual['resultado_operacional_liquido']}\n\n"
            f"💡 *Nota: O cálculo é efetuado com base em custos reais médios ponderados.*"
        )
    elif 'despes' in q or 'cust' in q or 'gasto' in q:
        return (
            f"📉 **Despesas do Mês Atual**:\n"
            f"- **Total de Despesas Operacionais Registadas**: {m_atual['despesas_operacionais']}\n"
            f"- **Dívidas a Fornecedores**: {pos['dividas_a_fornecedores_a_pagar']}\n\n"
            f"Recomenda-se verificar a secção de Gestão de Despesas para o detalhe por categorias (renda, salários, eletricidade, etc.)."
        )
    elif 'stock' in q or 'produto' in q or 'peça' in q:
        return (
            f"📦 **Situação de Stock e Inventário**:\n"
            f"- **Produtos em Stock Crítico / Baixo**: {ops['produtos_com_stock_baixo_ou_esgotado']} produto(s)\n"
            f"- **Destaques de Rentabilidade**: {', '.join(data.get('destaques_produtos_mais_lucrativos', ['Sem vendas suficientes']))}\n\n"
            f"Consulte o módulo de Stock para emitir ordens de compra de reposição."
        )
    elif 'dívida' in q or 'divida' in q or 'devedor' in q or 'receber' in q:
        return (
            f"💳 **Dívidas e Saldos Financeiros**:\n"
            f"- **Saldo Disponível em Caixa / Bancos**: {pos['saldo_disponivel_caixa']}\n"
            f"- **Valores a Receber de Clientes**: {pos['dividas_de_clientes_a_receber']}\n"
            f"- **Valores a Pagar a Fornecedores**: {pos['dividas_a_fornecedores_a_pagar']}"
        )
    else:
        recs = generate_business_recommendations()
        first_rec = recs[0] if recs else None
        rec_text = f"\n\n🎯 **Recomendação prioritária**: {first_rec['title']}\n{first_rec['recommended_action']}" if first_rec else ""

        return (
            f"🤖 **Resumo Executivo do Negócio ({data['data_atual']})**:\n"
            f"- **Faturação este mês**: {m_atual['faturacao_total']}\n"
            f"- **Lucro Bruto**: {m_atual['lucro_bruto']} ({m_atual['margem_bruta_percentual']})\n"
            f"- **Despesas Operacionais**: {m_atual['despesas_operacionais']}\n"
            f"- **Resultado Operacional**: {m_atual['resultado_operacional_liquido']}\n"
            f"- **Saldo em Caixa/Bancos**: {pos['saldo_disponivel_caixa']}\n"
            f"- **Contas a Receber**: {pos['dividas_de_clientes_a_receber']}\n"
            f"- **Alertas de Stock**: {ops['produtos_com_stock_baixo_ou_esgotado']} itens críticos"
            f"{rec_text}\n\n"
            f"Pode perguntar-me detalhes sobre 'lucro', 'despesas', 'stock' ou 'dívidas'."
        )
