# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    """
    Extension of sale.order for AMC (Annual Maintenance Contract) management.
    In Odoo 18, subscriptions are sale.order records with is_subscription=True.
    """
    _inherit = 'sale.order'

    # =====================================================================
    # AMC BOOKING INTEGRATION
    # =====================================================================
    is_amc_contract = fields.Boolean(
        string='AMC Contract',
        default=False,
        help='This is an AMC (Annual Maintenance Contract) order'
    )

    mh_zone_id = fields.Many2one(
        'mh.zone',
        string='Service Zone',
        index=True,
    )

    mh_booking_type_id = fields.Many2one(
        'mh.booking.type',
        string='Booking Type',
        index=True,
    )

    mh_staff_ids = fields.Many2many(
        'mh.staff',
        'sale_order_staff_rel',
        'order_id',
        'staff_id',
        string='Assigned Staff',
        help='Fixed staff assigned to this AMC contract'
    )

    mh_booking_ids = fields.One2many(
        'mh.booking',
        'sale_order_id',
        string='AMC Bookings',
        readonly=True,
        copy=False
    )

    # AMC Contract Details
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
    mh_paused = fields.Boolean(
        string='AMC Paused',
        default=False,
        help='AMC bookings are paused'
    )

    pause_reason = fields.Selection([
        ('pending_payment', 'Pending Payment'),
        ('seasonal', 'Seasonal'),
        ('client_request', 'Client Request'),
    ], string='Pause Reason')

    pause_date = fields.Date(string='Paused Date')

    # PPM (Preventive Maintenance)
    is_ppm = fields.Boolean(
        string='Preventive Maintenance',
        default=False,
        help='Enable preventive maintenance scheduling'
    )

    ppm_schedule = fields.Char(
        string='PPM Schedule',
        help='Quarterly schedule e.g. Q1,Q2,Q3,Q4'
    )

    # Client preference
    client_source = fields.Selection([
        ('google', 'Google'),
        ('referral', 'Referral'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('other', 'Other'),
    ], string='Customer Source', index=True)

    # =====================================================================
    # COMPUTED FIELDS
    # =====================================================================
    @api.depends('mh_booking_ids.state')
    def _compute_visits_completed(self):
        for order in self:
            order.visits_completed = len(order.mh_booking_ids.filtered_domain([
                ('state', '=', 'completed')
            ]))

    @api.depends('total_contracted_visits', 'visits_completed')
    def _compute_visits_remaining(self):
        for order in self:
            order.visits_remaining = order.total_contracted_visits - order.visits_completed

    # =====================================================================
    # ACTIONS
    # =====================================================================
    def action_pause_amc(self):
        """Pause AMC bookings"""
        self.ensure_one()
        if not self.is_amc_contract:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Pause AMC Contract',
            'res_model': 'mh.pause.amc.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def action_resume_amc(self):
        """Resume AMC bookings"""
        self.ensure_one()
        self.write({
            'mh_paused': False,
            'pause_reason': False,
            'pause_date': False,
        })

    def action_create_amc_booking(self):
        """Manually create a booking for this AMC contract"""
        self.ensure_one()
        if not self.is_amc_contract:
            raise UserError(_('This is not an AMC contract.'))

        if self.mh_paused:
            raise UserError(_('AMC contract is paused.'))

        return self._create_amc_booking()

    def _create_amc_booking(self):
        """Create a booking from this AMC contract"""
        self.ensure_one()

        if not self.mh_booking_type_id or not self.mh_zone_id:
            raise UserError(_('AMC contract must have booking type and zone defined.'))

        booking = self.env['mh.booking'].create({
            'partner_id': self.partner_id.id,
            'booking_type_id': self.mh_booking_type_id.id,
            'zone_id': self.mh_zone_id.id,
            'staff_ids': [(6, 0, self.mh_staff_ids.ids)] if self.mh_staff_ids else [(5,)],
            'sale_order_id': self.id,
            'is_amc_booking': True,
            'booking_date': fields.Date.today(),
            'booking_date_start': fields.Datetime.now(),
            'booking_date_end': fields.Datetime.now() + timedelta(hours=2),
            'client_source': self.client_source or 'referral',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mh.booking',
            'res_id': booking.id,
            'view_mode': 'form',
        }

    def action_view_amc_bookings(self):
        """View all AMC bookings"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('AMC Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
        }

    @api.onchange('is_amc_contract')
    def _onchange_is_amc_contract(self):
        """Set defaults when AMC is enabled"""
        if self.is_amc_contract:
            self.is_subscription = True


class MhPauseAmcWizard(models.TransientModel):
    _name = 'mh.pause.amc.wizard'
    _description = 'Pause AMC Contract Wizard'

    order_id = fields.Many2one(
        'sale.order',
        string='AMC Contract',
        required=True,
        default=lambda self: self.env.context.get('default_order_id'),
    )

    pause_reason = fields.Selection([
        ('pending_payment', 'Pending Payment'),
        ('seasonal', 'Seasonal'),
        ('client_request', 'Client Request'),
    ], string='Pause Reason', required=True)

    notes = fields.Text(string='Notes')

    def action_confirm_pause(self):
        """Pause the AMC contract"""
        self.ensure_one()
        self.order_id.write({
            'mh_paused': True,
            'pause_reason': self.pause_reason,
            'pause_date': fields.Date.today(),
        })
        return {'type': 'ir.actions.act_window_close'}
