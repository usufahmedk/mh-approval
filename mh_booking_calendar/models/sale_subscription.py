# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleSubscription(models.Model):
    """
    Extension of sale.subscription for AMC (Annual Maintenance Contract) management.
    Links subscriptions to zones and provides booking schedule generation.
    """
    _name = 'sale.subscription'
    _inherit = ['sale.subscription', 'mail.thread']

    # =====================================================================
    # ZONE AND BOOKING INTEGRATION
    # =====================================================================
    zone_id = fields.Many2one(
        'mh.zone',
        string='Service Zone',
        index=True,
        ondelete='cascade',
        tracking=True,
    )
    subscription_type = fields.Selection([
        ('amc', 'AMC (Annual Maintenance Contract)'),
        ('quarterly', 'Quarterly Service'),
        ('monthly', 'Monthly Service'),
        ('custom', 'Custom'),
    ], string='Subscription Type', default='amc', tracking=True)

    # AMC specific fields
    contract_number = fields.Char(
        string='Contract Number',
        copy=False,
        readonly=True,
    )
    contract_start_date = fields.Date(
        string='Contract Start Date',
        tracking=True,
    )
    contract_end_date = fields.Date(
        string='Contract End Date',
        tracking=True,
    )
    contract_duration_months = fields.Integer(
        string='Contract Duration (Months)',
        default=12,
    )

    # Service schedule
    frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('biannual', 'Bi-annual'),
        ('annual', 'Annual'),
    ], string='Service Frequency', default='quarterly')
    visits_per_year = fields.Integer(
        string='Visits Per Year',
        compute='_compute_visits_per_year',
        store=True,
    )
    next_service_date = fields.Date(
        string='Next Service Date',
        compute='_compute_next_service_date',
        store=True,
    )
    auto_generate_bookings = fields.Boolean(
        string='Auto Generate Bookings',
        default=True,
        help='Automatically create bookings based on the service schedule.',
    )
    days_before_to_notify = fields.Integer(
        string='Days Before to Notify',
        default=7,
        help='Days before service date to generate booking.',
    )
    preferred_day_of_week = fields.Selection([
        ('1', 'Monday'),
        ('2', 'Tuesday'),
        ('3', 'Wednesday'),
        ('4', 'Thursday'),
        ('5', 'Friday'),
        ('6', 'Saturday'),
        ('7', 'Sunday'),
    ], string='Preferred Day of Week')
    preferred_time_slot = fields.Selection([
        ('morning', 'Morning (8AM - 12PM)'),
        ('afternoon', 'Afternoon (12PM - 5PM)'),
        ('evening', 'Evening (5PM - 8PM)'),
    ], string='Preferred Time Slot')

    # Coverage
    coverage_area_ids = fields.Many2many(
        'mh.zone.coverage',
        'sale_subscription_coverage_rel',
        'subscription_id',
        'coverage_id',
        string='Coverage Areas',
    )

    # Linked bookings
    booking_ids = fields.One2many(
        'mh.booking',
        'subscription_id',
        string='AMC Bookings',
        readonly=True,
    )
    booking_count = fields.Integer(
        string='Booking Count',
        compute='_compute_booking_count',
        store=True,
    )
    completed_booking_count = fields.Integer(
        string='Completed Bookings',
        compute='_compute_completed_booking_count',
        store=True,
    )
    pending_booking_count = fields.Integer(
        string='Pending Bookings',
        compute='_compute_pending_booking_count',
        store=True,
    )

    # SLA and priority
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal')
    service_level_agreement = fields.Many2one(
        'mh.sla',
        string='SLA',
        ondelete='set null',
    )
    response_time_hours = fields.Integer(
        string='Response Time (Hours)',
        related='service_level_agreement.response_time_hours',
        readonly=True,
    )
    resolution_time_hours = fields.Integer(
        string='Resolution Time (Hours)',
        related='service_level_agreement.resolution_time_hours',
        readonly=True,
    )

    # Contract value
    total_contract_value = fields.Monetary(
        string='Total Contract Value',
        compute='_compute_total_contract_value',
        store=True,
        currency_field='currency_id',
    )
    revenue_per_visit = fields.Monetary(
        string='Revenue Per Visit',
        compute='_compute_revenue_per_visit',
        store=True,
        currency_field='currency_id',
    )

    # Compliance tracking
    compliance_status = fields.Selection([
        ('compliant', 'Compliant'),
        ('at_risk', 'At Risk'),
        ('breached', 'Breached'),
    ], string='Compliance Status', compute='_compute_compliance_status', store=True)
    last_service_date = fields.Date(
        string='Last Service Date',
        compute='_compute_last_service_date',
        store=True,
    )
    missed_visits = fields.Integer(
        string='Missed Visits',
        compute='_compute_missed_visits',
        store=True,
    )

    # Customer hierarchy
    customer_category = fields.Selection([
        ('individual', 'Individual'),
        ('residential', 'Residential Complex'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('government', 'Government'),
    ], string='Customer Category', default='individual')

    # Property details
    property_type = fields.Selection([
        ('apartment', 'Apartment'),
        ('villa', 'Villa'),
        ('office', 'Office'),
        ('warehouse', 'Warehouse'),
        ('retail', 'Retail'),
        ('other', 'Other'),
    ], string='Property Type')
    property_size_sqm = fields.Float(
        string='Property Size (sqm)',
    )
    floors_count = fields.Integer(
        string='Number of Floors',
    )
    bathroom_count = fields.Integer(
        string='Number of Bathrooms',
    )
    bedroom_count = fields.Integer(
        string='Number of Bedrooms',
    )

    # Special requirements
    special_instructions = fields.Text(
        string='Special Instructions',
        translate=True,
    )
    access_instructions = fields.Text(
        string='Access Instructions',
        translate=True,
    )
    key_location = fields.Text(
        string='Key/Access Location',
        translate=True,
    )
    parking_available = fields.Boolean(
        string='Parking Available',
        default=False,
    )

    # Notes
    contract_notes = fields.Text(
        string='Contract Notes',
        translate=True,
    )

    # =====================================================================
    # MH BOOKING CALENDAR INTEGRATION FIELDS
    # =====================================================================
    mh_booking_type_id = fields.Many2one(
        'mh.booking.type',
        string='Booking Type',
        help='Default booking type for AMC bookings'
    )
    mh_zone_id = fields.Many2one(
        'mh.zone',
        string='Zone',
        help='Default zone for AMC bookings'
    )
    mh_staff_ids = fields.Many2many(
        'mh.staff',
        'subscription_staff_rel',
        'subscription_id',
        'staff_id',
        string='Assigned Staff',
        help='Fixed staff assigned to this AMC contract'
    )
    mh_booking_ids = fields.One2many(
        'mh.booking',
        'subscription_id',
        string='AMC Bookings',
        readonly=True
    )
    total_contracted_visits = fields.Integer(
        string='Total Contracted Visits',
        help='Total number of visits in the contract'
    )
    visits_completed = fields.Integer(
        string='Visits Completed',
        compute='_compute_visits_completed',
        store=True
    )
    visits_remaining = fields.Integer(
        string='Visits Remaining',
        compute='_compute_visits_remaining',
        store=True
    )

    # Pause options for pending payment
    payment_pending_pause = fields.Boolean(
        string='Paused - Pending Payment',
        help='Manually pause bookings until payment is received'
    )
    pause_reason = fields.Selection([
        ('pending_payment', 'Pending Payment'),
        ('seasonal', 'Seasonal'),
        ('client_request', 'Client Request'),
    ], string='Pause Reason')
    pause_date = fields.Date(string='Paused Date')

    # PPM (Preventive Maintenance) scheduling
    is_ppm = fields.Boolean(
        string='Preventive Maintenance',
        help='Enable preventive maintenance scheduling'
    )
    ppm_schedule = fields.Char(
        string='PPM Schedule',
        help='Quarterly schedule e.g. Q1,Q2,Q3,Q4'
    )

    # =====================================================================
    # COMPUTED FIELDS
    # =====================================================================
    @api.depends('frequency')
    def _compute_visits_per_year(self):
        """Compute number of visits per year based on frequency."""
        frequency_map = {
            'weekly': 52,
            'biweekly': 26,
            'monthly': 12,
            'quarterly': 4,
            'biannual': 2,
            'annual': 1,
        }
        for record in self:
            record.visits_per_year = frequency_map.get(record.frequency, 0)

    @api.depends('booking_ids', 'booking_ids.booking_date', 'booking_ids.state', 'frequency')
    def _compute_next_service_date(self):
        """Compute the next service date based on bookings and frequency."""
        for record in self:
            today = fields.Date.context_today(record)

            # Find next unconfirmed booking
            upcoming = self.env['mh.booking'].search([
                ('subscription_id', '=', record.id),
                ('booking_date', '>=', today),
                ('state', 'in', ['draft', 'confirmed']),
            ], order='booking_date asc', limit=1)

            if upcoming:
                record.next_service_date = upcoming.booking_date
            else:
                # Calculate next based on frequency
                record.next_service_date = False

    @api.depends('booking_ids')
    def _compute_booking_count(self):
        """Compute total booking count for this subscription."""
        for record in self:
            record.booking_count = len(record.booking_ids)

    @api.depends('booking_ids.state')
    def _compute_completed_booking_count(self):
        """Compute completed booking count."""
        for record in self:
            record.completed_booking_count = len(
                record.booking_ids.filtered(lambda b: b.state == 'completed')
            )

    @api.depends('booking_ids.state')
    def _compute_pending_booking_count(self):
        """Compute pending booking count."""
        for record in self:
            record.pending_booking_count = len(
                record.booking_ids.filtered(
                    lambda b: b.state in ['draft', 'confirmed', 'in_progress']
                )
            )

    @api.depends('amount', 'visits_per_year')
    def _compute_revenue_per_visit(self):
        """Compute revenue per visit."""
        for record in self:
            if record.visits_per_year and record.amount > 0:
                record.revenue_per_visit = record.amount / record.visits_per_year
            else:
                record.revenue_per_visit = record.amount

    @api.depends('amount', 'contract_duration_months')
    def _compute_total_contract_value(self):
        """Compute total contract value."""
        for record in self:
            years = record.contract_duration_months / 12.0
            record.total_contract_value = record.amount * years

    @api.depends('booking_ids', 'booking_ids.state', 'last_service_date')
    def _compute_compliance_status(self):
        """Compute compliance status based on missed visits."""
        for record in self:
            if record.missed_visits > 0:
                record.compliance_status = 'breached'
            elif record.last_service_date:
                # Check if last service was within expected timeframe
                if record.next_service_date:
                    if fields.Date.today() > record.next_service_date:
                        record.compliance_status = 'at_risk'
                    else:
                        record.compliance_status = 'compliant'
                else:
                    record.compliance_status = 'compliant'
            else:
                record.compliance_status = 'compliant'

    @api.depends('booking_ids.booking_date', 'booking_ids.state')
    def _compute_last_service_date(self):
        """Compute the last completed service date."""
        for record in self:
            completed = record.booking_ids.filtered(
                lambda b: b.state == 'completed'
            ).sorted(key='booking_date', reverse=True)
            record.last_service_date = completed[0].booking_date if completed else False

    @api.depends('frequency', 'contract_start_date', 'completed_booking_count')
    def _compute_missed_visits(self):
        """Compute number of missed visits."""
        for record in self:
            if not record.contract_start_date or not record.frequency:
                record.missed_visits = 0
                continue

            # Calculate expected visits since contract start
            today = fields.Date.context_today(record)
            months_since_start = (
                (today.year - record.contract_start_date.year) * 12 +
                today.month - record.contract_start_date.month
            )

            frequency_months = {
                'weekly': 0.25,
                'biweekly': 0.5,
                'monthly': 1,
                'quarterly': 3,
                'biannual': 6,
                'annual': 12,
            }
            months = frequency_months.get(record.frequency, 3)
            expected_visits = int(months_since_start / months) if months else 0

            record.missed_visits = max(0, expected_visits - record.completed_booking_count)

    # =====================================================================
    # MH BOOKING CALENDAR INTEGRATION COMPUTED FIELDS
    # =====================================================================
    @api.depends('mh_booking_ids.state')
    def _compute_visits_completed(self):
        """Compute number of completed AMC visits."""
        for record in self:
            record.visits_completed = len(record.mh_booking_ids.filtered_domain([
                ('state', '=', 'completed')
            ]))

    @api.depends('total_contracted_visits', 'visits_completed')
    def _compute_visits_remaining(self):
        """Compute remaining visits in contract."""
        for record in self:
            record.visits_remaining = record.total_contracted_visits - record.visits_completed

    # =====================================================================
    # MH BOOKING CALENDAR INTEGRATION METHODS
    # =====================================================================
    def _create_booking_from_subscription(self):
        """
        Create a booking from subscription.
        Called by cron job or on demand.
        """
        self.ensure_one()
        if self.payment_pending_pause:
            # Contract is paused
            return False

        if self.state != 'open':
            return False

        # Check if booking already exists for next period
        next_date = self._get_next_booking_date()
        if not next_date:
            return False

        existing = self.env['mh.booking'].search([
            ('subscription_id', '=', self.id),
            ('booking_date', '=', next_date),
        ], limit=1)

        if existing:
            return existing

        # Create booking
        booking = self.env['mh.booking'].create({
            'subscription_id': self.id,
            'booking_type_id': self.mh_booking_type_id.id,
            'zone_id': self.mh_zone_id.id,
            'staff_ids': [(6, 0, self.mh_staff_ids.ids)],
            'booking_date': next_date,
            'partner_id': self.partner_id.id,
            'state': 'draft',
        })

        return booking

    def _get_next_booking_date(self):
        """
        Get the next booking date based on subscription frequency.
        Override this method for custom frequency logic.
        """
        self.ensure_one()
        # Get last booking date
        last_booking = self.mh_booking_ids.sorted('booking_date', reverse=True)[:1]

        if not last_booking:
            # First booking - use start_date
            return self.start_date

        # Calculate next date based on plan
        frequency_map = {
            'monthly': 30,
            'quarterly': 90,
            'biweekly': 14,
            'weekly': 7,
        }
        interval = frequency_map.get(self.frequency, 30)
        return last_booking.booking_date + timedelta(days=interval)

    def action_pause_contract(self):
        """Open wizard to pause contract"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pause Contract',
            'res_model': 'mh.pause.contract.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_resume_contract(self):
        """Resume paused contract"""
        self.write({
            'payment_pending_pause': False,
            'pause_reason': False,
            'pause_date': False,
        })

    def check_overdue_visits(self):
        """
        Cron job to flag overdue visits.
        Check for scheduled visits past due date.
        """
        today = fields.Date.today()
        overdue_subs = self.search([
            ('state', '=', 'open'),
            ('end_date', '<', today),
            ('visits_remaining', '>', 0),
        ])
        # Flag for review (could send notification)
        return True

    # =====================================================================
    # CONSTRAINTS
    # =====================================================================
    @api.constrains('contract_start_date', 'contract_end_date')
    def _check_contract_dates(self):
        """Ensure contract dates are valid."""
        for record in self:
            if record.contract_end_date and record.contract_start_date:
                if record.contract_end_date <= record.contract_start_date:
                    raise ValidationError(
                        _('Contract end date must be after start date.')
                    )

    # =====================================================================
    # ACTION METHODS
    # =====================================================================
    def action_view_bookings(self):
        """Action to view all bookings for this subscription."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('AMC Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_subscription_id': self.id},
        }

    def action_create_booking(self):
        """Create a new booking for this subscription."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please set a customer first.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create AMC Booking'),
            'res_model': 'mh.booking',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_subscription_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_zone_id': self.zone_id.id,
                'default_is_amc_booking': True,
            },
        }

    def action_generate_scheduled_bookings(self):
        """Generate bookings for the next period based on frequency."""
        self.ensure_one()
        if not self.auto_generate_bookings:
            raise UserError(
                _('Auto-generate bookings is disabled for this subscription.')
            )

        # Calculate next booking dates
        last_date = self.next_service_date or fields.Date.context_today(self)
        frequency_days = {
            'weekly': 7,
            'biweekly': 14,
            'monthly': 30,
            'quarterly': 90,
            'biannual': 180,
            'annual': 365,
        }
        interval = frequency_days.get(self.frequency, 30)

        bookings = self.env['mh.booking']
        for i in range(3):  # Generate next 3 bookings
            next_date = fields.Date.add(last_date, days=interval * (i + 1))

            # Adjust to preferred day if set
            if self.preferred_day_of_week:
                target_day = int(self.preferred_day_of_week)
                current_day = next_date.weekday() + 1
                days_to_add = (target_day - current_day) % 7
                next_date = fields.Date.add(next_date, days=days_to_add)

            booking_vals = {
                'subscription_id': self.id,
                'partner_id': self.partner_id.id,
                'zone_id': self.zone_id.id,
                'booking_date': next_date,
                'booking_type_id': self.line_ids[0].product_id.id if self.line_ids else False,
                'state': 'draft',
            }
            bookings |= self.env['mh.booking'].create(booking_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', bookings.ids)],
        }

    def action_view_schedule(self):
        """View subscription schedule calendar."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Schedule'),
            'res_model': 'mh.booking',
            'view_mode': 'calendar',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_subscription_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate contract number."""
        for vals in vals_list:
            if not vals.get('contract_number'):
                vals['contract_number'] = self.env['ir.sequence'].next_by_code(
                    'sale.subscription.contract'
                ) or 'AMC-0001'
        return super().create(vals_list)


class MHServiceLevelAgreement(models.Model):
    """
    Service Level Agreements for subscription contracts.
    """
    _name = 'mh.sla'
    _description = 'MH Service Level Agreement'
    _order = 'name'

    name = fields.Char(
        string='SLA Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        index=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )

    # Response and resolution times
    response_time_hours = fields.Integer(
        string='Response Time (Hours)',
        default=24,
        help='Maximum time to respond to a service request.',
    )
    resolution_time_hours = fields.Integer(
        string='Resolution Time (Hours)',
        default=72,
        help='Maximum time to resolve a service request.',
    )

    # Availability commitment
    availability_percent = fields.Float(
        string='Availability (%)',
        default=99.5,
        digits=(5, 2),
        help='Committed uptime percentage.',
    )

    # Penalty clause
    has_penalty = fields.Boolean(
        string='Has Penalty Clause',
        default=False,
    )
    penalty_description = fields.Text(
        string='Penalty Description',
        translate=True,
    )

    # Subscription count
    subscription_count = fields.Integer(
        string='Active Subscriptions',
        compute='_compute_subscription_count',
    )

    def _compute_subscription_count(self):
        """Compute number of subscriptions using this SLA."""
        for record in self:
            record.subscription_count = self.env['sale.subscription'].search_count([
                ('service_level_agreement', '=', record.id),
                ('state', '=', 'open'),
            ])

    def action_view_subscriptions(self):
        """View all subscriptions with this SLA."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('SLA Subscriptions'),
            'res_model': 'sale.subscription',
            'view_mode': 'tree,form',
            'domain': [('service_level_agreement', '=', self.id)],
        }
