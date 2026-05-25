# -*- coding: utf-8 -*-

from odoo import models, fields, api

class HrEmployeeExtend(models.Model):
    _inherit = 'hr.employee'

    # Booking Role - defines what type of work this employee can do
    booking_role = fields.Selection([
        ('cleaner', 'Cleaner'),
        ('technician', 'Technician'),
        ('driver', 'Driver'),
        ('supervisor', 'Supervisor'),
    ], string='Booking Role', index=True)

    # Team Lead flag for driver team assignment
    is_team_lead = fields.Boolean(
        string='Is Team Lead',
        default=False,
    )

    # Zone Assignment for this employee
    zone_ids = fields.Many2many(
        'mh.zone',
        'mh_zone_employee_rel',
        'employee_id',
        'zone_id',
        string='Assigned Zones',
    )

    primary_zone_id = fields.Many2one(
        'mh.zone',
        string='Primary Zone',
    )

    # Capacity limits
    max_daily_bookings = fields.Integer(
        string='Max Daily Bookings',
        default=3,
    )
    max_weekly_bookings = fields.Integer(
        string='Max Weekly Bookings',
        default=15,
    )

    # Working schedule
    working_days = fields.Char(
        string='Working Days',
        default='1,2,3,4,5',
        help='Comma-separated day numbers (1=Monday, 7=Sunday)',
    )
    working_hour_start = fields.Float(
        string='Start Time',
        default=9.0,
    )
    working_hour_end = fields.Float(
        string='End Time',
        default=18.0,
    )