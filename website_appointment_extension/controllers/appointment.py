
import pytz

from babel.dates import format_datetime
from werkzeug.exceptions import NotFound

from odoo import Command, fields, http
from odoo.http import request
from odoo.addons.appointment.controllers.appointment import AppointmentController
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.payment import utils as payment_utils
from odoo.tools.misc import get_lang


class AppointmentInherit(AppointmentController):

    @http.route(['/appointment/<int:appointment_type_id>/submit'],
                type='http', auth="public", website=True, methods=["POST"])
    def appointment_form_submit(self, appointment_type_id, datetime_str, duration_str, name, phone, email, staff_user_id=None, available_resource_ids=None, asked_capacity=1,guest_emails_str=None, **kwargs):
        if kwargs.get('sq_ft',False):
            asked_capacity = kwargs.get('sq_ft',False)


        return super(AppointmentInherit,self).appointment_form_submit(appointment_type_id=appointment_type_id, datetime_str=datetime_str, duration_str=duration_str, name=name, phone=phone, email=email, staff_user_id=staff_user_id, available_resource_ids=available_resource_ids, asked_capacity=asked_capacity,guest_emails_str=guest_emails_str, **kwargs)

    @http.route(['/appointment/<int:appointment_type_id>/update_available_slots'], type='json', auth="public", website=True)
    def appointment_update_available_slots(self, appointment_type_id, filter_resources=None, filter_users=None,
                                         invite_token=None, resource_selected_id='', timezone=None, **kwargs):
        """Override to fix ValueError when resource_selected_id is empty string and ensure proper recordsets"""
        if resource_selected_id == '' or resource_selected_id is None:
            resource_selected_id = False
        elif resource_selected_id and str(resource_selected_id).isdigit():
            try:
                resource_selected_id = int(resource_selected_id)
            except ValueError:
                resource_selected_id = False
        else:
            resource_selected_id = False

        if filter_resources is None or filter_resources is False:
            filter_resources = request.env['appointment.resource'].sudo()
        elif isinstance(filter_resources, (list, tuple)):
            filter_resources = request.env['appointment.resource'].sudo().browse(filter_resources)

        if filter_users is None or filter_users is False:
            filter_users = request.env['res.users'].sudo()
        elif isinstance(filter_users, (list, tuple)):
            filter_users = request.env['res.users'].sudo().browse(filter_users)

        return super().appointment_update_available_slots(
            appointment_type_id=appointment_type_id,
            filter_resources=filter_resources,
            filter_users=filter_users,
            invite_token=invite_token,
            resource_selected_id=resource_selected_id,
            timezone=timezone,
            **kwargs
        )

    def _get_max_capacity_possible(self, filter_resources, resource_selected_id):
        """Override to handle boolean filter_resources parameter"""
        if filter_resources is None or filter_resources is False or filter_resources == []:
            filter_resources = request.env['appointment.resource'].sudo()
        elif isinstance(filter_resources, (list, tuple)):
            filter_resources = request.env['appointment.resource'].sudo().browse(filter_resources)

        if resource_selected_id == '' or resource_selected_id is None:
            resource_selected_id = False
        elif isinstance(resource_selected_id, str) and resource_selected_id.isdigit():
            try:
                resource_selected_id = int(resource_selected_id)
            except ValueError:
                resource_selected_id = False

        return super()._get_max_capacity_possible(filter_resources, resource_selected_id)

