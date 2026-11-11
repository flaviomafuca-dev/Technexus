"""
app/utils/formatting.py — Utilitários de formatação para o TechNexus

Funções para formatar valores monetários, datas e números
de acordo com o contexto moçambicano (MZN, formato pt-MZ).
"""

from decimal import Decimal, InvalidOperation
from datetime import datetime, date


# ==========================================
# Formatação monetária
# ==========================================

def format_currency(value, symbol='MT', decimal_places=2):
    """
    Formata um valor como moeda moçambicana (MZN).
    
    Exemplos:
        format_currency(35000)      → "35.000,00 MT"
        format_currency(1500.5)     → "1.500,50 MT"
        format_currency(None)       → "0,00 MT"
    
    Parâmetros:
        value: Valor numérico a formatar.
        symbol: Símbolo da moeda (por defeito: MT).
        decimal_places: Casas decimais (por defeito: 2).
    
    Retorna:
        String formatada com o valor e símbolo.
    """
    if value is None:
        value = 0
    
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return f"0,00 {symbol}"
    
    # Formata com separadores do sistema pt-MZ
    # Ponto como separador de milhares, vírgula como decimal
    formatted = format_number_ptmz(decimal_value, decimal_places)
    return f"{formatted} {symbol}"


def format_number_ptmz(value, decimal_places=2):
    """
    Formata um número no padrão português (pt-MZ).
    Ponto para milhares, vírgula para decimais.
    
    Parâmetros:
        value: Valor numérico.
        decimal_places: Casas decimais.
    
    Retorna:
        String formatada (ex: "1.234.567,89")
    """
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        decimal_value = Decimal('0')
    
    # Arredonda para as casas decimais pedidas
    rounded = round(float(decimal_value), decimal_places)
    
    # Formata com Python e converte separadores
    python_formatted = f"{rounded:,.{decimal_places}f}"
    
    # Converte: "1,234,567.89" → "1.234.567,89"
    # Passo 1: substitui vírgulas temporariamente
    temp = python_formatted.replace(',', 'TEMP')
    # Passo 2: substitui ponto decimal por vírgula
    temp = temp.replace('.', ',')
    # Passo 3: substitui temporário por ponto
    result = temp.replace('TEMP', '.')
    
    return result


def format_number(value, decimal_places=2):
    """Formata um número sem símbolo de moeda."""
    return format_number_ptmz(value, decimal_places)


def format_percentage(value, decimal_places=1):
    """
    Formata um valor como percentagem.
    
    Exemplos:
        format_percentage(25.5)    → "25,5%"
        format_percentage(None)    → "—"
    
    Parâmetros:
        value: Valor da percentagem (já em %).
        decimal_places: Casas decimais.
    
    Retorna:
        String formatada com o símbolo %.
    """
    if value is None:
        return "—"
    
    try:
        formatted = format_number_ptmz(value, decimal_places)
        return f"{formatted}%"
    except Exception:
        return "—"


# ==========================================
# Formatação de datas
# ==========================================

# Meses em português
MONTHS_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

MONTHS_SHORT_PT = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}


def format_date(value, format_str='%d/%m/%Y'):
    """
    Formata uma data no padrão português.
    
    Exemplos:
        format_date(date(2024, 10, 23))   → "23/10/2024"
        format_date(None)                  → "—"
    
    Parâmetros:
        value: Objecto date ou datetime.
        format_str: Formato de saída (padrão: dd/mm/aaaa).
    
    Retorna:
        String com a data formatada.
    """
    if value is None:
        return "—"
    
    if isinstance(value, datetime):
        return value.strftime(format_str)
    elif isinstance(value, date):
        return value.strftime(format_str)
    
    return str(value)


def format_datetime(value, include_seconds=False):
    """
    Formata uma data e hora no padrão português.
    
    Exemplos:
        format_datetime(datetime(...))  → "23/10/2024 14:30"
    
    Parâmetros:
        value: Objecto datetime.
        include_seconds: Se True, inclui segundos.
    
    Retorna:
        String com data e hora formatadas.
    """
    if value is None:
        return "—"
    
    if not isinstance(value, (datetime, date)):
        return str(value)
    
    date_str = format_date(value)
    
    if isinstance(value, datetime):
        if include_seconds:
            time_str = value.strftime('%H:%M:%S')
        else:
            time_str = value.strftime('%H:%M')
        return f"{date_str} {time_str}"
    
    return date_str


def format_date_long(value):
    """
    Formata uma data por extenso em português.
    
    Exemplo: "23 de Outubro de 2024"
    """
    if value is None:
        return "—"
    
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        return str(value)
    
    month_name = MONTHS_PT.get(d.month, str(d.month))
    return f"{d.day} de {month_name} de {d.year}"


def format_month_year(value):
    """
    Formata mês e ano em português.
    
    Exemplo: "Outubro 2024"
    """
    if value is None:
        return "—"
    
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        return str(value)
    
    month_name = MONTHS_PT.get(d.month, str(d.month))
    return f"{month_name} {d.year}"


# ==========================================
# Utilitários de variação percentual
# ==========================================

def calculate_percentage_change(current_value, previous_value):
    """
    Calcula a variação percentual entre dois períodos.
    
    Fórmula: (valor actual - valor anterior) / valor anterior × 100
    
    NOTA: Se o valor anterior for zero, retorna None em vez de
    uma percentagem enganadora. O frontend deve tratar este caso.
    
    Parâmetros:
        current_value: Valor do período actual.
        previous_value: Valor do período anterior.
    
    Retorna:
        Variação em % ou None se não for possível calcular.
    """
    try:
        current = Decimal(str(current_value or 0))
        previous = Decimal(str(previous_value or 0))
        
        if previous == 0:
            return None  # Não apresenta percentagem enganadora
        
        change = (current - previous) / previous * 100
        return float(change)
    except (InvalidOperation, ZeroDivisionError):
        return None


def format_change_indicator(change_percent):
    """
    Formata a indicação de variação com símbolo.
    
    Parâmetros:
        change_percent: Variação em %.
    
    Retorna:
        Dicionário com valor formatado, classe CSS e símbolo.
    """
    if change_percent is None:
        return {
            'text': 'N/D',
            'css_class': 'text-muted',
            'symbol': '',
            'value': None
        }
    
    formatted = format_percentage(abs(change_percent))
    
    if change_percent > 0:
        return {
            'text': f'+{formatted}',
            'css_class': 'text-success',
            'symbol': '▲',
            'value': change_percent
        }
    elif change_percent < 0:
        return {
            'text': f'-{formatted}',
            'css_class': 'text-danger',
            'symbol': '▼',
            'value': change_percent
        }
    else:
        return {
            'text': '0%',
            'css_class': 'text-muted',
            'symbol': '—',
            'value': 0
        }
