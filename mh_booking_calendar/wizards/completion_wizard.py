# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MhBookingCompletionWizard(models.TransientModel):
    _name = 'mh.booking.completion.wizard'
    _description = 'Booking Completion Wizard'

    booking_id = fields.Many2one(
        'mh.booking',
        string='Booking',
        required=True,
        readonly=True,
        ondelete='cascade',
        default=lambda self: self.env.context.get('default_booking_id'),
    )

    # Completion details
    completion_notes = fields.Text(
        string='Completion Notes',
        help='Add notes about the service performed'
    )

    # Checklist completion status
    checklist_completed = fields.Boolean(
        string='Checklist Completed',
        related='booking_id.checklist_completed',
        readonly=True
    )

    # Customer feedback
    customer_feedback = fields.Text(
        string='Customer Feedback'
    )

    customer_rating = fields.Integer(
        string='Customer Rating',
    )

    # Notification settings for this completion
    send_completion_notification = fields.Boolean(
        string='Send Completion Notification',
        help='Send WhatsApp/Email to customer',
        default=lambda self: self._get_default_notification_setting()
    )

    notification_method = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('both', 'Both'),
    ], string='Method', default='whatsapp')

    @api.model
    def _get_default_notification_setting(self):
        """Get default from booking's completion_notification_setting"""
        booking = self.env['mh.booking'].browse(
            self.env.context.get('default_booking_id')
        )
        if booking:
            return booking.completion_notification_setting != 'off'
        return True

    def action_confirm_completion(self):
        """Confirm completion and optionally send notification"""
        self.ensure_one()

        if not self.checklist_completed:
            # Warn but allow completion anyway
            pass

        # Update booking
        self.booking_id.write({
            'state': 'completed',
            'completion_date': fields.Datetime.now(),
            'completion_notes': self.completion_notes,
            'customer_feedback': self.customer_feedback,
            'customer_rating': self.customer_rating,
        })

        # Send notification if enabled
        if self.send_completion_notification:
            self._send_completion_notification()

        return {'type': 'ir.actions.act_window_close'}

    def _send_completion_notification(self):
        """Send completion notification"""
        self.ensure_one()

        if self.notification_method in ['whatsapp', 'both']:
            self.booking_id.action_send_whatsapp()

        if self.notification_method in ['email', 'both']:
            template = self.env.ref(
                'mh_booking_calendar.booking_completion_email',
                raise_if_not_found=False
            )
            if template:
                template.send_mail(self.booking_id.id, force_send=True)

        # Mark notification as sent
        self.booking_id.write({
            'whatsapp_sent': True,
            'whatsapp_date': fields.Datetime.now(),
        })

    def action_skip_notification(self):
        """Complete without sending notification"""
        self.ensure_one()

        self.booking_id.write({
            'state': 'completed',
            'completion_date': fields.Datetime.now(),
            'completion_notes': self.completion_notes,
            'customer_feedback': self.customer_feedback,
            'customer_rating': self.customer_rating,
            # Do NOT send notification
        })

        return {'type': 'ir.actions.act_window_close'}