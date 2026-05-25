# Copyright 2026 Abdalrahman Shahrour
{
    'name': 'MH Approval Extension',
    'version': '1.0',
    'category': 'Generic',
    'summary': 'Extends dynamic approval workflow to Purchase Orders, Expenses, Invoices, and Payments',
    'description': """
MH Approval Extension
=====================
Adds multi-level approval workflow capabilities to:
- Purchase Orders
- Expenses
- Invoices (post from draft)
- Vendor Payments

Requires dynamic_approval_workflow module.
Approval thresholds and approvers configured via UI by admin.
    """,
    'author': 'Abdalah Shahrour',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'dynamic_approval_workflow',
        'purchase',
        'hr_expense',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}