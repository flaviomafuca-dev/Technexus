"""
app/services/report_service.py — Serviço de Relatórios e Exportações

Gera relatórios executivos e operacionais com suporte a exportação em:
- PDF (via ReportLab com layout corporativo, cabeçalho da empresa, moeda MT)
- Excel (.xlsx via OpenPyXL formatado)
- CSV (codificação UTF-8 com separador e formatação limpa)
"""

import io
import csv
from datetime import datetime, date
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.utils.formatting import format_currency, format_date


def export_to_csv(headers, rows, filename="relatorio.csv"):
    """
    Exporta dados tabulares para formato CSV em memória.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return io.BytesIO(output.getvalue().encode('utf-8-sig'))


def export_to_excel(title, headers, rows, filename="relatorio.xlsx"):
    """
    Exporta dados tabulares para uma folha de cálculo Excel (.xlsx) profissional.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = title[:30]

    # Estilos
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")  # Azul escuro
    title_font = Font(name="Calibri", size=14, bold=True, color="1B365D")
    border_thin = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # Título do Relatório
    ws.append([f"TechNexus — {title}"])
    ws.cell(row=1, column=1).font = title_font
    ws.append([f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Moeda: MZN (MT)"])
    ws.append([])  # Linha vazia

    # Cabeçalho da tabela
    ws.append(headers)
    header_row_idx = 4
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Linhas de dados
    for r in rows:
        ws.append(r)
        current_row = ws.max_row
        for col_idx in range(1, len(r) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.border = border_thin

    # Auto-ajuste da largura das colunas
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val_str = str(cell.value or '')
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_to_pdf(title, headers, rows, filename="relatorio.pdf", company_name="TechNexus"):
    """
    Exporta dados tabulares para um documento PDF profissional com ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1B365D')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#555555')
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10
    )

    elements = []

    # Cabeçalho do documento
    elements.append(Paragraph(f"<b>{company_name}</b> — Sistema de Gestão Empresarial", title_style))
    elements.append(Paragraph(f"<b>Relatório:</b> {title} | <b>Emitido:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')} | <b>Moeda:</b> MT (MZN)", subtitle_style))
    elements.append(Spacer(1, 15))

    # Formatar dados em tabela
    table_data = [[Paragraph(f"<b>{h}</b>", table_cell_style) for h in headers]]
    for row in rows:
        table_data.append([Paragraph(str(item), table_cell_style) for item in row])

    # Estilização da tabela
    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B365D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D9D9D9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))

    elements.append(t)
    doc.build(elements)

    buffer.seek(0)
    return buffer
