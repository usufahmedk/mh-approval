from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_default_lead_assignee = fields.Boolean(
        string='Default Lead Assignee',
        help='If checked, this user will be automatically assigned to new leads when no other user is specified',
        default=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_default_lead_assignee'):
                self.env['res.users'].search([('is_default_lead_assignee', '=', True)]).write({
                    'is_default_lead_assignee': False
                })
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('is_default_lead_assignee'):
            other_users = self.env['res.users'].search([
                ('is_default_lead_assignee', '=', True),
                ('id', 'not in', self.ids)
            ])
            if other_users:
                other_users.write({'is_default_lead_assignee': False})
        return super().write(vals)