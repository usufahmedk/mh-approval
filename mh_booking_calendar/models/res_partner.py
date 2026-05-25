# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    """
    Extension of res.partner to add MH Booking system integration.
    """
    _name = 'res.partner'
    _inherit = ['res.partner', 'mail.thread']

    # =====================================================================
    # ZONE ASSIGNMENT
    # =====================================================================
    partner_zone_id = fields.Many2one(
        'mh.zone',
        string='Default Zone',
        index=True,
        ondelete='set null',
        help='Default service zone for this customer.',
    )

    # =====================================================================
    # BOOKING INTEGRATION
    # =====================================================================
    booking_ids = fields.One2many(
        'mh.booking',
        'partner_id',
        string='Bookings',
        readonly=True,
    )
    booking_count = fields.Integer(
        string='Total Bookings',
        compute='_compute_booking_count',
        store=True,
    )
    active_booking_count = fields.Integer(
        string='Active Bookings',
        compute='_compute_active_booking_count',
        store=True,
    )
    completed_booking_count = fields.Integer(
        string='Completed Bookings',
        compute='_compute_completed_booking_count',
        store=True,
    )

    # Customer rating
    avg_rating = fields.Float(
        string='Average Rating',
        compute='_compute_avg_rating',
        digits=(5, 2),
    )
    total_ratings = fields.Integer(
        string='Total Ratings',
        compute='_compute_total_ratings',
        store=True,
    )

    # Customer category for booking priority
    customer_priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('vip', 'VIP'),
    ], string='Customer Priority', default='normal', tracking=True)

    # Access information
    access_instructions = fields.Text(
        string='Access Instructions',
        translate=True,
    )
    gate_code = fields.Char(
        string='Gate Code',
        copy=False,
    )
    building_name = fields.Char(
        string='Building Name',
        translate=True,
    )
    floor = fields.Char(
        string='Floor/Apartment',
    )
    landmark = fields.Char(
        string='Landmark',
        translate=True,
    )
    parking_instructions = fields.Text(
        string='Parking Instructions',
        translate=True,
    )
    preferred_language = fields.Many2one(
        'res.lang',
        string='Preferred Language',
        ondelete='set null',
    )

    # Contact preferences
    prefer_sms = fields.Boolean(
        string='Prefer SMS',
        default=True,
    )
    prefer_email = fields.Boolean(
        string='Prefer Email',
        default=True,
    )
    prefer_whatsapp = fields.Boolean(
        string='Prefer WhatsApp',
        default=False,
    )
    do_not_disturb = fields.Boolean(
        string='Do Not Disturb',
        default=False,
    )
    quiet_hours_start = fields.Char(
        string='Quiet Hours Start',
        help='e.g., 21:00',
    )
    quiet_hours_end = fields.Char(
        string='Quiet Hours End',
        help='e.g., 08:00',
    )

    # Notification preferences
    notify_booking_confirmation = fields.Boolean(
        string='Booking Confirmation',
        default=True,
    )
    notify_booking_reminder = fields.Boolean(
        string='Booking Reminder',
        default=True,
    )
    notify_booking_cancellation = fields.Boolean(
        string='Cancellation Notice',
        default=True,
    )
    notify_service_complete = fields.Boolean(
        string='Service Complete',
        default=True,
    )
    notify_feedback_request = fields.Boolean(
        string='Feedback Request',
        default=True,
    )

    # Payment information
    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Payment Terms',
        related='property_payment_term_id',
        readonly=False,
    )
    outstanding_balance = fields.Monetary(
        string='Outstanding Balance',
        compute='_compute_outstanding_balance',
        currency_field='currency_id',
    )

    # In Odoo 18, subscriptions are sale.order records with is_subscription=True
    subscription_ids = fields.One2many(
        'sale.order',
        'partner_id',
        string='AMC Subscriptions',
        domain=[('is_subscription', '=', True)],
        readonly=True,
    )
    subscription_count = fields.Integer(
        string='AMC Subscriptions',
        compute='_compute_subscription_count',
        store=True,
    )
    active_subscription_count = fields.Integer(
        string='Active Subscriptions',
        compute='_compute_active_subscription_count',
        store=True,
    )
    has_active_subscription = fields.Boolean(
        string='Has Active AMC',
        compute='_compute_has_active_subscription',
        store=True,
    )

    # =====================================================================
    # PROPERTY INFORMATION (for service delivery)
    # =====================================================================
    property_type = fields.Selection([
        ('apartment', 'Apartment'),
        ('villa', 'Villa'),
        ('row_house', 'Row House'),
        ('office', 'Office'),
        ('retail', 'Retail'),
        ('warehouse', 'Warehouse'),
        ('industrial', 'Industrial'),
        ('government', 'Government'),
        ('other', 'Other'),
    ], string='Property Type', default='apartment')
    property_size = fields.Float(
        string='Property Size (sqm)',
    )
    property_age_years = fields.Integer(
        string='Property Age (Years)',
    )
    number_of_floors = fields.Integer(
        string='Number of Floors',
    )
    number_of_bathrooms = fields.Integer(
        string='Number of Bathrooms',
    )
    number_of_bedrooms = fields.Integer(
        string='Number of Bedrooms',
    )
    has_pets = fields.Boolean(
        string='Has Pets',
        default=False,
    )
    pet_details = fields.Char(
        string='Pet Details',
        translate=True,
        help='Type and number of pets.',
    )
    has_security = fields.Boolean(
        string='Has Security',
        default=False,
    )

    # =====================================================================
    # SERVICE HISTORY
    # =====================================================================
    first_booking_date = fields.Date(
        string='First Booking',
        compute='_compute_first_booking_date',
        store=True,
    )
    last_booking_date = fields.Date(
        string='Last Booking',
        compute='_compute_last_booking_date',
        store=True,
    )
    customer_since = fields.Date(
        string='Customer Since',
        compute='_compute_customer_since',
        store=True,
    )
    total_revenue = fields.Monetary(
        string='Total Revenue',
        compute='_compute_total_revenue',
        currency_field='currency_id',
    )
    lifetime_value = fields.Monetary(
        string='Customer Lifetime Value',
        compute='_compute_lifetime_value',
        currency_field='currency_id',
    )

    # Risk assessment
    is_blacklisted = fields.Boolean(
        string='Blacklisted',
        default=False,
        copy=False,
    )
    blacklist_reason = fields.Text(
        string='Blacklist Reason',
        copy=False,
    )
    risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Risk Level', default='low', compute='_compute_risk_level', store=True)

    # Referral
    referred_by_id = fields.Many2one(
        'res.partner',
        string='Referred By',
        ondelete='set null',
        index=True,
        domain=[('customer_rank', '>', 0)],
    )
    referral_code = fields.Char(
        string='Referral Code',
        copy=False,
        readonly=True,
    )
    referral_count = fields.Integer(
        string='Referral Count',
        compute='_compute_referral_count',
        store=True,
    )

    # Notes
    booking_notes = fields.Text(
        string='Booking Notes',
        translate=True,
        help='Notes visible to field staff about this customer.',
    )

    # =====================================================================
    # COMPUTED FIELDS
    # =====================================================================
    @api.depends('booking_ids')
    def _compute_booking_count(self):
        """Compute total booking count."""
        for record in self:
            record.booking_count = len(record.booking_ids)

    @api.depends('booking_ids.state')
    def _compute_active_booking_count(self):
        """Compute active booking count."""
        for record in self:
            record.active_booking_count = len(
                record.booking_ids.filtered(
                    lambda b: b.state in ['draft', 'confirmed', 'in_progress']
                )
            )

    @api.depends('booking_ids.state')
    def _compute_completed_booking_count(self):
        """Compute completed booking count."""
        for record in self:
            record.completed_booking_count = len(
                record.booking_ids.filtered(lambda b: b.state == 'completed')
            )

    @api.depends('booking_ids.customer_rating')
    def _compute_avg_rating(self):
        """Compute average customer rating."""
        for record in self:
            ratings = record.booking_ids.filtered(
                lambda b: b.customer_rating > 0
            ).mapped('customer_rating')
            record.avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    @api.depends('booking_ids.customer_rating')
    def _compute_total_ratings(self):
        """Compute total number of ratings."""
        for record in self:
            record.total_ratings = len(
                record.booking_ids.filtered(lambda b: b.customer_rating > 0)
            )

    @api.depends('subscription_ids')
    def _compute_subscription_count(self):
        """Compute total subscription count."""
        for record in self:
            record.subscription_count = len(record.subscription_ids)

    @api.depends('subscription_ids.state')
    def _compute_active_subscription_count(self):
        """Compute active subscription count."""
        for record in self:
            record.active_subscription_count = len(
                record.subscription_ids.filtered(lambda s: s.state == 'open')
            )

    @api.depends('subscription_ids')
    def _compute_has_active_subscription(self):
        """Check if customer has active subscription."""
        for record in self:
            record.has_active_subscription = any(
                s.state == 'open' for s in record.subscription_ids
            )

    @api.depends('booking_ids.booking_date')
    def _compute_first_booking_date(self):
        """Compute first booking date."""
        for record in self:
            bookings = record.booking_ids.filtered(
                lambda b: b.state != 'cancelled'
            ).sorted(key='booking_date')
            record.first_booking_date = bookings[0].booking_date if bookings else False

    @api.depends('booking_ids.booking_date')
    def _compute_last_booking_date(self):
        """Compute last booking date."""
        for record in self:
            bookings = record.booking_ids.filtered(
                lambda b: b.state != 'cancelled'
            ).sorted(key='booking_date', reverse=True)
            record.last_booking_date = bookings[0].booking_date if bookings else False

    def _compute_customer_since(self):
        """Compute customer since date (first contact)."""
        for record in self:
            record.customer_since = record.create_date.date() if record.create_date else False

    def _compute_outstanding_balance(self):
        """Compute outstanding balance from invoices."""
        for record in self:
            # Get unpaid invoices
            invoices = self.env['account.move'].search([
                ('partner_id', '=', record.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid'),
            ])
            record.outstanding_balance = sum(invoices.mapped('amount_residual'))

    def _compute_total_revenue(self):
        """Compute total revenue from completed bookings."""
        for record in self:
            completed = record.booking_ids.filtered(
                lambda b: b.state == 'completed'
            )
            record.total_revenue = sum(completed.mapped('price_total'))

    def _compute_lifetime_value(self):
        """Compute customer lifetime value (projected)."""
        for record in self:
            # Base on total revenue and customer tenure
            months_customer = 1
            if record.customer_since:
                delta = fields.Date.today() - record.customer_since
                months_customer = max(1, delta.days / 30)

            if months_customer > 0 and record.total_revenue > 0:
                monthly_value = record.total_revenue / months_customer
                # Project for 24 months
                record.lifetime_value = monthly_value * 24
            else:
                record.lifetime_value = 0.0

    @api.depends('outstanding_balance', 'is_blacklisted', 'total_ratings', 'avg_rating')
    def _compute_risk_level(self):
        """Compute risk level for this customer."""
        for record in self:
            risk = 'low'

            # Check blacklist
            if record.is_blacklisted:
                risk = 'high'
            # Check outstanding balance
            elif record.outstanding_balance > 10000:
                risk = 'medium'
            # Check negative ratings
            elif record.avg_rating > 0 and record.avg_rating < 2.5:
                risk = 'medium'

            record.risk_level = risk

    @api.depends('referral_code')
    def _compute_referral_count(self):
        """Count referrals by this customer."""
        for record in self:
            record.referral_count = self.search_count([
                ('referred_by_id', '=', record.id),
            ])

    # =====================================================================
    # CONSTRAINTS
    # =====================================================================
    @api.constrains('referral_code')
    def _check_unique_referral_code(self):
        """Ensure referral code is unique."""
        for record in self:
            if record.referral_code:
                existing = self.search([
                    ('id', '!=', record.id),
                    ('referral_code', '=', record.referral_code),
                ])
                if existing:
                    raise ValidationError(
                        _('Referral code "%s" is already in use.')
                        % record.referral_code
                    )

    # =====================================================================
    # ACTION METHODS
    # =====================================================================
    def action_view_bookings(self):
        """Action to view all bookings for this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_subscriptions(self):
        """Action to view all subscriptions for this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('AMC Subscriptions'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('is_subscription', '=', True),
            ],
            'context': {'default_partner_id': self.id},
        }

    def action_create_booking(self):
        """Create a new booking for this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Booking'),
            'res_model': 'mh.booking',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.id,
                'default_zone_id': self.partner_zone_id.id,
                'default_contact_id': self.id,
            },
        }

    def action_view_invoices(self):
        """Action to view all invoices for this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
            ],
            'context': {'default_move_type': 'out_invoice', 'default_partner_id': self.id},
        }

    def action_blacklist(self):
        """Blacklist this customer."""
        self.ensure_one()
        self.write({'is_blacklisted': True})
        return True

    def action_remove_blacklist(self):
        """Remove customer from blacklist."""
        self.write({
            'is_blacklisted': False,
            'blacklist_reason': False,
        })

    def generate_referral_code(self):
        """Generate a unique referral code for this customer."""
        for record in self:
            if not record.referral_code:
                # Generate code: first 3 letters of name + 4 random digits
                name_part = (record.name or '').upper()[:3]
                import random
                rand_part = random.randint(1000, 9999)
                code = f'{name_part}{rand_part}'
                record.write({'referral_code': code})

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate referral code."""
        for vals in vals_list:
            if not vals.get('referral_code') and vals.get('customer_rank', 0) > 0:
                # Will be generated in write
                pass
        return super().create(vals_list)

    def write(self, vals):
        """Override write to auto-generate referral code."""
        result = super().write(vals)
        if 'customer_rank' in vals and vals['customer_rank'] > 0:
            for record in self:
                if not record.referral_code:
                    record.generate_referral_code()
        return result
