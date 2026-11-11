/**
 * TechNexus — JavaScript Corporativo
 * Controlos de navegação, alternância de menu, gráficos Chart.js e assistente IA
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Toggle de Barra Lateral (Mobile e Desktop)
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('active');
        });
    }

    // 2. Fechar mensagens de alerta automaticamente após 5 segundos
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {}
        }, 6000);
    });

    // 3. Inicializar tooltips do Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

/**
 * Envia uma mensagem para o TechNexus AI
 */
async function sendAIMessage(questionInputId, chatContainerId) {
    const input = document.getElementById(questionInputId);
    const container = document.getElementById(chatContainerId);
    if (!input || !container) return;

    const question = input.value.trim();
    if (!question) return;

    // Adiciona a bolha do utilizador imediatamente
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-bubble user';
    userBubble.innerHTML = `<strong>Você:</strong><br>${escapeHtml(question)}`;
    container.appendChild(userBubble);

    input.value = '';
    container.scrollTop = container.scrollHeight;

    // Bolha de espera
    const loadingBubble = document.createElement('div');
    loadingBubble.className = 'chat-bubble assistant text-muted';
    loadingBubble.id = 'ai-loading-bubble';
    loadingBubble.innerHTML = '<em><i class="bi bi-hourglass-split"></i> A analisar dados financeiros e operacionais...</em>';
    container.appendChild(loadingBubble);
    container.scrollTop = container.scrollHeight;

    try {
        const response = await fetch('/assistente/perguntar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ question: question })
        });

        const data = await response.json();
        const loadEl = document.getElementById('ai-loading-bubble');
        if (loadEl) loadEl.remove();

        const aiBubble = document.createElement('div');
        aiBubble.className = 'chat-bubble assistant';
        
        let formattedText = data.answer || "Ocorreu um erro ao processar a resposta.";
        // Converte quebras de linha em <br> e negritos simples
        formattedText = formattedText.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        aiBubble.innerHTML = `<strong><i class="bi bi-robot text-primary"></i> TechNexus AI:</strong><br>${formattedText}`;
        container.appendChild(aiBubble);
        container.scrollTop = container.scrollHeight;

    } catch (err) {
        const loadEl = document.getElementById('ai-loading-bubble');
        if (loadEl) loadEl.remove();

        const errBubble = document.createElement('div');
        errBubble.className = 'chat-bubble assistant text-danger';
        errBubble.innerHTML = '<strong>Erro:</strong> Não foi possível contactar o assistente inteligente neste momento.';
        container.appendChild(errBubble);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}
