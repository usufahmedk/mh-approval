# -*- coding: utf-8 -*-

{
    'name': 'MH Booking Calendar',
    'version': '18.0.1.0.0',
    'category': 'Services',
    'summary': 'Custom booking calendar for Cleaning and Maintenance services',
    'description': '''
        Custom Booking Calendar Module for M&H Technical Services
        - Zone-based scheduling
        - Staff conflict detection (time + zone)
        - AMC contract management via Subscriptions
        - One-time booking via Sales Orders
        - WhatsApp notifications
    ''',
    'author': 'M&H Technical Services',
    'website': '',
    'depends': [
        'base', 'calendar', 'crm', 'project', 'account',
        'product', 'contacts', 'website', 'sale',
        'sale_subscription', 'industry_fsm', 'appointment'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/mail_template_data.xml',
        'data/cron_data.xml',
        'views/mh_calendar_views.xml',
        'views/mh_booking_type_views.xml',
        'views/mh_booking_views.xml',
        'views/mh_staff_views.xml',
        'views/mh_zone_views.xml',
        'views/mh_driver_team_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
