# Copyright 2026 Abdalrahman Shahrour
{
    "name": "Customer Status Tracking",
    "version": "18.0.1.0.0",
    "category": "Customer Management",
    "summary": "Track customer activity status and automatically flag at-risk or inactive customers.",
    "description": """
Customer Status Tracking
========================
Automatically tracks customer activity based on booking records and flags
customers as At Risk or Inactive when no booking has been made within
configurable thresholds. Creates CRM follow-up activities assigned to the
customer's assigned salesperson.
    """,
    "author": "Abd al-Rahman Shahrour",
    "website": "",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "mh_booking_calendar",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_view.xml",
        "views/customer_status_config_view.xml",
        "views/customer_status_menu.xml",
        "data/default_config.xml",
    ],
    "installable": True,
    "application": True,
}
