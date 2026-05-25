# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MHResource(models.Model):
    """
    Resources that can be booked for service appointments.
    Examples: Equipment, Machines, Special Tools
    """
    _name = 'mh.resource'
    _description = 'MH Resource'
    _order = 'name'

    name = fields.Char(
        string='Resource Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Resource Code',
        index=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this resource will not be available for booking.',
    )
    resource_type = fields.Selection([
        ('equipment', 'Equipment'),
        ('machine', 'Machine'),
        ('tool', 'Tool'),
        ('vehicle', 'Vehicle'),
        ('room', 'Room'),
        ('other', 'Other'),
    ], string='Resource Type', default='equipment')

    # Capacity
    quantity = fields.Integer(
        string='Available Quantity',
        default=1,
        help='Total number of this resource available.',
    )
    quantity_available = fields.Integer(
        string='Available Now',
        compute='_compute_quantity_available',
        store=True,
    )

    # Time constraints
    duration_min = fields.Float(
        string='Min Duration (Hours)',
        default=1.0,
        digits=(5, 2),
        help='Minimum booking duration.',
    )
    duration_max = fields.Float(
        string='Max Duration (Hours)',
        default=8.0,
        digits=(5, 2),
        help='Maximum booking duration.',
    )
    buffer_time = fields.Float(
        string='Buffer Time (Minutes)',
        default=15,
        help='Required time gap between bookings.',
    )

    # Allocation method
    allocation_type = fields.Selection([
        ('fixed', 'Fixed Quantity'),
        ('time', 'Time-based'),
        ('capacity', 'Capacity-based'),
    ], string='Allocation Type', default='fixed')

    # Capacity settings (for capacity-based allocation)
    capacity_per_hour = fields.Integer(
        string='Capacity Per Hour',
        default=1,
    )

    # Booking lines
    booking_line_ids = fields.One2many(
        'mh.resource.booking.line',
        'resource_id',
        string='Bookings',
    )

    # Product link (for invoicing)
    product_id = fields.Many2one(
        'product.product',
        string='Related Product',
        domain=[('type', '=', 'service')],
        ondelete='restrict',
    )
    cost_per_hour = fields.Float(
        string='Cost Per Hour',
        digits='Product Price',
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    # Notes
    description = fields.Text(
        string='Description',
        translate=True,
    )
    notes = fields.Text(
        string='Internal Notes',
    )

    @api.depends('quantity', 'booking_line_ids.state')
    def _compute_quantity_available(self):
        """Compute available quantity based on active bookings."""
        for record in self:
            # Count booked resources
            booked = self.env['mh.resource.booking.line'].search_count([
                ('resource_id', '=', record.id),
                ('state', 'in', ['confirmed', 'in_progress']),
            ])
            record.quantity_available = max(0, record.quantity - booked)

    def is_available(self, datetime_start, datetime_end, quantity_needed=1):
        """
        Check if resource is available for the given time period.

        Args:
            datetime_start: Start datetime
            datetime_end: End datetime
            quantity_needed: Number of units needed

        Returns:
            tuple: (available: bool, message: str)
        """
        self.ensure_one()

        if quantity_needed > self.quantity:
            return False, f'Requested quantity ({quantity_needed}) exceeds total ({self.quantity})'

        # Get existing bookings for this time period
        bookings = self.env['mh.resource.booking.line'].search([
            ('resource_id', '=', self.id),
            ('state', 'in', ['confirmed', 'in_progress']),
            ('datetime_start', '<', datetime_end),
            ('datetime_end', '>', datetime_start),
        ])

        # Calculate booked quantity
        booked_qty = sum(bookings.mapped('quantity'))
        available_qty = self.quantity - booked_qty

        if available_qty < quantity_needed:
            return False, f'Only {available_qty} available, {quantity_needed} needed'

        return True, 'Available'

    def get_availability_slots(self, date, duration=1.0, quantity_needed=1):
        """
        Get available time slots for a date.

        Args:
            date: Date to check
            duration: Required duration in hours
            quantity_needed: Number of units needed

        Returns:
            list: Available slots with start/end times
        """
        self.ensure_one()
        from datetime import datetime, timedelta

        slots = []
        # Assuming 8 AM to 6 PM working hours
        for hour in range(8, 18):
            slot_start = datetime.combine(date, datetime.min.time().replace(hour=hour))
            slot_end = slot_start + timedelta(hours=duration)

            available, _ = self.is_available(slot_start, slot_end, quantity_needed)
            if available:
                slots.append({
                    'start': slot_start,
                    'end': slot_end,
                    'hour': hour,
                })

        return slots


class MHResourceBookingLine(models.Model):
    """
    Individual resource booking lines linking resources to bookings.
    """
    _name = 'mh.resource.booking.line'
    _description = 'MH Resource Booking Line'
    _order = 'datetime_start'

    resource_id = fields.Many2one(
        'mh.resource',
        string='Resource',
        required=True,
        index=True,
        ondelete='cascade',
    )
    booking_id = fields.Many2one(
        'mh.booking',
        string='Booking',
        required=True,
        index=True,
        ondelete='cascade',
    )
    datetime_start = fields.Datetime(
        string='Start Date & Time',
        required=True,
        index=True,
    )
    datetime_end = fields.Datetime(
        string='End Date & Time',
        required=True,
    )
    quantity = fields.Integer(
        string='Quantity',
        default=1,
        help='Number of resource units booked.',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', index=True)

    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
    )

    @api.depends('datetime_start', 'datetime_end')
    def _compute_duration(self):
        """Compute the booking duration in hours."""
        for record in self:
            if record.datetime_start and record.datetime_end:
                delta = record.datetime_end - record.datetime_start
                record.duration = delta.days * 24 + delta.seconds / 3600
            else:
                record.duration = 0.0

    @api.constrains('datetime_start', 'datetime_end')
    def _check_dates(self):
        """Ensure end date is after start date."""
        for record in self:
            if record.datetime_end and record.datetime_start:
                if record.datetime_end <= record.datetime_start:
                    raise ValidationError(
                        _('End datetime must be after start datetime.')
                    )

    @api.constrains('quantity')
    def _check_quantity(self):
        """Ensure quantity is positive and within limits."""
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero.'))
            if record.quantity > record.resource_id.quantity:
                raise ValidationError(
                    _('Requested quantity (%s) exceeds available (%s).')
                    % (record.quantity, record.resource_id.quantity)
                )

    def action_confirm(self):
        """Confirm the resource booking."""
        for record in self:
            # Check availability again before confirming
            available, msg = record.resource_id.is_available(
                record.datetime_start,
                record.datetime_end,
                record.quantity
            )
            if not available:
                raise UserError(
                    _('Cannot confirm: %s') % msg
                )
            record.state = 'confirmed'
        return True

    def action_complete(self):
        """Mark resource booking as completed."""
        self.write({'state': 'completed'})
        return True

    def action_cancel(self):
        """Cancel the resource booking."""
        self.write({'state': 'cancelled'})
        return True
