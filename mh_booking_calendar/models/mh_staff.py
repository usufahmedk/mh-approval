# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.date_utils import start_of, end_of, add, subtract


class MHStaff(models.Model):
    """
    Staff members who perform services for M&H Technical Services.
    Staff can be assigned to multiple zones and have specific skills/certifications.
    """
    _name = 'mh.staff'
    _description = 'MH Staff'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # =====================================================================
    # PERSONAL INFORMATION
    # =====================================================================
    name = fields.Char(
        string='Staff Name',
        required=True,
        index=True,
        translate=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Partner',
        ondelete='cascade',
        help='Linked partner record for contact information.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, this staff member will not be available for booking.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order staff in lists.',
    )
    staff_type = fields.Selection([
        ('cleaner', 'Cleaner'),
        ('technician', 'Technician'),
        ('driver', 'Driver'),
        ('supervisor', 'Supervisor'),
    ], string='Staff Type', default='cleaner', index=True, tracking=True)

    # Contact information (from partner if linked)
    phone = fields.Char(
        string='Phone',
        index=True,
    )
    mobile = fields.Char(
        string='Mobile',
        index=True,
    )
    email = fields.Char(
        string='Email',
        index=True,
    )
    image_128 = fields.Image(
        string='Photo',
        related='partner_id.image_128',
        readonly=True,
    )

    # Employment details
    employee_id = fields.Many2one(
        'hr.employee',
        string='HR Employee',
        ondelete='cascade',
        help='Linked HR employee record.',
    )
    job_title = fields.Char(
        string='Job Title',
        translate=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        readonly=True,
    )

    # User account
    user_id = fields.Many2one(
        'res.users',
        string='User',
        ondelete='cascade',
        index=True,
        help='Linked user account for portal access.',
    )

    # =====================================================================
    # ZONE ASSIGNMENT
    # =====================================================================
    zone_ids = fields.Many2many(
        'mh.zone',
        'mh_zone_staff_rel',
        'staff_id',
        'zone_id',
        string='Assigned Zones',
        tracking=True,
    )
    primary_zone_id = fields.Many2one(
        'mh.zone',
        string='Primary Zone',
        ondelete='set null',
        index=True,
        tracking=True,
    )
    zone_count = fields.Integer(
        string='Zone Count',
        compute='_compute_zone_count',
        store=True,
    )

    # =====================================================================
    # CERTIFICATIONS & SKILLS
    # =====================================================================
    certification_ids = fields.Many2many(
        'mh.staff.certification',
        'mh_staff_certification_rel',
        'staff_id',
        'certification_id',
        string='Certifications',
        tracking=True,
    )
    skill_ids = fields.Many2many(
        'mh.staff.skill',
        'mh_staff_skill_rel',
        'staff_id',
        'skill_id',
        string='Skills',
    )

    # =====================================================================
    # CAPACITY & AVAILABILITY
    # =====================================================================
    max_daily_bookings = fields.Integer(
        string='Max Daily Bookings',
        default=5,
        help='Maximum number of bookings per day for this staff member.',
    )
    max_weekly_bookings = fields.Integer(
        string='Max Weekly Bookings',
        default=25,
        help='Maximum number of bookings per week for this staff member.',
    )
    working_hours_template_id = fields.Many2one(
        'resource.calendar',
        string='Working Hours',
        ondelete='restrict',
        help='Working hours template for availability calculation.',
    )

    # Working schedule
    working_days = fields.Char(
        string='Working Days',
        default='1,2,3,4,5',  # Monday to Friday
        help='Comma-separated day numbers (1=Monday, 7=Sunday).',
    )
    working_hour_start = fields.Float(
        string='Default Start Time',
        default=9.0,
        widget='float_time',
    )
    working_hour_end = fields.Float(
        string='Default End Time',
        default=18.0,
        widget='float_time',
    )

    # Availability exceptions
    leave_ids = fields.One2many(
        'mh.staff.leave',
        'staff_id',
        string='Leaves/Absences',
    )

    # =====================================================================
    # BOOKING STATISTICS
    # =====================================================================
    booking_count = fields.Integer(
        string='Total Bookings',
        compute='_compute_booking_count',
    )
    booking_count_today = fields.Integer(
        string="Today's Bookings",
        compute='_compute_booking_count_today',
    )
    booking_count_week = fields.Integer(
        string="This Week's Bookings",
        compute='_compute_booking_count_week',
    )
    booking_count_month = fields.Integer(
        string="This Month's Bookings",
        compute='_compute_booking_count_month',
    )

    # Performance metrics
    completion_rate = fields.Float(
        string='Completion Rate (%)',
        compute='_compute_performance_metrics',
        digits=(5, 2),
    )
    avg_customer_rating = fields.Float(
        string='Avg. Customer Rating',
        compute='_compute_performance_metrics',
        digits=(5, 2),
    )
    total_hours_worked = fields.Float(
        string='Total Hours Worked',
        compute='_compute_performance_metrics',
    )

    # =====================================================================
    # TEAM ASSIGNMENT
    # =====================================================================
    team_id = fields.Many2one(
        'mh.driver.team',
        string='Driver Team',
        ondelete='set null',
        index=True,
    )
    is_team_lead = fields.Boolean(
        string='Is Team Lead',
        default=False,
    )

    # =====================================================================
    # BOOKING RELATIONS
    # =====================================================================
    booking_ids = fields.Many2many(
        'mh.booking',
        'mh_booking_staff_rel',
        'staff_id',
        'booking_id',
        string='Bookings',
        readonly=True,
    )
    upcoming_booking_ids = fields.One2many(
        'mh.booking',
        string='Upcoming Bookings',
        compute='_compute_upcoming_bookings',
    )

    # =====================================================================
    # VEHICLE & EQUIPMENT
    # =====================================================================
    vehicle_id = fields.Many2one(
        'mh.vehicle',
        string='Assigned Vehicle',
        ondelete='set null',
    )
    equipment_ids = fields.Many2many(
        'mh.equipment',
        'mh_staff_equipment_rel',
        'staff_id',
        'equipment_id',
        string='Equipment',
    )

    # =====================================================================
    # COLOR & DISPLAY
    # =====================================================================
    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Color for calendar and Gantt view representation.',
    )

    # =====================================================================
    # COMPANY & NOTES
    # =====================================================================
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    notes = fields.Text(
        string='Internal Notes',
    )

    # =====================================================================
    # COMPUTED FIELDS
    # =====================================================================
    @api.depends('zone_ids')
    def _compute_zone_count(self):
        """Compute the number of assigned zones."""
        for record in self:
            record.zone_count = len(record.zone_ids)

    def _compute_booking_count(self):
        """Compute total booking count for this staff member."""
        for record in self:
            count = self.env['mh.booking'].search_count([
                ('staff_ids', 'in', record.id),
                ('state', 'not in', ['cancelled']),
            ])
            record.booking_count = count

    def _compute_booking_count_today(self):
        """Compute today's booking count for this staff member."""
        today = fields.Date.context_today(self)
        for record in self:
            count = self.env['mh.booking'].search_count([
                ('staff_ids', 'in', record.id),
                ('booking_date', '=', today),
                ('state', 'not in', ['cancelled']),
            ])
            record.booking_count_today = count

    def _compute_booking_count_week(self):
        """Compute this week's booking count for this staff member."""
        today = fields.Date.context_today(self)
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        for record in self:
            count = self.env['mh.booking'].search_count([
                ('staff_ids', 'in', record.id),
                ('booking_date', '>=', start_of_week),
                ('booking_date', '<=', end_of_week),
                ('state', 'not in', ['cancelled']),
            ])
            record.booking_count_week = count

    def _compute_booking_count_month(self):
        """Compute this month's booking count for this staff member."""
        today = fields.Date.context_today(self)
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + relativedelta(months=1) - timedelta(days=1))

        for record in self:
            count = self.env['mh.booking'].search_count([
                ('staff_ids', 'in', record.id),
                ('booking_date', '>=', start_of_month),
                ('booking_date', '<=', end_of_month),
                ('state', 'not in', ['cancelled']),
            ])
            record.booking_count_month = count

    def _compute_upcoming_bookings(self):
        """Compute upcoming bookings for this staff member."""
        for record in self:
            now = fields.Datetime.now()
            bookings = self.env['mh.booking'].search([
                ('staff_ids', 'in', record.id),
                ('booking_date_start', '>=', now),
                ('state', 'in', ['confirmed', 'in_progress']),
            ], limit=10)
            record.upcoming_booking_ids = bookings

    def _compute_performance_metrics(self):
        """Compute performance metrics for this staff member."""
        for record in self:
            # Get completed bookings
            bookings = self.env['mh.booking'].search([
                ('staff_ids', 'in', record.id),
                ('state', '=', 'completed'),
            ])

            if not bookings:
                record.completion_rate = 0.0
                record.avg_customer_rating = 0.0
                record.total_hours_worked = 0.0
            else:
                total = len(bookings)
                # Calculate completion rate
                all_bookings = self.env['mh.booking'].search([
                    ('staff_ids', 'in', record.id),
                    ('state', 'not in', ['draft', 'cancelled']),
                ])
                completed = len([b for b in all_bookings if b.state == 'completed'])
                record.completion_rate = (completed / len(all_bookings) * 100) if all_bookings else 0.0

                # Calculate average rating
                ratings = [b.customer_rating for b in bookings if b.customer_rating]
                record.avg_customer_rating = sum(ratings) / len(ratings) if ratings else 0.0

                # Calculate total hours
                record.total_hours_worked = sum(bookings.mapped('duration'))

    # =====================================================================
    # CONSTRAINTS
    # =====================================================================
    @api.constrains('user_id')
    def _check_user_link(self):
        """Ensure user is linked only to one staff member."""
        for record in self:
            if record.user_id:
                existing = self.search([
                    ('id', '!=', record.id),
                    ('user_id', '=', record.user_id.id),
                ])
                if existing:
                    raise ValidationError(
                        _('User "%s" is already linked to another staff member.')
                        % record.user_id.name
                    )

    @api.constrains('partner_id')
    def _check_partner_link(self):
        """Ensure partner is linked only to one staff member."""
        for record in self:
            if record.partner_id:
                existing = self.search([
                    ('id', '!=', record.id),
                    ('partner_id', '=', record.partner_id.id),
                ])
                if existing:
                    raise ValidationError(
                        _('Partner "%s" is already linked to another staff member.')
                        % record.partner_id.name
                    )

    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    def get_working_days(self):
        """Return list of working day numbers."""
        self.ensure_one()
        if not self.working_days:
            return []
        return [int(d) for d in self.working_days.split(',')]

    def is_working_day(self, date):
        """Check if given date is a working day for this staff member."""
        self.ensure_one()
        working_days = self.get_working_days()
        return date.weekday() + 1 in working_days

    def is_available(self, date_start, date_end, zone_id=False):
        """
        Check if staff member is available for the given time period.
        Optionally check zone availability.
        """
        self.ensure_one()

        # Check if on leave
        leave = self.env['mh.staff.leave'].search([
            ('staff_id', '=', self.id),
            ('date_from', '<=', date_end),
            ('date_to', '>=', date_start),
            ('state', '=', 'approved'),
        ])
        if leave:
            return False, 'On leave'

        # Check for booking conflicts
        conflict_domain = [
            ('staff_ids', 'in', self.id),
            ('booking_date_start', '<', date_end),
            ('booking_date_end', '>', date_start),
            ('state', 'not in', ['cancelled', 'completed', 'no_show']),
        ]
        conflicts = self.env['mh.booking'].search(conflict_domain)
        if conflicts:
            return False, f'Booking conflict: {conflicts[0].name}'

        # Check zone assignment if zone specified
        if zone_id:
            zone = self.env['mh.zone'].browse(zone_id)
            if zone and zone not in self.zone_ids:
                return False, f'Not assigned to zone {zone.name}'

        # Check daily limit
        booking_date = fields.Date.to_date(date_start)
        daily_count = self.env['mh.booking'].search_count([
            ('staff_ids', 'in', self.id),
            ('booking_date', '=', booking_date),
            ('state', 'not in', ['cancelled']),
        ])
        if daily_count >= self.max_daily_bookings:
            return False, 'Daily booking limit reached'

        return True, 'Available'

    def get_available_slots(self, date, duration=2.0, zone_id=False):
        """Get available time slots for a given date."""
        self.ensure_one()
        if not self.is_working_day(date):
            return []

        slots = []
        current_hour = self.working_hour_start

        while current_hour + duration <= self.working_hour_end:
            slot_start = datetime.combine(date, datetime.min.time()).replace(
                hour=int(current_hour),
                minute=int((current_hour % 1) * 60)
            )
            slot_end = datetime.combine(date, datetime.min.time()).replace(
                hour=int(current_hour + duration),
                minute=int(((current_hour + duration) % 1) * 60)
            )

            available, _ = self.is_available(slot_start, slot_end, zone_id)
            if available:
                slots.append({
                    'start': slot_start,
                    'end': slot_end,
                    'hour': current_hour,
                })

            current_hour += 1.0

        return slots

    def get_bookings_for_date(self, date):
        """Get all bookings for a specific date."""
        self.ensure_one()
        return self.env['mh.booking'].search([
            ('staff_ids', 'in', self.id),
            ('booking_date', '=', date),
            ('state', 'not in', ['cancelled']),
        ], order='booking_date_start')

    # =====================================================================
    # ACTION METHODS
    # =====================================================================
    def action_view_bookings(self):
        """Action to view all bookings for this staff member."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Staff Bookings'),
            'res_model': 'mh.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('staff_ids', 'in', self.id)],
            'context': {'default_staff_ids': [(4, self.id)]},
        }

    def action_view_calendar(self):
        """Action to view calendar view of bookings."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Staff Calendar'),
            'res_model': 'mh.booking',
            'view_mode': 'calendar',
            'domain': [('staff_ids', 'in', self.id)],
            'context': {'default_staff_ids': [(4, self.id)]},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set defaults."""
        for vals in vals_list:
            if vals.get('partner_id') and not vals.get('name'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                vals['name'] = partner.name
                vals['phone'] = partner.phone
                vals['mobile'] = partner.mobile
                vals['email'] = partner.email
        return super().create(vals_list)

    def write(self, vals):
        """Override write to sync with partner."""
        result = super().write(vals)
        if 'partner_id' in vals and vals['partner_id']:
            partner = self.env['res.partner'].browse(vals['partner_id'])
            sync_vals = {}
            if not self.name or self.name == partner.name:
                sync_vals['name'] = partner.name
            if not self.phone:
                sync_vals['phone'] = partner.phone
            if not self.mobile:
                sync_vals['mobile'] = partner.mobile
            if not self.email:
                sync_vals['email'] = partner.email
            if sync_vals:
                super().write(sync_vals)
        return result


class MHStaffCertification(models.Model):
    """
    Certifications that staff can hold.
    Examples: HVAC Certification, Electrical License, Safety Certificate
    """
    _name = 'mh.staff.certification'
    _description = 'MH Staff Certification'
    _order = 'name'

    name = fields.Char(
        string='Certification Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        index=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )
    validity_months = fields.Integer(
        string='Validity (Months)',
        default=12,
        help='How many months the certification is valid for.',
    )
    issuing_body = fields.Char(
        string='Issuing Body',
        translate=True,
    )
    staff_ids = fields.Many2many(
        'mh.staff',
        'mh_staff_certification_rel',
        'certification_id',
        'staff_id',
        string='Staff Members',
        readonly=True,
    )
    staff_count = fields.Integer(
        string='Staff Count',
        compute='_compute_staff_count',
        store=True,
    )
    booking_type_ids = fields.Many2many(
        'mh.booking.type',
        'mh_booking_type_certification_rel',
        'certification_id',
        'booking_type_id',
        string='Required For Booking Types',
    )

    def _compute_staff_count(self):
        """Compute number of staff with this certification."""
        for record in self:
            record.staff_count = len(record.staff_ids)

    def action_view_staff(self):
        """Action to view all staff with this certification."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Certified Staff'),
            'res_model': 'mh.staff',
            'view_mode': 'tree,form',
            'domain': [('certification_ids', 'in', self.id)],
        }


