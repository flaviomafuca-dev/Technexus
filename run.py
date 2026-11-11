"""
run.py — Ponto de entrada principal do TechNexus

Este ficheiro inicia a aplicação Flask em modo de desenvolvimento.
Em produção, usa-se o Gunicorn ou outro servidor WSGI.

Uso:
    python run.py
    
Ou com Flask CLI:
    flask run

Em produção:
    gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
"""

import os
from app import create_app

# Cria a instância da aplicação com base na configuração do ambiente
app = create_app()

if __name__ == '__main__':
    # Obtém configurações de execução das variáveis de ambiente
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))

    # ATENÇÃO: debug=True nunca deve ser usado em produção
    if os.environ.get('FLASK_ENV') == 'production' and debug_mode:
        print("AVISO: Modo debug ativo em ambiente de produção. A desativar...")
        debug_mode = False

    print(f"TechNexus a iniciar em http://{host}:{port}")
    print(f"Ambiente: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Debug: {debug_mode}")

    app.run(
        host=host,
        port=port,
        debug=debug_mode
    )
