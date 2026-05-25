# -*- coding: utf-8 -*-

import re
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.date_utils import start_of, end_of, add, subtract

_logger = logging.getLogger(__name__)


class MHBooking(models.Model):
    """
    Main booking model for M&H Technical Services.
    Represents a scheduled service appointment.
    """
    _name = 'mh.booking'
    _description = 'MH Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'booking_date_start desc'

    # =====================================================================
    # CORE FIELDS
    # =====================================================================
    name = fields.Char(
        string='Booking Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default='New',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ], string='Status', default='draft', tracking=True, copy=False)

    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this booking will be archived.',
    )

    # =====================================================================
    # CUSTOMER & CONTACT
    # =====================================================================
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        index=True,
        tracking=True,
        ondelete='restrict',
    )
    partner_phone = fields.Char(
        string='Phone',
        related='partner_id.phone',
        store=True,
    )
    partner_mobile = fields.Char(
        string='Mobile',
        related='partner_id.mobile',
        store=True,
    )
    partner_email = fields.Char(
        string='Email',
        related='partner_id.email',
        store=True,
    )
    contact_id = fields.Many2one(
        'res.partner',
        string='Contact Person',
        domain="[('parent_id', '=', partner_id)]",
        ondelete='set null',
    )
    delivery_address = fields.Text(
        string='Service Address',
        compute='_compute_delivery_address',
        store=True,
    )

    # =====================================================================
    # BOOKING TYPE & SERVICE DETAILS
    # =====================================================================
    booking_type_id = fields.Many2one(
        'mh.booking.type',
        string='Booking Type',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    description = fields.Text(
        string='Service Description',
        translate=True,
    )
    property_values = fields.One2many(
        'mh.booking.property.value',
        'booking_id',
        string='Property Values',
    )

    # =====================================================================
    # ZONE ASSIGNMENT
    # =====================================================================
    zone_id = fields.Many2one(
        'mh.zone',
        string='Zone',
        required=True,
        index=True,
        tracking=True,
        ondelete='restrict',
    )
    zone_code = fields.Char(
        string='Zone Code',
        related='zone_id.code',
        store=True,
    )

    # =====================================================================
    # SCHEDULING
    # =====================================================================
    booking_date = fields.Date(
        string='Booking Date',
        required=True,
        index=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    booking_date_start = fields.Datetime(
        string='Start Date & Time',
        required=True,
        tracking=True,
        index=True,
    )
    booking_date_end = fields.Datetime(
        string='End Date & Time',
        required=True,
        tracking=True,
        index=True,
    )
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        readonly=False,
    )
    duration_display = fields.Char(
        string='Duration',
        compute='_compute_duration_display',
    )
    all_day = fields.Boolean(
        string='All Day',
        default=False,
    )

    # Time slot tracking
    slot_id = fields.Many2one(
        'mh.slot',
        string='Time Slot',
        ondelete='set null',
    )

    # =====================================================================
    # STAFF ASSIGNMENT
    # =====================================================================
    staff_ids = fields.Many2many(
        'mh.staff',
        'mh_booking_staff_rel',
        'booking_id',
        'staff_id',
        string='Assigned Staff',
        domain="[('zone_ids', 'in', zone_id), ('active', '=', True)]",
        tracking=True,
    )
    staff_count = fields.Integer(
        string='Staff Count',
        compute='_compute_staff_count',
        store=True,
    )
    team_lead_id = fields.Many2one(
        'mh.staff',
        string='Team Lead',
        domain="[('id', 'in', staff_ids)]",
        ondelete='set null',
    )
    driver_team_id = fields.Many2one(
        'mh.driver.team',
        string='Driver Team',
        ondelete='set null',
    )

    # =====================================================================
    # CONFLICT DETECTION
    # =====================================================================
    has_conflicts = fields.Boolean(
        string='Has Conflicts',
        compute='_compute_has_conflicts',
        store=True,
    )
    conflict_message = fields.Text(
        string='Conflict Details',
        compute='_compute_conflict_message',
    )
    conflict_line_ids = fields.One2many(
        'mh.booking.conflict',
        'booking_id',
        string='Conflicts',
        readonly=True,
    )

    # In Odoo 18, subscriptions are sale.order records with is_subscription=True
    subscription_id = fields.Many2one(
        'sale.order',
        string='AMC/Subscription Order',
        ondelete='set null',
        index=True,
        tracking=True,
        domain=[('is_subscription', '=', True)],
    )
    is_amc_booking = fields.Boolean(
        string='AMC Booking',
        compute='_compute_is_amc_booking',
        store=True,
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        ondelete='set null',
        index=True,
        tracking=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        ondelete='set null',
    )
    is_one_time_booking = fields.Boolean(
        string='One-Time Booking',
        compute='_compute_is_one_time_booking',
        store=True,
    )

    # Pricing
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        related='partner_id.property_product_pricelist',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='pricelist_id.currency_id',
    )
    list_price = fields.Float(
        string='Unit Price',
        digits='Product Price',
    )
    tax_ids = fields.Many2many(
        'account.tax',
        string='Taxes',
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_price_subtotal',
        store=True,
    )
    price_tax = fields.Float(
        string='Tax',
        compute='_compute_price_tax',
        store=True,
    )
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_price_total',
        store=True,
    )

    # =====================================================================
    # PROJECT & TASK INTEGRATION
    # =====================================================================
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    task_id = fields.Many2one(
        'project.task',
        string='Task',
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    task_ids = fields.One2many(
        'project.task',
        'booking_id',
        string='Tasks',
    )

    # =====================================================================
    # INVOICING
    # =====================================================================
    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_count',
    )
    invoice_ids = fields.Many2many(
        'account.move',
        string='Invoices',
        compute='_compute_invoice_ids',
    )
    invoice_status = fields.Selection([
        ('no', 'No Invoice'),
        ('to_invoice', 'To Invoice'),
        ('invoiced', 'Fully Invoiced'),
    ], string='Invoice Status', compute='_compute_invoice_status', store=True)

    # =====================================================================
    # COMPLETION & FOLLOW-UP
    # =====================================================================
    completion_date = fields.Datetime(
        string='Completion Date',
        readonly=True,
    )
    completion_notes = fields.Text(
        string='Completion Notes',
        copy=False,
    )
    customer_feedback = fields.Text(
        string='Customer Feedback',
        copy=False,
    )
    customer_rating = fields.Integer(
        string='Customer Rating',
        copy=False,
    )

    # Checklist
    checklist_line_ids = fields.One2many(
        'mh.booking.checklist',
        'booking_id',
        string='Completion Checklist',
    )
    checklist_completed = fields.Boolean(
        string='Checklist Completed',
        compute='_compute_checklist_completed',
    )

    # =====================================================================
    # NOTIFICATION TRACKING
    # =====================================================================
    whatsapp_sent = fields.Boolean(
        string='WhatsApp Notification Sent',
        copy=False,
    )
    whatsapp_date = fields.Datetime(
        string='WhatsApp Sent Date',
        copy=False,
    )
    confirmation_email_sent = fields.Datetime(
        string='Confirmation Email Sent',
        copy=False,
    )
    reminder_email_sent = fields.Datetime(
        string='Reminder Email Sent',
        copy=False,
    )

    # =====================================================================
    # GOOGLE CALENDAR SYNC
    # =====================================================================
    calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Calendar Event',
        ondelete='cascade',
        copy=False,
    )
    google_event_id = fields.Char(
        string='Google Event ID',
        copy=False,
    )

    # =====================================================================
    # MARKETING & SOURCE TRACKING
    # =====================================================================
    client_source = fields.Selection([
        ('google', 'Google'),
        ('referral', 'Referral'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('other', 'Other'),
    ], string='Client Source', tracking=True, index=True, default='other',
       help='How the client found or was referred to our services.')

    service_subcategory = fields.Char(
        string='Service Subcategory',
        index=True,
        help='Specific subcategory of the service being booked (e.g., Deep Clean, Spot Treatment).',
    )

    # =====================================================================
    # MATERIAL MANAGEMENT
    # =====================================================================
    material_flag = fields.Boolean(
        string='Materials Required',
        default=False,
        tracking=True,
        help='Enable if this booking requires materials to be sourced or prepared.',
    )
    material_required = fields.Boolean(
        string='Material Required',
        compute='_compute_material_required',
        store=True,
        help='Automatically set based on material_flag.',
    )

    # =====================================================================
    # PAYMENT DETAILS
    # =====================================================================
    payment_method = fields.Selection([
        ('online', 'Online Payment'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
    ], string='Payment Method', tracking=True, index=True,
       help='Preferred payment method for this booking.')
    payment_collected = fields.Boolean(
        string='Payment Collected',
        default=False,
        tracking=True,
        copy=False,
        help='Whether payment has been collected for this booking.',
    )

    # =====================================================================
    # JOB STATUS TRACKING
    # =====================================================================
    job_status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('en_route', 'En Route'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('follow_up_required', 'Follow-up Required'),
    ], string='Job Status', tracking=True, index=True, default='scheduled',
       help='Current operational status of the job.')

    # =====================================================================
    # CONTRACT & COMMERCIAL
    # =====================================================================
    contract_reference = fields.Char(
        string='Contract Reference',
        index=True,
        help='Reference number for any associated contract.',
    )
    is_commercial = fields.Boolean(
        string='Commercial Booking',
        compute='_compute_is_commercial',
        store=True,
        help='True if the booking type is marked as commercial.',
    )
    contract_hours_start = fields.Float(
        string='Contract Start Time',
        digits=(5, 2),
        help='Start time for commercial bookings (e.g., 8.00 for 8:00 AM).',
    )
    contract_hours_end = fields.Float(
        string='Contract End Time',
        digits=(5, 2),
        help='End time for commercial bookings (e.g., 17.00 for 5:00 PM).',
    )

    # =====================================================================
    # SITE & LOCATION
    # =====================================================================
    site_address = fields.Char(
        string='Site Address',
        index=True,
        help='Physical address where the service will be performed (may differ from billing address).',
    )
    gps_coordinates = fields.Char(
        string='GPS Coordinates',
        index=True,
        help='GPS coordinates in format "latitude,longitude" (e.g., "1.3521,103.8198").',
    )
    maps_link = fields.Char(
        string='Maps Link',
        compute='_compute_maps_link',
        store=True,
        help='Direct link to Google Maps for the GPS coordinates.',
    )

    # =====================================================================
    # NOTES & COMMUNICATION
    # =====================================================================
    notes = fields.Text(
        string='Notes',
        translate=True,
        help='Additional notes or special instructions for this booking.',
    )

    # =====================================================================
    # DELIVERY & LOGISTICS
    # =====================================================================
    is_on_time = fields.Boolean(
        string='On Time',
        default=True,
        help='Whether the booking was completed on time.',
    )
    distance_traveled = fields.Float(
        string='Distance Traveled (km)',
        default=0.0,
        digits=(10, 2),
        help='Distance traveled for this booking in kilometers.',
    )

    # =====================================================================
    # SCHEDULING BUFFER & GRACE PERIOD
    # =====================================================================
    buffer_time_minutes = fields.Integer(
        string='Buffer Time (Minutes)',
        default=0,
        help='Additional time buffer before/after the booking for preparation or cleanup.',
    )
    grace_period_minutes = fields.Integer(
        string='Grace Period (Minutes)',
        default=30,
        help='Allowed lateness before marking as late or sending alerts.',
    )

    # =====================================================================
    # NOTIFICATION SETTINGS
    # =====================================================================
    booking_notification_setting = fields.Selection([
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
        ('off', 'Off'),
    ], string='Booking Notification', default='manual', tracking=True,
       help='Controls when and how booking reminders are sent to the customer.')
    completion_notification_setting = fields.Selection([
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
        ('off', 'Off'),
    ], string='Completion Notification', default='manual', tracking=True,
       help='Controls when and how completion confirmations are sent to the customer.')
    notify_operations_manager = fields.Boolean(
        string='Notify Operations Manager',
        default=True,
        tracking=True,
        help='Send notifications to the operations manager for this booking.',
    )
    completion_confirmed = fields.Boolean(
        string='Completion Confirmed',
        default=False,
        copy=False,
        help='Customer has confirmed booking completion.',
    )
    operations_manager_confirmed = fields.Boolean(
        string='Manager Confirmed',
        default=False,
        copy=False,
        help='Operations manager has reviewed and confirmed the booking.',
    )

    # =====================================================================
    # DRIVER ASSIGNMENT
    # =====================================================================
    driver_id = fields.Many2one(
        'res.users',
        string='Assigned Driver',
        domain="[('active', '=', True)]",
        ondelete='set null',
        index=True,
        tracking=True,
        help='Driver assigned to transport staff or materials for this booking.',
    )

    # =====================================================================
    # INTERNAL NOTES
    # =====================================================================
    internal_notes = fields.Text(
        string='Internal Notes',
        copy=False,
    )

    # =====================================================================
    # COMPANY & RESPONSIBILITY
    # =====================================================================
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        tracking=True,
        default=lambda self: self.env.user,
    )
    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        related='user_id.sale_team_id',
        store=True,
    )

    # =====================================================================
    # COMPUTED FIELDS
    # =====================================================================
    @api.depends('booking_date_start', 'booking_date_end')
    def _compute_duration(self):
        """Compute the booking duration in hours."""
        for record in self:
            if record.booking_date_start and record.booking_date_end:
                delta = record.booking_date_end - record.booking_date_start
                record.duration = delta.days * 24 + delta.seconds / 3600
            else:
                record.duration = 0.0

    @api.depends('duration')
    def _compute_duration_display(self):
        """Compute human-readable duration display."""
        for record in self:
            if record.duration:
                hours = int(record.duration)
                minutes = int((record.duration - hours) * 60)
                if hours and minutes:
                    record.duration_display = f'{hours}h {minutes}m'
                elif hours:
                    record.duration_display = f'{hours}h'
                else:
                    record.duration_display = f'{minutes}m'
            else:
                record.duration_display = '-'

    @api.depends('partner_id')
    def _compute_delivery_address(self):
        """Compute the delivery/service address."""
        for record in self:
            if record.partner_id:
                parts = [
                    record.partner_id.street,
                    record.partner_id.street2,
                    record.partner_id.city,
                    record.partner_id.state_id.name,
                    record.partner_id.zip,
                    record.partner_id.country_id.name,
                ]
                record.delivery_address = ', '.join(filter(None, parts))
            else:
                record.delivery_address = ''

    @api.depends('staff_ids')
    def _compute_staff_count(self):
        """Compute the number of assigned staff."""
        for record in self:
            record.staff_count = len(record.staff_ids)

    @api.depends('subscription_id')
    def _compute_is_amc_booking(self):
        """Determine if this is an AMC (Annual Maintenance Contract) booking."""
        for record in self:
            record.is_amc_booking = bool(record.subscription_id)

    @api.depends('sale_order_id')
    def _compute_is_one_time_booking(self):
        """Determine if this is a one-time booking."""
        for record in self:
            record.is_one_time_booking = bool(record.sale_order_id) and not record.subscription_id

    @api.depends('conflict_line_ids')
    def _compute_has_conflicts(self):
        """Check if there are any conflicts."""
        for record in self:
            record.has_conflicts = len(record.conflict_line_ids) > 0

    @api.depends('conflict_line_ids.name')
    def _compute_conflict_message(self):
        """Generate conflict message from conflicts."""
        for record in self:
            if record.conflict_line_ids:
                messages = [c.name for c in record.conflict_line_ids]
                record.conflict_message = '\n'.join(messages)
            else:
                record.conflict_message = ''

    @api.depends('list_price', 'tax_ids', 'duration')
    def _compute_price_subtotal(self):
        """Compute the subtotal price."""
        for record in self:
            record.price_subtotal = record.list_price * record.duration

    @api.depends('price_subtotal', 'tax_ids')
    def _compute_price_tax(self):
        """Compute the tax amount."""
        for record in self:
            taxes = record.tax_ids.compute_all(
                record.price_subtotal,
                record.currency_id,
                1.0,
                product_id=record.booking_type_id.product_id,
                partner=record.partner_id,
            )
            record.price_tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))

    @api.depends('price_subtotal', 'price_tax')
    def _compute_price_total(self):
        """Compute the total price including tax."""
        for record in self:
            record.price_total = record.price_subtotal + record.price_tax

    @api.depends('task_id.invoice_count')
    def _compute_invoice_count(self):
        """Compute the number of related invoices."""
        for record in self:
            if record.task_id:
                record.invoice_count = record.task_id.invoice_count
            else:
                record.invoice_count = 0

    @api.depends('task_id.invoice_ids')
    def _compute_invoice_ids(self):
        """Compute the related invoices."""
        for record in self:
            record.invoice_ids = record.task_id.invoice_ids if record.task_id else False

    @api.depends('invoice_ids', 'state')
    def _compute_invoice_status(self):
        """Compute the invoice status."""
        for record in self:
            if not record.invoice_ids:
                record.invoice_status = 'no'
            elif all(inv.state == 'posted' for inv in record.invoice_ids):
                record.invoice_status = 'invoiced'
            else:
                record.invoice_status = 'to_invoice'

    @api.depends('checklist_line_ids.is_done')
    def _compute_checklist_completed(self):
        """Check if all checklist items are completed."""
        for record in self:
            if not record.checklist_line_ids:
                record.checklist_completed = True
            else:
                record.checklist_completed = all(
                    line.is_done for line in record.checklist_line_ids
                )

    @api.depends('material_flag')
    def _compute_material_required(self):
        """Compute material_required based on material_flag."""
        for record in self:
            record.material_required = record.material_flag

    @api.depends('booking_type_id.is_commercial')
    def _compute_is_commercial(self):
        """Determine if booking is commercial based on booking type."""
        for record in self:
            if record.booking_type_id:
                record.is_commercial = record.booking_type_id.is_commercial
            else:
                record.is_commercial = False

    @api.depends('gps_coordinates')
    def _compute_maps_link(self):
        """Generate Google Maps link from GPS coordinates."""
        for record in self:
            if record.gps_coordinates:
                # Clean and validate GPS coordinates
                coords = record.gps_coordinates.strip()
                # Validate basic format (should contain comma for lat,long)
                if re.match(r'^-?\d+\.?\d*,\s*-?\d+\.?\d*$', coords):
                    record.maps_link = f'https://maps.google.com/?q={coords}'
                else:
                    # If just text, URL encode it
                    encoded = coords.replace(' ', '+')
                    record.maps_link = f'https://maps.google.com/?q={encoded}'
            else:
                record.maps_link = False

    # =====================================================================
    # CONSTRAINTS
    # =====================================================================
    @api.constrains('booking_date_start', 'booking_date_end')
    def _check_dates(self):
        """Ensure end date is after start date."""
        for record in self:
            if record.booking_date_end and record.booking_date_start:
                if record.booking_date_end <= record.booking_date_start:
                    raise ValidationError(
                        _('End date and time must be after start date and time.')
                    )

    @api.constrains('grace_period_minutes', 'buffer_time_minutes')
    def _check_time_values(self):
        """Ensure grace period and buffer time are non-negative."""
        for record in self:
            if record.grace_period_minutes < 0:
                raise ValidationError(
                    _('Grace period cannot be negative.')
                )
            if record.buffer_time_minutes < 0:
                raise ValidationError(
                    _('Buffer time cannot be negative.')
                )

    @api.constrains('contract_hours_start', 'contract_hours_end')
    def _check_contract_hours(self):
        """Ensure contract hours are valid."""
        for record in self:
            if record.contract_hours_start or record.contract_hours_end:
                if record.contract_hours_start and (record.contract_hours_start < 0 or record.contract_hours_start >= 24):
                    raise ValidationError(
                        _('Contract start time must be between 0 and 24.')
                    )
                if record.contract_hours_end and (record.contract_hours_end < 0 or record.contract_hours_end >= 24):
                    raise ValidationError(
                        _('Contract end time must be between 0 and 24.')
                    )
                if record.contract_hours_start and record.contract_hours_end:
                    if record.contract_hours_start >= record.contract_hours_end:
                        raise ValidationError(
                            _('Contract start time must be before end time.')
                        )

    @api.constrains('staff_ids', 'booking_date_start', 'booking_date_end', 'zone_id', 'driver_id')
    def _check_staff_conflicts(self):
        """Check for staff and driver scheduling conflicts."""
        for record in self:
            if not record.booking_date_start or not record.booking_date_end:
                continue

            # Remove existing conflicts
            record.conflict_line_ids.unlink()

            for staff in record.staff_ids:
                # Check time conflicts
                time_conflicts = record._search_time_conflicts(staff)
                for conflict in time_conflicts:
                    self.env['mh.booking.conflict'].create({
                        'booking_id': record.id,
                        'staff_id': staff.id,
                        'conflict_booking_id': conflict.id,
                        'conflict_type': 'time',
                        'name': f'Time conflict with {conflict.name} ({conflict.booking_date_start} - {conflict.booking_date_end})',
                    })

                # Check zone conflicts (staff assigned to multiple zones at same time)
                zone_conflicts = record._search_zone_conflicts(staff)
                for conflict in zone_conflicts:
                    self.env['mh.booking.conflict'].create({
                        'booking_id': record.id,
                        'staff_id': staff.id,
                        'conflict_booking_id': conflict.id,
                        'conflict_type': 'zone',
                        'name': f'Zone conflict: {staff.name} already assigned to zone {conflict.zone_id.name} at this time',
                    })

            # Check driver conflicts if driver is assigned
            if record.driver_id:
                driver_conflicts = record._search_driver_conflicts(record.driver_id)
                for conflict in driver_conflicts:
                    self.env['mh.booking.conflict'].create({
                        'booking_id': record.id,
                        'conflict_booking_id': conflict.id,
                        'conflict_type': 'time',
                        'name': f'Driver conflict: {record.driver_id.name} already assigned to booking {conflict.name} at this time',
                    })

    def _search_time_conflicts(self, staff):
        """Search for time-based conflicts with staff."""
        return self.search([
            ('id', '!=', self.id or False),
            ('staff_ids', 'in', staff.id),
            ('state', 'not in', ['cancelled', 'completed', 'no_show']),
            ('booking_date_start', '<', self.booking_date_end),
            ('booking_date_end', '>', self.booking_date_start),
        ])

    def _search_zone_conflicts(self, staff):
        """
        Search for zone-based conflicts with staff at the same time.

        Checks for bookings in different zones that overlap in time with the staff
        member already assigned. This helps prevent staff being assigned to multiple
        zones simultaneously.
        """
        return self.search([
            ('id', '!=', self.id or False),
            ('zone_id', '!=', self.zone_id.id),
            ('staff_ids', 'in', staff.id),
            ('state', 'not in', ['cancelled', 'completed', 'no_show']),
            ('booking_date_start', '<', self.booking_date_end),
            ('booking_date_end', '>', self.booking_date_start),
        ])

    def _search_driver_conflicts(self, driver):
        """
        Search for driver scheduling conflicts.

        Args:
            driver: res.users record for the driver

        Returns:
            mh.booking records that conflict with driver's schedule
        """
        if not driver:
            return self.browse()

        return self.search([
            ('id', '!=', self.id or False),
            ('driver_id', '=', driver.id),
            ('state', 'not in', ['cancelled', 'completed', 'no_show']),
            ('booking_date_start', '<', self.booking_date_end),
            ('booking_date_end', '>', self.booking_date_start),
        ])

    # =====================================================================
    # LIFECYCLE METHODS
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mh.booking') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        """Override write to handle state transitions and job status updates."""
        result = super().write(vals)

        # Handle state-specific logic
        if 'state' in vals:
            for record in self:
                # Update job_status based on state transitions
                state_to_job_status = {
                    'draft': 'scheduled',
                    'confirmed': 'scheduled',
                    'in_progress': 'in_progress',
                    'completed': 'completed',
                }
                if record.state in state_to_job_status:
                    record.job_status = state_to_job_status[record.state]

                if record.state == 'confirmed':
                    record._action_confirm()
                elif record.state == 'completed':
                    record._action_complete()

        return result

    def _action_confirm(self):
        """Actions to perform when booking is confirmed."""
        self.ensure_one()
        if not self.staff_ids:
            raise UserError(_('Please assign staff before confirming the booking.'))
        if self.has_conflicts:
            raise UserError(_('Cannot confirm booking with unresolved conflicts.'))

        # Create calendar event
        self._create_calendar_event()

        # Send confirmation notification
        self._send_confirmation_notification()

        return True

    def _action_complete(self):
        """Actions to perform when booking is completed."""
        self.ensure_one()
        self.completion_date = fields.Datetime.now()

        # Update task if exists
        if self.task_id:
            self.task_id.write({
                'stage_id': self.env.ref('industry_fsm.project_task_type_done').id,
            })

        return True

    def _create_calendar_event(self):
        """Create a calendar event for the booking."""
        self.ensure_one()
        if self.calendar_event_id:
            return self.calendar_event_id

        event_vals = {
            'name': f'{self.name} - {self.booking_type_id.name}',
            'start': self.booking_date_start,
            'stop': self.booking_date_end,
            'allday': self.all_day,
            'partner_ids': [
                (4, self.partner_id.id),
                (4, self.user_id.partner_id.id),
            ],
            'user_id': self.user_id.id,
            'description': self.description,
            'mh_booking_id': self.id,
        }

        return self.env['calendar.event'].create(event_vals)

    def _send_confirmation_notification(self):
        """Send confirmation notification to customer."""
        self.ensure_one()
        template = self.env.ref('mh_booking_calendar.booking_confirmation_email', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
            self.confirmation_email_sent = fields.Datetime.now()

    def action_confirm(self):
        """Wizard action to confirm booking."""
        for record in self:
            record._action_confirm()
            record.state = 'confirmed'
        return True

    def action_start(self):
        """Action to start the booking."""
        self.write({'state': 'in_progress'})
        return True

    def action_complete(self):
        """Action to complete the booking - opens wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Complete Booking'),
            'res_model': 'mh.booking.completion.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id},
        }

    def action_cancel(self):
        """Action to cancel the booking."""
        for record in self:
            # Unlink calendar event
            if record.calendar_event_id:
                record.calendar_event_id.unlink()

            # Send cancellation notification
            record._send_cancellation_notification()

            record.state = 'cancelled'
        return True

    def action_mark_no_show(self):
        """Action to mark booking as no-show."""
        self.write({'state': 'no_show'})
        return True

    # =====================================================================
    # JOB STATUS ACTIONS
    # =====================================================================
    def action_set_en_route(self):
        """Set job status to en route."""
        self.ensure_one()
        if self.state not in ('confirmed', 'in_progress'):
            raise UserError(_('Booking must be confirmed before marking as en route.'))
        self.write({'job_status': 'en_route'})
        return True

    def action_set_in_progress_job(self):
        """Set job status to in progress."""
        self.ensure_one()
        self.write({'job_status': 'in_progress'})
        if self.state == 'confirmed':
            self.write({'state': 'in_progress'})
        return True

    def action_set_follow_up_required(self):
        """Set job status to follow-up required."""
        self.ensure_one()
        self.write({'job_status': 'follow_up_required'})
        return True

    def action_confirm_completion(self):
        """Mark completion as confirmed by customer."""
        self.ensure_one()
        self.completion_confirmed = True
        # Auto-send notification if setting is automatic
        if self.completion_notification_setting == 'auto':
            self._send_completion_notification()
        return True

    def action_manager_confirm(self):
        """Mark as confirmed by operations manager."""
        self.ensure_one()
        if not self.env.user.has_group('mh_booking_calendar.group_operations_manager'):
            raise UserError(_('Only operations managers can confirm bookings.'))
        self.operations_manager_confirmed = True
        return True

    def _send_cancellation_notification(self):
        """Send cancellation notification to customer."""
        self.ensure_one()
        template = self.env.ref('mh_booking_calendar.booking_cancellation_email', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def _send_completion_notification(self):
        """Send completion notification to customer."""
        self.ensure_one()
        if not self.completion_confirmed:
            _logger.warning(
                'Completion notification skipped for booking %s: not confirmed by customer',
                self.name
            )
            return False

        template = self.env.ref('mh_booking_calendar.booking_completion_email', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
            _logger.info('Completion notification sent for booking %s', self.name)
            return True
        return False

    def _notify_operations_manager(self):
        """Send notification to operations manager."""
        self.ensure_one()
        if not self.notify_operations_manager:
            return False

        # Find operations manager(s)
        manager_group = self.env.ref('mh_booking_calendar.group_operations_manager', raise_if_not_found=False)
        if not manager_group:
            _logger.warning('Operations manager group not found')
            return False

        # Get users in the manager group
        manager_users = manager_group.users
        if not manager_users:
            _logger.warning('No users in operations manager group')
            return False

        # Create activity for each manager
        for user in manager_users:
            self.activity_schedule(
                'mail.mail_activity_data_notification',
                user_id=user.id,
                note=_('Booking %s requires manager review. Customer: %s, Date: %s') % (
                    self.name,
                    self.partner_id.name,
                    self.booking_date_start,
                ),
            )
        return True

    # =====================================================================
    # WHATSAPP NOTIFICATION HANDLING
    # =====================================================================
    def _prepare_whatsapp_message(self, message_type='confirmation'):
        """
        Prepare WhatsApp message content based on message type.

        Args:
            message_type: Type of message - 'confirmation', 'reminder', 'completion', 'cancellation'

        Returns:
            str: Formatted message content
        """
        self.ensure_one()
        lang_code = self.env.lang or 'en_US'

        base_data = {
            'booking_ref': self.name,
            'customer_name': self.partner_id.name or '',
            'service_type': self.booking_type_id.name or '',
            'date': fields.Date.format(self.booking_date),
            'time': fields.Datetime.format(self.booking_date_start),
            'address': self.site_address or self.delivery_address or '',
            'contact_phone': self.partner_phone or self.partner_mobile or '',
        }

        templates = {
            'confirmation': _(
                "Hi {customer_name},\n\n"
                "Your booking *{booking_ref}* for *{service_type}* has been confirmed.\n\n"
                "📅 Date: {date}\n"
                "🕐 Time: {time}\n"
                "📍 Address: {address}\n\n"
                "Thank you for choosing M&H Technical Services!"
            ),
            'reminder': _(
                "Hi {customer_name},\n\n"
                "Reminder: Your booking *{booking_ref}* for *{service_type}* is tomorrow.\n\n"
                "📅 Date: {date}\n"
                "🕐 Time: {time}\n"
                "📍 Address: {address}\n\n"
                "We look forward to serving you!"
            ),
            'completion': _(
                "Hi {customer_name},\n\n"
                "✅ Your booking *{booking_ref}* for *{service_type}* has been completed.\n\n"
                "Thank you for your business!\n\n"
                "Please share your feedback: [feedback link]"
            ),
            'cancellation': _(
                "Hi {customer_name},\n\n"
                "Your booking *{booking_ref}* for *{service_type}* has been cancelled.\n\n"
                "If you have any questions, please contact us."
            ),
            'en_route': _(
                "Hi {customer_name},\n\n"
                "🚗 Our team is on the way!\n\n"
                "Booking: *{booking_ref}*\n"
                "Service: *{service_type}*\n"
                "📍 Address: {address}\n\n"
                "We'll arrive shortly."
            ),
        }

        template = templates.get(message_type, templates['confirmation'])
        return template.format(**base_data)

    def action_send_whatsapp(self, message_type='confirmation'):
        """
        Send WhatsApp notification for the booking.

        Args:
            message_type: Type of message to send ('confirmation', 'reminder', 'completion', 'cancellation')

        Returns:
            bool: True if message was sent successfully
        """
        self.ensure_one()

        # Check if notifications are enabled for this booking
        if message_type == 'completion' and self.completion_notification_setting == 'off':
            _logger.info('Completion WhatsApp disabled for booking %s', self.name)
            return False

        # Check operations manager confirmation if required
        if message_type == 'completion' and self.notify_operations_manager and not self.operations_manager_confirmed:
            raise UserError(_('Operations manager must confirm before sending completion notification.'))

        message = self._prepare_whatsapp_message(message_type)

        # Log the message for audit trail
        _logger.info(
            'WhatsApp message prepared for booking %s (type: %s):\n%s',
            self.name,
            message_type,
            message
        )

        # Integration point for WhatsApp API
        # This would typically call an external API service
        # Example integration point - replace with actual WhatsApp API call
        whatsapp_api_endpoint = self.env['ir.config_parameter'].sudo().get_param(
            'mh_booking_calendar.whatsapp_api_endpoint'
        )

        if whatsapp_api_endpoint:
            try:
                # Prepare phone number (ensure format is correct)
                phone = self.partner_mobile or self.partner_phone
                if not phone:
                    raise UserError(_('No phone number found for this customer.'))

                # Format phone for WhatsApp (remove non-digits, add country code if needed)
                phone = re.sub(r'[^\d+]', '', phone)
                if not phone.startswith('+'):
                    phone = '+' + phone

                # Here you would make the actual API call
                # Example: requests.post(whatsapp_api_endpoint, json={...})
                _logger.info('WhatsApp API call would be made to %s for booking %s', whatsapp_api_endpoint, self.name)

            except Exception as e:
                _logger.error('Failed to send WhatsApp message for booking %s: %s', self.name, str(e))
                raise UserError(_('Failed to send WhatsApp message: %s') % str(e))

        # Mark as sent
        self.write({
            'whatsapp_sent': True,
            'whatsapp_date': fields.Datetime.now(),
        })

        # Post message in chatter
        self.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return True

    def action_send_reminder_whatsapp(self):
        """Send booking reminder via WhatsApp."""
        self.ensure_one()
        if self.booking_notification_setting == 'off':
            raise UserError(_('Notifications are disabled for this booking.'))
        return self.action_send_whatsapp(message_type='reminder')

    def action_send_en_route_whatsapp(self):
        """Send en route notification via WhatsApp."""
        self.ensure_one()
        return self.action_send_whatsapp(message_type='en_route')

    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    def get_available_staff(self):
        """Get list of available staff for this booking's zone and time."""
        self.ensure_one()
        staff_pool = self.env['mh.staff']

        # Get all staff assigned to this zone
        zone_staff = staff_pool.search([
            ('zone_ids', 'in', self.zone_id.id),
            ('active', '=', True),
        ])

        # Filter out those with conflicts
        available = staff_pool
        for staff in zone_staff:
            if not self._search_time_conflicts(staff):
                available |= staff

        return available

    def get_checklist_template(self):
        """Get checklist items based on booking type."""
        self.ensure_one()
        if not self.booking_type_id:
            return []

        # Create checklist based on booking type properties
        checklist_items = []
        for prop in self.booking_type_id.property_ids:
            checklist_items.append({
                'name': prop.name,
                'booking_id': self.id,
            })

        return checklist_items

    @api.onchange('booking_type_id')
    def _onchange_booking_type_id(self):
        """Update default values when booking type changes."""
        if self.booking_type_id:
            self.list_price = self.booking_type_id.price
            self.duration = self.booking_type_id.duration
            self.tax_ids = self.booking_type_id.product_id.taxes_id

            # Create checklist items
            checklist_vals = []
            for prop in self.booking_type_id.property_ids:
                checklist_vals.append((0, 0, {
                    'name': prop.name,
                }))
            if checklist_vals:
                self.checklist_line_ids = checklist_vals

    @api.onchange('zone_id')
    def _onchange_zone_id(self):
        """Clear staff when zone changes."""
        if self.zone_id:
            # Return domain for staff that can work in this zone
            return {
                'domain': {
                    'staff_ids': [
                        ('zone_ids', 'in', self.zone_id.id),
                        ('active', '=', True),
                    ]
                }
            }
        else:
            return {
                'domain': {
                    'staff_ids': [('active', '=', True)]
                }
            }

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Update partner-related fields when customer changes."""
        if self.partner_id:
            # Update zone if customer has a default zone
            if self.partner_id.partner_zone_id:
                self.zone_id = self.partner_id.partner_zone_id

            # Auto-fill site address from partner if not set
            if not self.site_address and hasattr(self.partner_id, 'street'):
                address_parts = [
                    self.partner_id.street,
                    self.partner_id.street2,
                    self.partner_id.city,
                ]
                self.site_address = ', '.join(filter(None, address_parts))

            # Check for active subscriptions (sale.order with is_subscription=True in Odoo 18)
            subscriptions = self.env['sale.order'].search([
                ('partner_id', '=', self.partner_id.id),
                ('is_subscription', '=', True),
                ('subscription_state', 'in', ['3_progress', '4_paused']),
            ])
            if subscriptions:
                # Could show a wizard to select subscription
                pass

    @api.onchange('driver_id')
    def _onchange_driver_id(self):
        """Check for driver conflicts when driver changes."""
        if self.driver_id and self.booking_date_start and self.booking_date_end:
            conflicts = self._search_driver_conflicts(self.driver_id)
            if conflicts:
                conflict_names = ', '.join([c.name for c in conflicts])
                return {
                    'warning': {
                        'title': _('Driver Conflict'),
                        'message': _(
                            'Driver %s is already assigned to booking(s): %s during this time slot.'
                        ) % (self.driver_id.name, conflict_names),
                    }
                }

    @api.onchange('booking_date_start', 'booking_date_end')
    def _onchange_dates_check_conflicts(self):
        """Check for conflicts when dates change."""
        if self.driver_id and self.booking_date_start and self.booking_date_end:
            conflicts = self._search_driver_conflicts(self.driver_id)
            if conflicts:
                conflict_names = ', '.join([c.name for c in conflicts])
                return {
                    'warning': {
                        'title': _('Scheduling Conflict'),
                        'message': _(
                            'Driver %s has conflicts with booking(s): %s'
                        ) % (self.driver_id.name, conflict_names),
                    }
                }

    @api.onchange('contract_hours_start', 'contract_hours_end')
    def _onchange_contract_hours(self):
        """Validate contract hours."""
        if self.contract_hours_start and self.contract_hours_end:
            if self.contract_hours_start >= 24 or self.contract_hours_end >= 24:
                return {
                    'warning': {
                        'title': _('Invalid Hours'),
                        'message': _('Contract hours must be between 0 and 24.'),
                    }
                }
            if self.contract_hours_start >= self.contract_hours_end:
                return {
                    'warning': {
                        'title': _('Invalid Time Range'),
                        'message': _('Contract start time must be before end time.'),
                    }
                }

    @api.onchange('gps_coordinates')
    def _onchange_gps_coordinates(self):
        """Validate GPS coordinates format."""
        if self.gps_coordinates:
            coords = self.gps_coordinates.strip()
            if not re.match(r'^-?\d+\.?\d*,\s*-?\d+\.?\d*$', coords):
                return {
                    'warning': {
                        'title': _('Invalid GPS Format'),
                        'message': _(
                            'GPS coordinates should be in format "latitude,longitude" '
                            'e.g., "1.3521,103.8198"'
                        ),
                    }
                }


class MHBookingConflict(models.Model):
    """
    Tracks conflicts between bookings for the same staff.
    """
    _name = 'mh.booking.conflict'
    _description = 'MH Booking Conflict'

    booking_id = fields.Many2one(
        'mh.booking',
        string='Booking',
        required=True,
        ondelete='cascade',
    )
    staff_id = fields.Many2one(
        'mh.staff',
        string='Staff Member',
        required=True,
        ondelete='cascade',
    )
    conflict_booking_id = fields.Many2one(
        'mh.booking',
        string='Conflicting Booking',
        required=True,
        ondelete='cascade',
    )
    conflict_type = fields.Selection([
        ('time', 'Time Conflict'),
        ('zone', 'Zone Conflict'),
        ('capacity', 'Capacity Conflict'),
    ], string='Conflict Type', required=True)
    name = fields.Char(
        string='Conflict Description',
        required=True,
    )
    resolved = fields.Boolean(
        string='Resolved',
        default=False,
    )
    resolution_notes = fields.Text(
        string='Resolution Notes',
    )


class MHBookingPropertyValue(models.Model):
    """
    Stores dynamic property values for bookings.
    """
    _name = 'mh.booking.property.value'
    _description = 'MH Booking Property Value'

    booking_id = fields.Many2one(
        'mh.booking',
        string='Booking',
        required=True,
        ondelete='cascade',
    )
    property_id = fields.Many2one(
        'mh.booking.type.property',
        string='Property',
        required=True,
        ondelete='cascade',
    )
    value_char = fields.Char(
        string='Text Value',
    )
    value_integer = fields.Integer(
        string='Integer Value',
    )
    value_float = fields.Float(
        string='Float Value',
    )
    value_boolean = fields.Boolean(
        string='Boolean Value',
    )
    value_text = fields.Text(
        string='Multi-line Value',
    )

    @api.constrains('property_id', 'booking_id')
    def _check_unique_property(self):
        """Ensure one value per property per booking."""
        for record in self:
            existing = self.search([
                ('id', '!=', record.id),
                ('booking_id', '=', record.booking_id.id),
                ('property_id', '=', record.property_id.id),
            ])
            if existing:
                raise ValidationError(
                    _('Property "%s" already has a value for this booking.')
                    % record.property_id.name
                )


class MHBookingChecklist(models.Model):
    """
    Completion checklist items for bookings.
    """
    _name = 'mh.booking.checklist'
    _description = 'MH Booking Checklist'

    booking_id = fields.Many2one(
        'mh.booking',
        string='Booking',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(
        string='Task',
        required=True,
        translate=True,
    )
    is_done = fields.Boolean(
        string='Done',
        default=False,
    )
    notes = fields.Text(
        string='Notes',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    staff_id = fields.Many2one(
        'mh.staff',
        string='Completed By',
        ondelete='set null',
    )
    completed_date = fields.Datetime(
        string='Completed Date',
    )

    @api.onchange('is_done')
    def _onchange_is_done(self):
        """Record completion details when checked."""
        if self.is_done and not self.completed_date:
            self.completed_date = fields.Datetime.now()
            self.staff_id = self.env['mh.staff'].search([
                ('user_id', '=', self.env.uid)
            ], limit=1)
        elif not self.is_done:
            self.completed_date = False
            self.staff_id = False
