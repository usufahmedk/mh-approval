# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MHZone(models.Model):
    """
    Geographic zones for service coverage areas.
    Each zone represents a specific area where M&H Technical Services operates.
    """
    _name = 'mh.zone'
    _description = 'MH Zone'
    _order = 'sequence, name'
    _parent_store = True
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Zone Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Zone Code',
        required=True,
        index=True,
        size=10,
        help='Short code for the zone (e.g., ZN-NORTH, ZN-SOUTH).',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this zone will not be available.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order zones in lists.',
    )

    # Zone hierarchy
    parent_id = fields.Many2one(
        'mh.zone',
        string='Parent Zone',
        index=True,
        ondelete='cascade',
    )
    child_ids = fields.One2many(
        'mh.zone',
        'parent_id',
        string='Child Zones',
    )
    parent_path = fields.Char(
        index=True,
    )

    # Geographic information
    street = fields.Char(
        string='Street',
        translate=True,
    )
    street2 = fields.Char(
        string='Street 2',
        translate=True,
    )
    city = fields.Char(
        string='City',
        index=True,
    )
    state_id = fields.Many2one(
        'res.country.state',
        string='State',
        ondelete='restrict',
        domain="[('country_id', '=?', country_id)]",
    )
    zip = fields.Char(
        string='ZIP Code',
        index=True,
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        ondelete='restrict',
    )

    # Full address computed field
    full_address = fields.Char(
        string='Full Address',
        compute='_compute_full_address',
        store=True,
    )

    # Color for calendar view
    color = fields.Integer(
        string='Color',
        default=0,
        help='Color for calendar view representation.',
    )

    # Zone management
    manager_id = fields.Many2one(
        'res.users',
        string='Zone Manager',
        ondelete='set null',
        tracking=True,
    )
    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        ondelete='set null',
    )

    # Staff assignment
    staff_ids = fields.Many2many(
        'mh.staff',
        'mh_zone_staff_rel',
        'zone_id',
        'staff_id',
        string='Assigned Staff',
        context={},
    )
    staff_count = fields.Integer(
        string='Staff Count',
        compute='_compute_staff_count',
        store=True,
    )

    # Booking statistics
    booking_count = fields.Integer(
        string='Total Bookings',
        compute='_compute_booking_count',
    )
    booking_count_today = fields.Integer(
        string="Today's Bookings",
        compute='_compute_booking_count_today',
    )
    booking_count_week = fields.Integer(
        string="This Week's Bookings",
        compute='_compute_booking_count_week',
    )

    # Capacity settings
    capacity_per_day = fields.Integer(
        string='Capacity Per Day',
        default=50,
        help='Maximum bookings per day for this zone'
    )
    max_daily_bookings = fields.Integer(
        string='Max Daily Bookings',
        default=50,
        help='Maximum number of bookings allowed per day in this zone.',
    )
    default_buffer_minutes = fields.Integer(
        string='Default Buffer (Minutes)',
        default=30,
        help='Default buffer time between bookings in the same zone'
    )
    booking_buffer_minutes = fields.Integer(
        string='Buffer Between Bookings (Minutes)',
        default=30,
        help='Minimum time gap between consecutive bookings.',
    )
    cross_zone_buffer_minutes = fields.Integer(
        string='Cross-Zone Buffer (Minutes)',
        default=45,
        help='Default buffer time when staff moves between zones'
    )

    # Service settings
    working_hour_start = fields.Float(
        string='Working Hours Start',
        default=8.0,
        widget='float_time',
        help='Start time for bookings in this zone.',
    )
    working_hour_end = fields.Float(
        string='Working Hours End',
        default=18.0,
        widget='float_time',
        help='End time for bookings in this zone.',
    )
    working_days = fields.Char(
        string='Working Days',
        default='1,2,3,4,5',  # Monday to Friday
        help='Comma-separated day numbers (1=Monday, 7=Sunday).',
    )

    # Coverage areas (many2many for flexibility)
    coverage_area_ids = fields.Many2many(
        'mh.zone.coverage',
        'mh_zone_coverage_rel',
        'zone_id',
        'coverage_id',
        string='Coverage Areas',
    )

    # Notes
    description = fields.Text(
        string='Description',
        translate=True,
    )
    notes = fields.Text(
        string='Internal Notes',
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    # =====================================================================
    # COMPUTED FIELDS
    # =====================================================================
    @api.depends('street', 'street2', 'city', 'state_id', 'zip', 'country_id')
    def _compute_full_address(self):
        """Compute the full address string."""
        for record in self:
            parts = [
                record.street,
                record.street2,
                record.city,
                record.state_id.name if record.state_id else '',
                record.zip,
                record.country_id.name if record.country_id else '',
            ]
            record.full_address = ', '.join(filter(None, parts))

    @api.depends('staff_ids')
    def _compute_staff_count(self):
        """Compute the number of staff assigned to this zone."""
        for record in self:
            record.staff_count = len(record.staff_ids)

    def _compute_booking_count(self):
        """Compute total booking count for this zone."""
        for record in self:
            count = self.env['mh.booking'].search_count([
                ('zone_id', 'child_of', record.id),
                ('state', 'not in', ['cancelled']),
            ])
            record.booking_count = count

    def _compute_booking_count_today(self):
        """Compute today's booking count for this zone."""
        today = fields.Date.context_today(self)
        for record in self:
            count = self.env['mh.booking'].search_count([
                ('zone_id', 'child_of', record.id),
                ('booking_date', '=', today),
                ('state', 'not in', ['cancelled']),
            ])
            record.booking_count_today = count

    def _compute_booking_count_week(self):
        """Compute this week's booking count for this zone."""
        today = fields.Date.context_today(self)
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        for record in self:
            count = self.env['mh.booking'].search_count([
                ('zone_id', 'child_of', record.id),
                ('booking_date', '>=', start_of_week),
                ('booking_date', '<=', end_of_week),
                ('state', 'not in', ['cancelled']),
            ])
            record.booking_count_week = count

    # =====================================================================
    # CONSTRAINTS
    # =====================================================================
    @api.constrains('code')
    def _check_unique_code(self):
        """Ensure zone code is unique."""
        for record in self:
            if self.search([
                ('id', '!=', record.id),
                ('code', '=', record.code),
                ('company_id', '=', record.company_id.id),
            ]):
                raise ValidationError(
                    _('Zone code "%s" already exists.') % record.code
                )

    @api.constrains('parent_id')
    def _check_hierarchy(self):
        """Prevent circular references in zone hierarchy."""
        for record in self:
            current = record.parent_id
            visited = set()
            while current:
                if current.id in visited:
                    raise ValidationError(
                        _('Circular reference detected in zone hierarchy.')
                    )
                visited.add(current.id)
                current = current.parent_id

    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    def get_working_days(self):
        """Return list of working day numbers."""
        self.ensure_one()
        if not self.working_days:
            return []
        return [int(d) for d in self.working_days.split(',')]

    def is_working_day(self, date):
        """Check if given date is a working day for this zone."""
        self.ensure_one()
        working_days = self.get_working_days()
        return date.weekday() + 1 in working_days  # weekday() returns 0-6

    def get_working_hours(self, date):
        """Return working hours for a specific date."""
        self.ensure_one()
        if not self.is_working_day(date):
            return None, None
        return self.working_hour_start, self.working_hour_end

    def get_available_slots(self, date, duration=2.0):
        """Get available time slots for a given date."""
        self.ensure_one()
        if not self.is_working_day(date):
            return []

        start_hour, end_hour = self.get_working_hours(date)
        if not start_hour or not end_hour:
            return []

        slots = []
        current_hour = start_hour

        while current_hour + duration <= end_hour:
            # Check if slot is available
            slot_start = date.replace(hour=int(current_hour), minute=int((current_hour % 1) * 60))
            slot_end = date.replace(
                hour=int(current_hour + duration),
                minute=int(((current_hour + duration) % 1) * 60)
            )

            # Check for existing bookings
            conflict = self.env['mh.booking'].search([
                ('zone_id', 'in', self.ids),
                ('booking_date_start', '<', slot_end),
                ('booking_date_end', '>', slot_start),
                ('state', 'not in', ['cancelled', 'completed', 'no_show']),
            ])

            if not conflict:
                slots.append({
                    'start': slot_start,
                    'end': slot_end,
                    'hour': current_hour,
                })

            current_hour += 1.0  # Move to next hour

        return slots

    def action_view_bookings(self):
        """Action to view all bookings for this zone."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Zone Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('zone_id', 'child_of', self.id)],
            'context': {'default_zone_id': self.id},
        }

    def action_view_staff(self):
        """Action to view all staff for this zone."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Zone Staff'),
            'res_model': 'mh.staff',
            'view_mode': 'tree,form',
            'domain': [('zone_ids', 'in', self.ids)],
        }


class MHZoneCoverage(models.Model):
    """
    Coverage areas within a zone.
    Can be used to define specific areas, buildings, or complexes.
    """
    _name = 'mh.zone.coverage'
    _description = 'MH Zone Coverage'
    _order = 'name'

    name = fields.Char(
        string='Coverage Area Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        index=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    zone_id = fields.Many2one(
        'mh.zone',
        string='Primary Zone',
        required=True,
        index=True,
        ondelete='cascade',
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Coverage code must be unique!'),
    ]
