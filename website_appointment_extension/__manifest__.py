# -*- coding: utf-8 -*-
{
    'name': 'Website Appointment Extension',
    'summary': """Backend Team Management & Smart Assignment for Appointments""",
    'category': 'Appointments',
    'version': '18.0.1.5.0',
    'depends': ['website', 'appointment_account_payment', 'mail', 'desality_customization'],
    'data': [
        'security/ir.model.access.csv',
        'views/appointment_type_views.xml',
        'views/appointment_template.xml',
        'views/hide_referral_partner.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
    'author': 'Desality',
    'website': 'https://www.desality.com',
}
