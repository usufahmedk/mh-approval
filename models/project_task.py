# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    """
    Extension of project.task to integrate with MH Booking system.
    Adds booking-related fields and functionality.
    """
    _name = 'project.task'
    _inherit = ['project.task', 'mail.thread']

    # =====================================================================
    # BOOKING INTEGRATION FIELDS
    # =====================================================================
    booking_id = fields.Many2one(
        'mh.booking',
        string='Related Booking',
        index=True,
        ondelete='cascade',
        copy=False,
    )
    is_booking_task = fields.Boolean(
        string='Is Booking Task',
        compute='_compute_is_booking_task',
        store=True,
    )

    # Booking details (cached from booking for display)
    booking_reference = fields.Char(
        string='Booking Reference',
        related='booking_id.name',
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Service Product',
        related='booking_id.product_id',
        readonly=True,
    )
    booking_date = fields.Date(
        string='Booking Date',
        related='booking_id.booking_date',
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

    # Zone and staff
    zone_id = fields.Many2one(
        'mh.zone',
        string='Zone',
        related='booking_id.zone_id',
        readonly=True,
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Assigned Employees',
        related='booking_id.staff_ids',
        readonly=True,
    )
    team_lead_id = fields.Many2one(
        'hr.employee',
        string='Team Lead',
        related='booking_id.team_lead_id',
        readonly=True,
    )

    # Customer
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='booking_id.partner_id',
        readonly=True,
    )
    service_address = fields.Text(
        string='Service Address',
        related='booking_id.delivery_address',
        readonly=True,
    )

    # Checklist from booking
    checklist_line_ids = fields.One2many(
        'mh.booking.checklist',
        string='Checklist',
        related='booking_id.checklist_line_ids',
        readonly=True,
    )
    checklist_completed = fields.Boolean(
        string='Checklist Completed',
        related='booking_id.checklist_completed',
        readonly=True,
    )

    # Completion info
    completion_date = fields.Datetime(
        string='Completion Date',
        related='booking_id.completion_date',
        readonly=True,
    )
    completion_notes = fields.Text(
        string='Completion Notes',
        related='booking_id.completion_notes',
        readonly=True,
    )
    customer_feedback = fields.Text(
        string='Customer Feedback',
        related='booking_id.customer_feedback',
        readonly=True,
    )
    customer_rating = fields.Integer(
        string='Customer Rating',
        related='booking_id.customer_rating',
        readonly=True,
    )

    # Material usage tracking
    material_line_ids = fields.One2many(
        'project.task.material',
        'task_id',
        string='Materials Used',
    )
    total_material_cost = fields.Monetary(
        string='Total Material Cost',
        compute='_compute_total_material_cost',
        store=True,
        currency_field='currency_id',
    )

    # Signature
    customer_signature = fields.Binary(
        string='Customer Signature',
        attachment=True,
        copy=False,
    )
    signature_date = fields.Datetime(
        string='Signature Date',
        copy=False,
    )
    signature_name = fields.Char(
        string='Signed By',
        copy=False,
    )

    # Photos (before/after)
    photo_before_ids = fields.Many2many(
        'ir.attachment',
        'mh_booking_photo_before_rel',
        string='Before Photos',
        domain=[('mimetype', 'ilike', 'image')],
        context={'default_mimetype': 'image/jpeg'},
    )
    photo_after_ids = fields.Many2many(
        'ir.attachment',
        'mh_booking_photo_after_rel',
        string='After Photos',
        domain=[('mimetype', 'ilike', 'image')],
        context={'default_mimetype': 'image/jpeg'},
    )

    # Currency for material costs
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )

    # =====================================================================
    # COMPUTED FIELDS
    # =====================================================================
    @api.depends('booking_id')
    def _compute_is_booking_task(self):
        """Determine if this task is related to a booking."""
        for record in self:
            record.is_booking_task = bool(record.booking_id)

    @api.depends('material_line_ids', 'material_line_ids.cost_subtotal')
    def _compute_total_material_cost(self):
        """Compute total material cost."""
        for record in self:
            record.total_material_cost = sum(
                record.material_line_ids.mapped('cost_subtotal')
            )

    # =====================================================================
    # OVERRIDE METHODS
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set project from booking if needed."""
        for vals in vals_list:
            if vals.get('booking_id') and not vals.get('project_id'):
                booking = self.env['mh.booking'].browse(vals['booking_id'])
                if booking.project_id:
                    vals['project_id'] = booking.project_id.id
                elif booking.zone_id and booking.zone_id.team_id:
                    # Create or get project for this customer/zone
                    project = record._get_or_create_project(
                        booking.partner_id,
                        booking.zone_id
                    )
                    vals['project_id'] = project.id
        return super().create(vals_list)

    def write(self, vals):
        """Override write to sync with booking."""
        result = super().write(vals)

        # Sync state with booking
        if 'stage_id' in vals:
            for record in self:
                if record.booking_id:
                    if record.stage_id and record.stage_id.fold:
                        # Task is done
                        record.booking_id.write({'state': 'completed'})
                    elif record.stage_id and record.stage_id.name == 'In Progress':
                        record.booking_id.write({'state': 'in_progress'})

        return result

    # =====================================================================
    # FSM INTEGRATION METHODS (industry_fsm)
    # =====================================================================
    def action_fsm_validate(self):
        """Override FSM validation to sync with booking."""
        result = super().action_fsm_validate()

        # Sync completion to booking
        if self.booking_id:
            self.booking_id.write({
                'state': 'completed',
                'completion_date': fields.Datetime.now(),
            })

        return result

    def action_fsm_start(self):
        """Override FSM start to sync with booking."""
        result = super().action_fsm_start()

        if self.booking_id:
            self.booking_id.write({'state': 'in_progress'})

        return result

    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    def _get_or_create_project(self, partner, zone):
        """Get or create a project for the customer/zone combination."""
        self.ensure_one()

        # Check for existing project
        project = self.env['project.project'].search([
            ('partner_id', '=', partner.id),
            ('zone_id', '=', zone.id if zone else False),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not project:
            project = self.env['project.project'].create({
                'name': f'{partner.name} - {zone.name}' if zone else partner.name,
                'partner_id': partner.id,
                'zone_id': zone.id if zone else False,
                'company_id': self.env.company.id,
            })

        return project

    def action_view_booking(self):
        """Action to view the related booking."""
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_('No booking linked to this task.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Related Booking'),
            'res_model': 'mh.booking',
            'res_id': self.booking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_sync_with_booking(self):
        """Sync task data with booking."""
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_('No booking linked to this task.'))

        self.write({
            'date_deadline': self.booking_id.booking_date,
            'planned_date_begin': self.booking_id.booking_date_start,
            'planned_date_end': self.booking_id.booking_date_end,
        })
        return True

    def action_capture_signature(self):
        """Capture signature."""
        self.ensure_one()
        self.write({
            'signature_date': fields.Datetime.now(),
            'signature_name': self.partner_id.name if self.partner_id else '',
        })
        return True

    def action_add_photo(self, photo_type='before'):
        """Add a photo to the task."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Photo'),
            'res_model': 'ir.attachment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'project.task',
                'default_res_id': self.id,
                'default_mimetype': 'image/jpeg',
            },
        }

    @api.onchange('booking_id')
    def _onchange_booking_id(self):
        """Update task fields from booking."""
        if self.booking_id:
            booking = self.booking_id
            return {
                'domain': {
                    'project_id': [
                        '|',
                        ('partner_id', '=', booking.partner_id.id),
                        ('id', '=', self.project_id.id),
                    ]
                }
            }


class ProjectTaskMaterial(models.Model):
    """
    Tracks materials used in task execution.
    Used for inventory management and cost tracking.
    """
    _name = 'project.task.material'
    _description = 'Project Task Material'
    _order = 'sequence, id'

    task_id = fields.Many2one(
        'project.task',
        string='Task',
        required=True,
        index=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('type', 'in', ['product', 'consumable'])],
        ondelete='restrict',
    )
    description = fields.Char(
        string='Description',
        related='product_id.name',
        readonly=True,
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True,
    )
    unit_cost = fields.Float(
        string='Unit Cost',
        digits='Product Price',
        help='Cost price per unit.',
    )
    cost_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_cost_subtotal',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='task_id.currency_id',
        readonly=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot/Serial Number',
        domain="[('product_id', '=', product_id)]",
        ondelete='restrict',
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Location',
        domain=[('usage', '=', 'internal')],
    )
    notes = fields.Text(
        string='Notes',
    )
    date_used = fields.Datetime(
        string='Date Used',
        default=fields.Datetime.now,
    )
    used_by = fields.Many2one(
        'res.users',
        string='Used By',
        default=lambda self: self.env.user,
    )

    @api.depends('quantity', 'unit_cost')
    def _compute_cost_subtotal(self):
        """Compute the cost subtotal."""
        for record in self:
            record.cost_subtotal = record.quantity * record.unit_cost

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update unit cost from product."""
        if self.product_id:
            self.unit_cost = self.product_id.standard_price

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set defaults."""
        for vals in vals_list:
            if not vals.get('unit_cost') and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['unit_cost'] = product.standard_price
        return super().create(vals_list)
