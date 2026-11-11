"""
app/routes/ai_assistant.py — TechNexus AI: Consultor Empresarial Inteligente

Interface de Conversação e API de Apoio à Decisão com Google Gemini e Motor Local.
Acesso exclusivo a Administradores para salvaguardar segredo comercial e financeiro.
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.services.ai_service import ask_business_assistant, get_authorized_business_context
from app.models.notification import AIConversation
from app.utils.permissions import admin_required

ai_bp = Blueprint('ai_assistant', __name__)


@ai_bp.route('/')
@login_required
@admin_required
def index():
    """Interface principal do Consultor Empresarial com chat interativo."""
    # Carregar histórico recente de conversas do utilizador
    history = AIConversation.query.filter_by(
        user_id=current_user.id
    ).order_by(AIConversation.created_at.asc()).limit(30).all()

    # Contexto rápido para os cartões de sugestão
    context = get_authorized_business_context()

    return render_template(
        'ai_assistant/index.html',
        history=history,
        context=context
    )


@ai_bp.route('/perguntar', methods=['POST'])
@login_required
@admin_required
def ask():
    """Endpoint API para responder a questões do administrador."""
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    session_id = data.get('session_id')

    if not question:
        return jsonify({'success': False, 'answer': 'Pergunta vazia.'}), 400

    result = ask_business_assistant(
        user_id=current_user.id,
        question=question,
        session_id=session_id
    )

    return jsonify(result)
