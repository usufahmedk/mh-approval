# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MHSlot(models.Model):
    """
    Time slots for booking appointments.
    Defines available time windows within a day for scheduling.
    """
    _name = 'mh.slot'
    _description = 'MH Time Slot'
    _order = 'sequence, time_start'

    name = fields.Char(
        string='Slot Name',
        required=True,
        index=True,
        translate=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of the slot in the day.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this slot will not be available for booking.',
    )

    # Time definitions
    time_start = fields.Float(
        string='Start Time',
        required=True,
        widget='float_time',
        help='Start time in hours (e.g., 9.5 = 9:30).',
    )
    time_end = fields.Float(
        string='End Time',
        required=True,
        widget='float_time',
        help='End time in hours (e.g., 11.5 = 11:30).',
    )
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        help='Slot duration in hours.',
    )

    # Slot type
    slot_type = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('evening', 'Evening'),
        ('full_day', 'Full Day'),
    ], string='Slot Type', default='morning')

    # Availability settings
    is_default = fields.Boolean(
        string='Default Slot',
        default=False,
        help='If checked, this slot will be preselected for new bookings.',
    )
    max_bookings = fields.Integer(
        string='Max Bookings per Slot',
        default=1,
        help='Maximum number of concurrent bookings allowed for this slot.',
    )
    allow_overflow = fields.Boolean(
        string='Allow Overflow',
        default=False,
        help='Allow more bookings than max_bookings if needed.',
    )

    # Zone-specific slots
    zone_id = fields.Many2one(
        'mh.zone',
        string='Zone',
        index=True,
        ondelete='cascade',
        help='If set, this slot is specific to a zone. Leave empty for global.',
    )

    # Booking type restrictions
    booking_type_ids = fields.Many2many(
        'mh.booking.type',
        'mh_slot_booking_type_rel',
        'slot_id',
        'booking_type_id',
        string='Allowed Booking Types',
        help='If set, only these booking types can use this slot. Leave empty for all.',
    )

    # Color for calendar display
    color = fields.Integer(
        string='Color',
        default=0,
    )

    # Description
    description = fields.Text(
        string='Description',
        translate=True,
        help='Additional information about this slot.',
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    @api.depends('time_start', 'time_end')
    def _compute_duration(self):
        """Compute slot duration in hours."""
        for record in self:
            if record.time_end and record.time_start:
                record.duration = record.time_end - record.time_start
            else:
                record.duration = 0.0

    @api.constrains('time_start', 'time_end')
    def _check_times(self):
        """Ensure end time is after start time."""
        for record in self:
            if record.time_end <= record.time_start:
                raise ValidationError(
                    _('End time must be after start time.')
                )

    @api.constrains('is_default')
    def _check_unique_default(self):
        """Ensure only one default slot per zone."""
        for record in self:
            if record.is_default:
                domain = [
                    ('id', '!=', record.id),
                    ('is_default', '=', True),
                ]
                if record.zone_id:
                    domain.append(('zone_id', '=', record.zone_id.id))
                else:
                    domain.append(('zone_id', '=', False))
                if self.search(domain):
                    raise ValidationError(
                        _('Only one default slot is allowed per zone.')
                    )

    def get_display_time(self):
        """Return formatted time string."""
        self.ensure_one()
        hours = int(self.time_start)
        minutes = int((self.time_start % 1) * 60)
        start_str = f'{hours:02d}:{minutes:02d}'

        hours = int(self.time_end)
        minutes = int((self.time_end % 1) * 60)
        end_str = f'{hours:02d}:{minutes:02d}'

        return f'{start_str} - {end_str}'


class MHSlotAvailability(models.Model):
    """
    Defines slot availability on specific dates.
    Used to block out dates or modify slot availability.
    """
    _name = 'mh.slot.availability'
    _description = 'MH Slot Availability'
    _order = 'date_from desc'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )

    # Date range
    date_from = fields.Date(
        string='From Date',
        required=True,
        index=True,
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        index=True,
    )

    # Availability type
    availability_type = fields.Selection([
        ('available', 'Available'),
        ('blocked', 'Blocked'),
        ('limited', 'Limited'),
    ], string='Type', default='available', required=True)

    # For limited availability
    slot_ids = fields.Many2many(
        'mh.slot',
        'mh_slot_availability_slot_rel',
        'availability_id',
        'slot_id',
        string='Affected Slots',
        help='Slots affected by this availability rule.',
    )
    max_bookings_per_slot = fields.Integer(
        string='Max Bookings per Slot',
        default=1,
    )

    # Zone specificity
    zone_id = fields.Many2one(
        'mh.zone',
        string='Zone',
        index=True,
        ondelete='cascade',
    )

    # Recurrence
    is_recurring = fields.Boolean(
        string='Recurring',
        default=False,
    )
    recurring_type = fields.Selection([
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Recurring Type')
    recurring_day_ids = fields.Many2many(
        'resource.calendar.attendance',
        string='Recurring Days',
    )

    # Reason
    reason = fields.Char(
        string='Reason',
        translate=True,
        help='Reason for unavailability (e.g., Holiday, Maintenance).',
    )
    notes = fields.Text(
        string='Notes',
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Ensure date range is valid."""
        for record in self:
            if record.date_to < record.date_from:
                raise ValidationError(
                    _('End date must be after start date.')
                )

    @api.onchange('availability_type')
    def _onchange_availability_type(self):
        """Update fields based on availability type."""
        if self.availability_type == 'available':
            self.max_bookings_per_slot = 0
            self.slot_ids = False
        elif self.availability_type == 'limited':
            if not self.max_bookings_per_slot:
                self.max_bookings_per_slot = 1
