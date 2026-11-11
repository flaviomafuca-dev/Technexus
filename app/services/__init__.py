"""
app/services/__init__.py — Módulo central de serviços de negócio do TechNexus
"""

from app.services.financial_calculations import (
    calculate_revenue,
    calculate_collections,
    calculate_cost_of_goods_sold,
    calculate_gross_profit,
    calculate_operating_expenses,
    calculate_operating_result,
    calculate_cash_flow,
    calculate_accounts_receivable,
    calculate_accounts_payable,
    calculate_break_even,
    get_dashboard_indicators,
    get_period_dates,
    get_previous_period
)

from app.services.inventory_service import (
    register_stock_movement,
    manual_stock_adjustment,
    register_serial_number,
    mark_serial_sold
)

from app.services.payment_service import (
    register_payment,
    cancel_payment
)

from app.services.sales_service import (
    create_sale_or_quote,
    confirm_sale,
    cancel_sale,
    convert_quote_to_sale
)

from app.services.purchase_service import (
    create_purchase,
    confirm_purchase,
    receive_purchase
)

from app.services.service_order_service import (
    create_service_order,
    update_order_status,
    add_material_to_order
)

from app.services.analytics_service import (
    get_growth_analytics,
    get_profitability_analytics,
    generate_business_recommendations
)

from app.services.ai_service import (
    ask_business_assistant,
    get_authorized_business_context
)

from app.services.notification_service import (
    get_unread_count,
    create_notification,
    check_and_generate_system_alerts
)

from app.services.report_service import (
    export_to_csv,
    export_to_excel,
    export_to_pdf
)

from app.services.backup_service import (
    create_system_backup,
    list_available_backups
)
