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
        subscription_ids = self.env.context.get('active_ids', [])

        if not subscription_ids:
            raise ValidationError(_('No subscriptions selected.'))

        subscriptions = self.env['sale.subscription'].browse(subscription_ids)

        for subscription in subscriptions:
            subscription.write({
                'payment_pending_pause': True,
                'pause_reason': self.pause_reason,
                'pause_date': fields.Date.today(),
                'contract_notes': (
                    subscription.contract_notes + '\n' +
                    _('[%(date)s] Paused: %(reason)s - %(notes)s') % {
                        'date': fields.Date.today(),
                        'reason': self.pause_reason,
                        'notes': self.notes or '',
                    }
                ) if subscription.contract_notes else _(
                    '[%(date)s] Paused: %(reason)s - %(notes)s'
                ) % {
                    'date': fields.Date.today(),
                    'reason': self.pause_reason,
                    'notes': self.notes or '',
                },
            })

        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        """Close wizard without action."""
        return {'type': 'ir.actions.act_window_close'}
