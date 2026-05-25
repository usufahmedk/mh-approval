
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class AppointmentTeam(models.Model):
    _name = 'appointment.team'
    _description = 'Appointment Team'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char("Team Name", required=True, tracking=True)
    description = fields.Text("Description", tracking=True)
    user_ids = fields.Many2many('res.users', 'appointment_team_user_rel', 
                               'team_id', 'user_id', string="Team Members", required=True, tracking=True)
    active = fields.Boolean("Active", default=True, tracking=True)
    color = fields.Integer("Color", help="Color for team identification")
    user_count = fields.Integer("Number of Users", compute='_compute_user_count', store=True)
    appointment_type_count = fields.Integer("Appointment Types", compute='_compute_appointment_type_count', store=True)
    
    @api.depends('user_ids')
    def _compute_user_count(self):
        for team in self:
            team.user_count = len(team.user_ids)
    
    def _compute_appointment_type_count(self):
        for team in self:
            team.appointment_type_count = self.env['appointment.type'].search_count([
                ('team_ids', 'in', team.id)
            ])
    
    @api.constrains('user_ids')
    def _check_user_ids(self):
        for team in self:
            if not team.user_ids:
                raise ValidationError(_("A team must have at least one member."))
    
    def get_available_users_for_slot(self, slot_start_utc, slot_end_utc, availability_values):
        """
        Get list of available users from this team for the given time slot
        
        :param datetime slot_start_utc: Start time of the slot in UTC
        :param datetime slot_end_utc: End time of the slot in UTC
        :param dict availability_values: Availability data from appointment type
        :return: recordset of available users
        """
        available_users = self.env['res.users']
        
        for user in self.user_ids:
            if self._is_user_available_for_slot(user, slot_start_utc, slot_end_utc, availability_values):
                available_users |= user
                
        return available_users
    
    def _is_user_available_for_slot(self, user, slot_start_utc, slot_end_utc, availability_values):
        """
        Check if a specific user is available for the given time slot
        Enhanced to check ALL calendar events, not just appointment-linked ones
        
        :param res.users user: User to check
        :param datetime slot_start_utc: Start time in UTC
        :param datetime slot_end_utc: End time in UTC
        :param dict availability_values: Availability data
        :return: boolean
        """
        import pytz
        from dateutil import rrule
        
        user_tz = pytz.timezone(user.tz) if user.tz else pytz.utc
        slot_start_user_tz = slot_start_utc.astimezone(user_tz)
        slot_end_user_tz = slot_end_utc.astimezone(user_tz)
        
        all_events = self.env['calendar.event'].search([
            ('partner_ids', 'in', user.partner_id.id),
            '|',
            '&', ('start', '<', slot_end_utc), ('stop', '>', slot_start_utc),  # Overlapping events
            '&', ('allday', '=', True), ('start_date', '=', slot_start_utc.date())  # All-day events
        ])
        
        for event in all_events:
            if event.allday:
                return False
            else:
                if event.start < slot_end_utc and event.stop > slot_start_utc:
                    return False
        
        return True
    
    def name_get(self):
        result = []
        for team in self:
            name = f"{team.name} ({team.user_count} users)"
            result.append((team.id, name))
        return result
    
    def action_view_appointment_types(self):
        return {
            'name': 'Appointment Types',
            'type': 'ir.actions.act_window',
            'res_model': 'appointment.type',
            'view_mode': 'list,form',
            'domain': [('team_ids', 'in', self.id)],
            'context': {'default_team_ids': [(6, 0, [self.id])]},
        }