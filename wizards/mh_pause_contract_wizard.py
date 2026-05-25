# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MhPauseContractWizard(models.TransientModel):
    """
    Wizard to pause AMC contracts with a reason.
    Allows pausing subscriptions due to pending payment, seasonal closure,
    or customer request.
    """
    _name = 'mh.pause.contract.wizard'
    _description = 'Pause Contract Wizard'

    pause_reason = fields.Selection([
        ('pending_payment', 'Pending Payment'),
        ('seasonal', 'Seasonal'),
        ('client_request', 'Client Request'),
    ], string='Pause Reason', required=True)

    notes = fields.Text(string='Notes')

    def action_confirm_pause(self):
        """Pause the contract with selected reason."""
        self.ensure_one()
        order_ids = self.env.context.get('active_ids', [])

        if not order_ids:
            raise ValidationError(_('No subscriptions selected.'))

        # In Odoo 18, subscriptions are sale.order with is_subscription=True
        subscriptions = self.env['sale.order'].browse(order_ids).filtered(
            lambda o: o.is_subscription
        )

        for subscription in subscriptions:
            subscription.write({
                'mh_paused': True,
                'pause_reason': self.pause_reason,
                'pause_date': fields.Date.today(),
            })

        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        """Close wizard without action."""
        return {'type': 'ir.actions.act_window_close'}
