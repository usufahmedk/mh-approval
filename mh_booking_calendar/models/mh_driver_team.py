# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MHDriverTeam(models.Model):
    """
    Driver teams responsible for transportation and logistics.
    Each team has a team lead and multiple driver members.
    """
    _name = 'mh.driver.team'
    _description = 'MH Driver Team'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Team Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Team Code',
        index=True,
        size=10,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this team will not be available.',
    )

    # Team lead
    team_lead_id = fields.Many2one(
        'hr.employee',
        string='Team Lead',
        required=True,
        index=True,
        ondelete='restrict',
        domain=[('is_team_lead', '=', True)],
        tracking=True,
    )
    team_lead_phone = fields.Char(
        string='Team Lead Phone',
        related='team_lead_id.phone',
        readonly=True,
    )

    # Team members (drivers)
    member_ids = fields.One2many(
        'mh.driver.team.member',
        'team_id',
        string='Team Members',
    )
    member_count = fields.Integer(
        string='Member Count',
        compute='_compute_member_count',
        store=True,
    )

    # Driver members (for easy filtering)
    driver_ids = fields.Many2many(
        'hr.employee',
        'mh_driver_team_driver_rel',
        'team_id',
        'driver_id',
        string='Drivers',
        domain=[('is_team_lead', '=', False)],
    )
    driver_count = fields.Integer(
        string='Driver Count',
        compute='_compute_driver_count',
        store=True,
    )

    # Vehicle assignment
    vehicle_id = fields.Many2one(
        'mh.vehicle',
        string='Assigned Vehicle',
        ondelete='set null',
    )
    vehicle_license_plate = fields.Char(
        string='Vehicle Plate',
        related='vehicle_id.license_plate',
        readonly=True,
    )

    # Capacity
    max_stops_per_day = fields.Integer(
        string='Max Stops per Day',
        default=10,
        help='Maximum number of customer stops per day for this team.',
    )
    max_distance_km = fields.Float(
        string='Max Distance (km)',
        default=100.0,
        help='Maximum distance the team can travel per day.',
    )

    # Zones covered
    zone_ids = fields.Many2many(
        'mh.zone',
        'mh_driver_team_zone_rel',
        'team_id',
        'zone_id',
        string='Covered Zones',
    )

    # Operating hours
    working_hour_start = fields.Float(
        string='Working Hours Start',
        default=7.0,
        widget='float_time',
    )
    working_hour_end = fields.Float(
        string='Working Hours End',
        default=19.0,
        widget='float_time',
    )
    working_days = fields.Char(
        string='Working Days',
        default='1,2,3,4,5,6',  # Monday to Saturday
        help='Comma-separated day numbers (1=Monday, 7=Sunday).',
    )

    # Current location tracking
    current_location = fields.Char(
        string='Current Location',
        help='Last known location of the team.',
    )
    last_location_update = fields.Datetime(
        string='Last Location Update',
    )
    is_on_route = fields.Boolean(
        string='On Route',
        default=False,
    )

    # Booking assignments
    booking_ids = fields.One2many(
        'mh.booking',
        'driver_team_id',
        string='Assigned Bookings',
        readonly=True,
    )
    today_booking_count = fields.Integer(
        string="Today's Bookings",
        compute='_compute_today_booking_count',
    )
    week_booking_count = fields.Integer(
        string="This Week's Bookings",
        compute='_compute_week_booking_count',
    )

    # Statistics
    total_trips = fields.Integer(
        string='Total Trips',
        compute='_compute_statistics',
        store=True,
    )
    total_distance = fields.Float(
        string='Total Distance (km)',
        compute='_compute_statistics',
        store=True,
    )
    avg_trip_duration = fields.Float(
        string='Avg. Trip Duration (hrs)',
        compute='_compute_statistics',
        store=True,
    )

    # Performance
    on_time_rate = fields.Float(
        string='On-Time Rate (%)',
        compute='_compute_performance',
        digits=(5, 2),
    )
    customer_rating = fields.Float(
        string='Customer Rating',
        compute='_compute_performance',
        digits=(5, 2),
    )

    # Color for display
    color = fields.Integer(
        string='Color',
        default=0,
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
    @api.depends('member_ids')
    def _compute_member_count(self):
        """Compute the number of team members."""
        for record in self:
            record.member_count = len(record.member_ids)

    @api.depends('driver_ids')
    def _compute_driver_count(self):
        """Compute the number of drivers."""
        for record in self:
            record.driver_count = len(record.driver_ids)

    @api.depends('booking_ids')
    def _compute_today_booking_count(self):
        """Compute today's booking count for this team."""
        today = fields.Date.context_today(self)
        for record in self:
            count = self.env['mh.booking'].search_count([
                ('driver_team_id', '=', record.id),
                ('booking_date', '=', today),
                ('state', 'not in', ['cancelled']),
            ])
            record.today_booking_count = count

    @api.depends('booking_ids')
    def _compute_week_booking_count(self):
        """Compute this week's booking count for this team."""
        today = fields.Date.context_today(self)
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        for record in self:
            count = self.env['mh.booking'].search_count([
                ('driver_team_id', '=', record.id),
                ('booking_date', '>=', start_of_week),
                ('booking_date', '<=', end_of_week),
                ('state', 'not in', ['cancelled']),
            ])
            record.week_booking_count = count

    def _compute_statistics(self):
        """Compute team statistics."""
        for record in self:
            bookings = self.env['mh.booking'].search([
                ('driver_team_id', '=', record.id),
                ('state', '=', 'completed'),
            ])
            record.total_trips = len(bookings)
            record.total_distance = sum(bookings.mapped('distance_traveled') or [0])
            if bookings:
                record.avg_trip_duration = sum(bookings.mapped('duration')) / len(bookings)
            else:
                record.avg_trip_duration = 0.0

    def _compute_performance(self):
        """Compute team performance metrics."""
        for record in self:
            bookings = self.env['mh.booking'].search([
                ('driver_team_id', '=', record.id),
                ('state', '=', 'completed'),
            ])
            if not bookings:
                record.on_time_rate = 0.0
                record.customer_rating = 0.0
            else:
                on_time = len([b for b in bookings if b.is_on_time])
                record.on_time_rate = (on_time / len(bookings) * 100) if bookings else 0.0
                ratings = [b.customer_rating for b in bookings if b.customer_rating]
                record.customer_rating = sum(ratings) / len(ratings) if ratings else 0.0

    # =====================================================================
    # CONSTRAINTS
    # =====================================================================
    @api.constrains('team_lead_id')
    def _check_team_lead(self):
        """Ensure team lead is marked as team lead."""
        for record in self:
            if record.team_lead_id and not record.team_lead_id.is_team_lead:
                raise ValidationError(
                    _('The selected team lead must have "Is Team Lead" checked.')
                )

    @api.constrains('member_ids')
    def _check_member_duplicates(self):
        """Ensure no duplicate members."""
        for record in self:
            member_ids = record.member_ids.mapped('staff_id').ids
            if len(member_ids) != len(set(member_ids)):
                raise ValidationError(
                    _('Duplicate team members are not allowed.')
                )

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
        """Check if given date is a working day for this team."""
        self.ensure_one()
        working_days = self.get_working_days()
        return date.weekday() + 1 in working_days

    def get_available_capacity(self, date):
        """Get available capacity for a given date."""
        self.ensure_one()
        if not self.is_working_day(date):
            return 0

        booked = self.env['mh.booking'].search_count([
            ('driver_team_id', '=', self.id),
            ('booking_date', '=', date),
            ('state', 'not in', ['cancelled']),
        ])
        return max(0, self.max_stops_per_day - booked)

    # =====================================================================
    # ACTION METHODS
    # =====================================================================
    def action_view_bookings(self):
        """Action to view all bookings for this team."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Team Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'list,form,calendar',
            'domain': [('driver_team_id', '=', self.id)],
            'context': {'default_driver_team_id': self.id},
        }

    def action_view_members(self):
        """Action to view team members."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Team Members'),
            'res_model': 'mh.driver.team.member',
            'view_mode': 'list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set team lead as driver."""
        for vals in vals_list:
            if vals.get('team_lead_id') and 'driver_ids' not in vals:
                # Add team lead to drivers if not already present
                vals['driver_ids'] = [(4, vals['team_lead_id'])]
        return super().create(vals_list)

    def write(self, vals):
        """Override write to sync team lead with drivers."""
        result = super().write(vals)
        if 'team_lead_id' in vals:
            for record in self:
                if record.team_lead_id:
                    # Ensure team lead is in driver list
                    if record.team_lead_id.id not in record.driver_ids.ids:
                        record.write({'driver_ids': [(4, record.team_lead_id.id)]})
        return result


class MHDriverTeamMember(models.Model):
    """
    Team members within a driver team.
    """
    _name = 'mh.driver.team.member'
    _description = 'MH Driver Team Member'
    _order = 'sequence, id'

    name = fields.Char(
        string='Name',
        related='staff_id.name',
        readonly=True,
    )
    staff_id = fields.Many2one(
        'hr.employee',
        string='Staff Member',
        required=True,
        index=True,
        ondelete='cascade',
    )
    team_id = fields.Many2one(
        'mh.driver.team',
        string='Team',
        required=True,
        index=True,
        ondelete='cascade',
    )
    role = fields.Selection([
        ('driver', 'Driver'),
        ('helper', 'Helper'),
        ('technician', 'Technician'),
        ('coordinator', 'Coordinator'),
    ], string='Role', default='driver')
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    is_active = fields.Boolean(
        string='Active',
        default=True,
    )
    date_from = fields.Date(
        string='Start Date',
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string='End Date',
    )
    notes = fields.Text(
        string='Notes',
    )

    @api.constrains('staff_id', 'team_id')
    def _check_unique_member(self):
        """Ensure staff member is not in the same team twice."""
        for record in self:
            existing = self.search([
                ('id', '!=', record.id),
                ('staff_id', '=', record.staff_id.id),
                ('team_id', '=', record.team_id.id),
            ])
            if existing:
                raise ValidationError(
                    _('Staff member "%s" is already in this team.')
                    % record.staff_id.name
                )


# Import timedelta for date calculations
from datetime import timedelta