class MHStaffSkill(models.Model):
    """
    Skills that staff can possess.
    Examples: Deep Cleaning, Painting, Plumbing, Electrical
    """
    _name = 'mh.staff.skill'
    _description = 'MH Staff Skill'
    _order = 'name'

    name = fields.Char(
        string='Skill Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        index=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )
    category_id = fields.Many2one(
        'mh.staff.skill.category',
        string='Category',
        ondelete='set null',
    )
    staff_ids = fields.Many2many(
        'mh.staff',
        'mh_staff_skill_rel',
        'skill_id',
        'staff_id',
        string='Staff Members',
        readonly=True,
    )
    staff_count = fields.Integer(
        string='Staff Count',
        compute='_compute_staff_count',
        store=True,
    )

    def _compute_staff_count(self):
        """Compute number of staff with this skill."""
        for record in self:
            record.staff_count = len(record.staff_ids)


class MHStaffSkillCategory(models.Model):
    """
    Categories for grouping staff skills.
    Examples: Cleaning, Maintenance, Technical, Administrative
    """
    _name = 'mh.staff.skill.category'
    _description = 'MH Staff Skill Category'
    _order = 'name'

    name = fields.Char(
        string='Category Name',
        required=True,
        index=True,
        translate=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )
    skill_ids = fields.One2many(
        'mh.staff.skill',
        'category_id',
        string='Skills',
    )
    skill_count = fields.Integer(
        string='Skill Count',
        compute='_compute_skill_count',
        store=True,
    )

    def _compute_skill_count(self):
        """Compute number of skills in this category."""
        for record in self:
            record.skill_count = len(record.skill_ids)


class MHStaffLeave(models.Model):
    """
    Staff leaves and absences.
    """
    _name = 'mh.staff.leave'
    _description = 'MH Staff Leave'
    _order = 'date_from desc'

    name = fields.Char(
        string='Leave Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default='New',
    )
    staff_id = fields.Many2one(
        'mh.staff',
        string='Staff Member',
        required=True,
        index=True,
        ondelete='cascade',
    )
    leave_type_id = fields.Many2one(
        'mh.staff.leave.type',
        string='Leave Type',
        required=True,
        ondelete='restrict',
    )
    date_from = fields.Datetime(
        string='Start Date & Time',
        required=True,
        index=True,
    )
    date_to = fields.Datetime(
        string='End Date & Time',
        required=True,
        index=True,
    )
    duration_days = fields.Float(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)
    reason = fields.Text(
        string='Reason',
        translate=True,
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
    )
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
    )
    notes = fields.Text(
        string='Notes',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    # Overlapping bookings warning
    overlapping_booking_ids = fields.Many2many(
        'mh.booking',
        string='Overlapping Bookings',
        compute='_compute_overlapping_bookings',
    )

    @api.depends('date_from', 'date_to')
    def _compute_duration(self):
        """Compute leave duration in days."""
        for record in self:
            if record.date_from and record.date_to:
                delta = record.date_to - record.date_from
                # Assuming 8 hours per day
                record.duration_days = delta.days + (delta.seconds / 28800)

    def _compute_overlapping_bookings(self):
        """Find bookings that overlap with this leave."""
        for record in self:
            if record.date_from and record.date_to:
                bookings = self.env['mh.booking'].search([
                    ('staff_ids', 'in', record.staff_id.id),
                    ('booking_date_start', '<', record.date_to),
                    ('booking_date_end', '>', record.date_from),
                    ('state', 'not in', ['cancelled', 'completed', 'no_show']),
                ])
                record.overlapping_booking_ids = bookings
            else:
                record.overlapping_booking_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mh.staff.leave') or 'New'
        return super().create(vals_list)

    def action_approve(self):
        """Approve the leave request."""
        for record in self:
            record.write({
                'state': 'approved',
                'approved_by': self.env.uid,
                'approved_date': fields.Datetime.now(),
            })
        return True

    def action_reject(self):
        """Reject the leave request."""
        self.write({'state': 'rejected'})
        return True


class MHStaffLeaveType(models.Model):
    """
    Types of staff leaves.
    Examples: Annual Leave, Sick Leave, Emergency Leave, Training
    """
    _name = 'mh.staff.leave.type'
    _description = 'MH Staff Leave Type'
    _order = 'name'

    name = fields.Char(
        string='Leave Type',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        index=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    color = fields.Integer(
        string='Color',
        default=0,
    )
    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=True,
    )
    leave_count = fields.Integer(
        string='Leave Count',
        compute='_compute_leave_count',
    )

    def _compute_leave_count(self):
        """Compute number of leaves of this type."""
        for record in self:
            record.leave_count = self.env['mh.staff.leave'].search_count([
                ('leave_type_id', '=', record.id),
            ])


class MHVehicle(models.Model):
    """
    Company vehicles used for staff transportation.
    """
    _name = 'mh.vehicle'
    _description = 'MH Vehicle'
    _order = 'name'

    name = fields.Char(
        string='Vehicle Name',
        required=True,
        index=True,
    )
    license_plate = fields.Char(
        string='License Plate',
        required=True,
        index=True,
    )
    vehicle_type = fields.Selection([
        ('van', 'Van'),
        ('truck', 'Truck'),
        ('car', 'Car'),
        ('bike', 'Bike'),
    ], string='Vehicle Type', default='van')
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    driver_id = fields.Many2one(
        'mh.staff',
        string='Primary Driver',
        ondelete='set null',
    )
    capacity_kg = fields.Float(
        string='Capacity (kg)',
        default=1000.0,
    )
    capacity_volume = fields.Float(
        string='Capacity (m³)',
        help='Volume capacity in cubic meters.',
    )
    fuel_type = fields.Selection([
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
    ], string='Fuel Type', default='diesel')
    last_service_date = fields.Date(
        string='Last Service Date',
    )
    next_service_date = fields.Date(
        string='Next Service Date',
    )
    odometer_reading = fields.Float(
        string='Odometer (km)',
        help='Current odometer reading.',
    )
    notes = fields.Text(
        string='Notes',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )


class MHEquipment(models.Model):
    """
    Equipment assigned to staff for service delivery.
    """
    _name = 'mh.equipment'
    _description = 'MH Equipment'
    _order = 'name'

    name = fields.Char(
        string='Equipment Name',
        required=True,
        index=True,
        translate=True,
    )
    code = fields.Char(
        string='Equipment Code',
        index=True,
    )
    equipment_type = fields.Selection([
        ('cleaning', 'Cleaning Equipment'),
        ('power_tools', 'Power Tools'),
        ('safety', 'Safety Equipment'),
        ('measurement', 'Measurement Tools'),
        ('other', 'Other'),
    ], string='Type', default='other')
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    staff_ids = fields.Many2many(
        'mh.staff',
        'mh_staff_equipment_rel',
        'equipment_id',
        'staff_id',
        string='Assigned Staff',
        readonly=True,
    )
    staff_count = fields.Integer(
        string='Staff Count',
        compute='_compute_staff_count',
        store=True,
    )
    serial_number = fields.Char(
        string='Serial Number',
    )
    purchase_date = fields.Date(
        string='Purchase Date',
    )
    warranty_expiry = fields.Date(
        string='Warranty Expiry',
    )
    last_maintenance = fields.Date(
        string='Last Maintenance',
    )
    next_maintenance = fields.Date(
        string='Next Maintenance',
    )
    condition = fields.Selection([
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('maintenance', 'Needs Maintenance'),
    ], string='Condition', default='good')
    notes = fields.Text(
        string='Notes',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    def _compute_staff_count(self):
        """Compute number of staff using this equipment."""
        for record in self:
            record.staff_count = len(record.staff_ids)
