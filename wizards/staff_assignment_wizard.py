# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class MhStaffAssignmentWizard(models.TransientModel):
    _name = 'mh.employee.assignment.wizard'
    _description = 'Staff Assignment Wizard'

    booking_id = fields.Many2one(
        'mh.booking',
        string='Booking',
        required=True,
        ondelete='cascade',
    )

    zone_id = fields.Many2one(
        'mh.zone',
        string='Zone',
        related='booking_id.zone_id',
        readonly=True,
    )

    booking_date_start = fields.Datetime(
        string='Booking Start',
        related='booking_id.booking_date_start',
        readonly=True,
    )

    booking_date_end = fields.Datetime(
        string='Booking End',
        related='booking_id.booking_date_end',
        readonly=True,
    )

    staff_ids = fields.Many2many(
        'hr.employee',
        'wizard_staff_rel',
        'wizard_id',
        'staff_id',
        string='Assign Staff',
        domain="[('active', '=', True)]",
        required=True,
    )

    # Conflict warnings
    conflict_warning = fields.Text(
        string='Conflict Warning',
        compute='_compute_conflict_warning',
    )

    available_staff_count = fields.Integer(
        string='Available Staff Count',
        compute='_compute_available_staff',
    )

    @api.depends('staff_ids', 'booking_date_start', 'booking_date_end', 'zone_id')
    def _compute_conflict_warning(self):
        for wizard in self:
            warnings = []
            if not wizard.staff_ids:
                wizard.conflict_warning = ''
                continue

            for staff in wizard.staff_ids:
                conflicts = self._check_staff_conflicts(staff)
                for conflict in conflicts:
                    warnings.append(
                        f"Warning: {staff.name}: {conflict.name}"
                    )

            wizard.conflict_warning = '\n'.join(warnings) if warnings else ''

    @api.depends('zone_id', 'booking_date_start', 'booking_date_end')
    def _compute_available_staff(self):
        for wizard in self:
            if not wizard.zone_id or not wizard.booking_date_start:
                wizard.available_staff_count = 0
                continue

            # Find available staff in zone
            staff_pool = self.env['hr.employee']
            zone_staff = staff_pool.search([
                ('zone_ids', 'in', wizard.zone_id.id),
                ('active', '=', True),
            ])

            available = 0
            for staff in zone_staff:
                if not self._check_staff_conflicts(staff):
                    available += 1

            wizard.available_staff_count = available

    def _check_staff_conflicts(self, staff):
        """Check for conflicts with staff"""
        domain = [
            ('id', '!=', self.booking_id.id or False),
            ('staff_ids', 'in', staff.id),
            ('state', 'not in', ['cancelled', 'completed', 'no_show']),
            ('booking_date_start', '<', self.booking_date_end),
            ('booking_date_end', '>', self.booking_date_start),
        ]
        return self.env['mh.booking'].search(domain)

    def action_assign_staff(self):
        """Assign staff to booking"""
        self.ensure_one()

        if self.conflict_warning:
            # Confirm with warning
            raise ValidationError(
                _('Cannot assign staff with unresolved conflicts.\n'
                  'Please resolve conflicts before assigning.')
            )

        # Assign staff to booking
        self.booking_id.write({
            'staff_ids': [(6, 0, self.staff_ids.ids)],
        })

        return {'type': 'ir.actions.act_window_close'}