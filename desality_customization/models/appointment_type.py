from odoo import models, fields, Command


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    link_portal_user = fields.Boolean(
        string="Link Portal User as Referral Partner",
        help="Automatically capture logged-in portal user and set as referral partner in CRM leads",
        default=False,
    )
    
    invoice_activity_assignee_id = fields.Many2one(
        'res.users',
        string='Invoice Activity Assignee',
        help='User who will receive the invoice creation activity',
    )
    
    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('referral_partner', 'Referral Partner')
    ], string="Appointment Type", default='customer', 
       help="Select whether this appointment is for customers or referral partners")

    def _prepare_calendar_event_values(
        self, asked_capacity, booking_line_values, duration,
        appointment_invite, guests, name, customer, staff_user, start, stop
    ):
        self.ensure_one()
        result = super()._prepare_calendar_event_values(
            asked_capacity, booking_line_values, duration, appointment_invite, 
            guests, name, customer, staff_user, start, stop
        )
        
        if self.link_portal_user:
            portal_user_id = None
            
            if isinstance(booking_line_values, dict):
                portal_user_id = booking_line_values.get('portal_user_id')
            elif hasattr(self, '_context') and 'portal_user_id' in self._context:
                portal_user_id = self._context.get('portal_user_id')
            
            if not portal_user_id and self.env.user.has_group('base.group_portal') and not self.env.user._is_public():
                portal_user_id = self.env.user.id
            elif not portal_user_id and self.env.user._is_public():
                pass
            
            if portal_user_id:
                result['portal_user_id'] = int(portal_user_id)
        
        return result