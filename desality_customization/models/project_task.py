from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Related Appointment',
        help='Appointment that generated this task',
        index=True,
        ondelete='set null',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-assign default assignees from project"""
        for vals in vals_list:
            if not vals.get('user_ids') and vals.get('project_id'):
                project = self.env['project.project'].browse(vals['project_id'])
                if project.default_assignee_ids:
                    vals['user_ids'] = [(6, 0, project.default_assignee_ids.ids)]

        return super().create(vals_list)

    def action_view_appointment(self):
        """Action to view related appointment from smart button"""
        self.ensure_one()
        if not self.calendar_event_id:
            return False
            
        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Appointment',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'res_id': self.calendar_event_id.id,
            'target': 'current',
        }

    def unlink(self):
        """Override unlink to handle appointment relationship properly"""
        try:
            appointments_to_flag = set()
            for task in self:
                if task.calendar_event_id:
                    appointments_to_flag.add(task.calendar_event_id)
            result = super().unlink()
            for appointment in appointments_to_flag:
                appointment.tasks_deleted_manually = True
            
            return result
            
        except Exception as e:
            pass
            raise