# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools.translate import _


class MHBookingType(models.Model):
    """
    Defines the types of booking services offered by M&H Technical Services.
    Examples: Deep Cleaning, Routine Maintenance, AMC Visit, Emergency Service
    """
    _name = 'mh.booking.type'
    _description = 'MH Booking Type'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Booking Type Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        index=True,
        help='Short code for the booking type'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order the booking types in lists.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this booking type will not be available for selection.',
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )
    duration = fields.Float(
        string='Default Duration (Hours)',
        default=2.0,
        digits=(5, 2),
        help='Default estimated duration for this booking type.',
    )
    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Used to color-code booking types in calendar views.',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Related Product',
        domain=[('type', '=', 'service')],
        help='The product associated with this booking type for sale orders.',
    )
    invoice_policy = fields.Selection([
        ('prepaid', 'Prepaid'),
        ('delivery', 'Delivered'),
    ], string='Invoice Policy', default='delivery')
    price = fields.Float(
        string='Default Price',
        digits='Product Price',
    )
    booking_count = fields.Integer(
        string='Number of Bookings',
        compute='_compute_booking_count',
    )

    # Zone assignment - which zones this booking type can be performed in
    zone_ids = fields.Many2many(
        'mh.zone',
        'mh_booking_type_zone_rel',
        'booking_type_id',
        'zone_id',
        string='Applicable Zones',
    )

    # Staff requirements
    requires_special_certification = fields.Boolean(
        string='Requires Special Certification',
        default=False,
    )
    is_commercial = fields.Boolean(
        string='Commercial',
        default=False,
        help='If True, this is a commercial cleaning booking type'
    )
    certification_ids = fields.Many2many(
        'mh.staff.certification',
        'mh_booking_type_certification_rel',
        'booking_type_id',
        'certification_id',
        string='Required Certifications',
    )
    min_staff_count = fields.Integer(
        string='Minimum Staff Required',
        default=1,
        help='Minimum number of staff members required for this booking type.',
    )
    max_staff_count = fields.Integer(
        string='Maximum Staff Allowed',
        default=5,
        help='Maximum number of staff members allowed for this booking type.',
    )

    # Technical fields
    property_ids = fields.One2many(
        'mh.booking.type.property',
        'booking_type_id',
        string='Properties',
    )

    def _compute_booking_count(self):
        """Compute the number of bookings of this type."""
        for record in self:
            count = self.env['mh.booking'].search_count([
                ('booking_type_id', '=', record.id)
            ])
            record.booking_count = count

    def action_view_bookings(self):
        """Action to view all bookings of this type."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('booking_type_id', '=', self.id)],
            'context': {'default_booking_type_id': self.id},
        }


class MHBookingTypeProperty(models.Model):
    """
    Dynamic properties that can be configured for each booking type.
    Examples: Square footage, Number of rooms, Special requirements
    """
    _name = 'mh.booking.type.property'
    _description = 'MH Booking Type Property'

    booking_type_id = fields.Many2one(
        'mh.booking.type',
        string='Booking Type',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(
        string='Property Name',
        required=True,
        translate=True,
    )
    field_type = fields.Selection([
        ('char', 'Text'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Checkbox'),
        ('selection', 'Selection'),
        ('text', 'Multi-line Text'),
    ], string='Field Type', default='char', required=True)
    default_value = fields.Char(
        string='Default Value',
    )
    required = fields.Boolean(
        string='Required',
        default=False,
    )
    placeholder = fields.Char(
        string='Placeholder',
        translate=True,
    )
    selection_options = fields.Text(
        string='Selection Options',
        help='Enter options as key=value pairs, one per line.\nExample:\nsmall=Small (up to 50 sqm)\nmedium=Medium (50-100 sqm)',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )
