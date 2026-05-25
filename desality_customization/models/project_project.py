from odoo import models, fields


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_snagging_project = fields.Boolean(
        string='Is Snagging Project',
        help='Check this box to mark this project for automatic snagging task creation from appointments',
        default=False,
        index=True,
    )

    default_assignee_ids = fields.Many2many(
        'res.users',
        string='Default Assignees',
        help='Default internal users to assign to new tasks created in this project',
        domain=[('share', '=', False)],
    )