from odoo import http
from odoo.http import request
from odoo.addons.appointment.controllers.appointment import AppointmentController


class DesalityAppointmentController(AppointmentController):

    @http.route(['/appointment/<int:appointment_type_id>/submit'],
                type='http', auth="public", website=True, methods=["POST"])
    def appointment_form_submit(self, appointment_type_id, datetime_str, duration_str, name, phone, email, 
                              staff_user_id=None, available_resource_ids=None, asked_capacity=1, 
                              guest_emails_str=None, **kwargs):
        
        appointment_type = request.env['appointment.type'].sudo().browse(appointment_type_id)
        
        if appointment_type.link_portal_user:
            portal_user_id = kwargs.get('portal_user_id')
            if portal_user_id:
                kwargs['portal_user_id'] = int(portal_user_id)
                
                kwargs['portal_user_referral'] = True
        
        return super().appointment_form_submit(
            appointment_type_id=appointment_type_id, 
            datetime_str=datetime_str, 
            duration_str=duration_str, 
            name=name, 
            phone=phone, 
            email=email, 
            staff_user_id=staff_user_id, 
            available_resource_ids=available_resource_ids, 
            asked_capacity=asked_capacity,
            guest_emails_str=guest_emails_str, 
            **kwargs
        )