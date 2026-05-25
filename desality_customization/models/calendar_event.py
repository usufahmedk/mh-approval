from odoo import models, fields, api


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    task_ids = fields.One2many(
        'project.task',
        'calendar_event_id',
        string='Related Tasks',
        help='Tasks created from this appointment',
    )
    
    task_count = fields.Integer(
        string='Task Count',
        compute='_compute_task_count',
        store=True,
    )
    
    tasks_deleted_manually = fields.Boolean(
        string='Tasks Deleted Manually',
        default=False,
        help='Set to True when tasks are manually deleted to prevent recreation',
    )
    
    portal_user_id = fields.Many2one(
        'res.users',
        string='Portal User Who Booked',
        help='Portal user who booked this appointment (for referral partner tracking)',
        index=True,
    )
    
    customer_name = fields.Char(
        string='Customer Name',
        compute='_compute_customer_name',
        store=True,
        help='Name of the customer who booked this appointment (computed from partner)',
    )


    @api.depends('partner_ids')
    def _compute_customer_name(self):
        for record in self:
            customer_partner = record._get_customer_partner()
            record.customer_name = customer_partner.name if customer_partner else False


    @api.depends('task_ids')
    def _compute_task_count(self):
        for record in self:
            try:
                record.task_count = len(record.task_ids) if record.task_ids else 0
            except Exception:
                record.task_count = 0

    def create_snagging_tasks(self):
        """Create snagging tasks based on appointment details"""
        self.ensure_one()
        
        if not self.partner_ids:
            return
        snagging_project = self.env['project.project'].search([
            ('is_snagging_project', '=', True),
            ('active', '=', True)
        ], limit=1)
        
        if not snagging_project:
            return

        if self.tasks_deleted_manually:
            return

        existing_tasks = self.env['project.task'].search([
            ('calendar_event_id', '=', self.id)
        ])
        if existing_tasks:
            return existing_tasks

        if self.env.context.get(f'creating_tasks_{self.id}'):
            return
        self = self.with_context(**{f'creating_tasks_{self.id}': True})
        
        try:
            answers = self.env['appointment.answer.input'].search([
                ('calendar_event_id', '=', self.id)
            ])

            question_answers = {}
            for ans in answers:
                question_name = ans.question_id.name
                question_answers[question_name] = ans.value_text_box or ''

            developer_name = question_answers.get('Developer Name', 'No Developer')
            project_name = question_answers.get('Project Name', 'No Project')
            unit_no = question_answers.get('Unit No', 'No Unit')
            partner = self.partner_ids[0]
            customer_first_name = partner.name.split()[0] if partner.name else 'Customer'

            base_task_name = f"{customer_first_name} / {developer_name} / {project_name} / {unit_no}"

            deadline_2d = False
            deadline_1d = False
            if self.stop:
                import datetime
                stop_datetime = fields.Datetime.from_string(self.stop)
                deadline_2d = stop_datetime + datetime.timedelta(days=2)  # +48h
                deadline_1d = stop_datetime + datetime.timedelta(days=1)  # +24h

            assignee_id = self.user_id.id if self.user_id else False

            tasks_created = []

            final_check = self.env['project.task'].search([
                ('calendar_event_id', '=', self.id)
            ])
            if final_check:
                return final_check

            snagging_task = self.env['project.task'].create({
                'name': f"{base_task_name} / Snagging Report",
                'partner_id': partner.id,
                'project_id': snagging_project.id,
                'date_deadline': deadline_2d,
                'user_ids': [(6, 0, [assignee_id])] if assignee_id else False,
                'calendar_event_id': self.id,
            })
            tasks_created.append(snagging_task)

            submission_task = self.env['project.task'].create({
                'name': f"{base_task_name} / Snagging Report Submission",
                'partner_id': partner.id,
                'project_id': snagging_project.id,
                'date_deadline': deadline_1d,
                'user_ids': [(6, 0, [assignee_id])] if assignee_id else False,
                'calendar_event_id': self.id,
            })
            tasks_created.append(submission_task)

            if tasks_created:
                self.message_post(
                    body=f"✅ Created {len(tasks_created)} snagging task(s) for this appointment.",
                    message_type='notification'
                )

            return tasks_created
        
        except Exception as e:
            return

    def write(self, vals):
        """Override write to handle portal user referral when opportunity is created or changed"""
        result = super().write(vals)

        if 'opportunity_id' in vals and vals['opportunity_id']:
            for record in self:
                record._sync_appointment_to_crm()

        if 'portal_user_id' in vals:
            for record in self:
                if record.opportunity_id:
                    record._sync_appointment_to_crm()

        return result

    def _sync_appointment_to_crm(self):
        """Sync appointment name to CRM lead and handle portal user referrals"""
        self.ensure_one()
        
        if not self.opportunity_id:
            return

        try:
            opportunity = self.opportunity_id
            update_vals = {}
            correct_customer_partner = self._get_customer_partner()
            if correct_customer_partner and opportunity.partner_id != correct_customer_partner:
                update_vals['partner_id'] = correct_customer_partner.id
            if self.name and opportunity.name != self.name:
                if not opportunity.original_name:
                    update_vals['original_name'] = opportunity.name
                update_vals['name'] = self.name
            default_user = self.env['res.users'].search([
                ('is_default_lead_assignee', '=', True),
                ('active', '=', True)
            ], limit=1)
            
            if default_user and opportunity.user_id != default_user:
                update_vals['user_id'] = default_user.id
            if self.portal_user_id:
                portal_user = self.portal_user_id
                if not portal_user._is_public() and portal_user.partner_id.is_referral_partner:
                    if opportunity.referral_partner_id != portal_user.partner_id:
                        update_vals['referral_partner_id'] = portal_user.partner_id.id
                elif portal_user._is_public():
                    pass
                elif not portal_user.partner_id.is_referral_partner:
                    pass
            elif opportunity.referral_partner_id:
                update_vals['referral_partner_id'] = False
            if update_vals:
                opportunity.sudo().with_context(skip_name_formatting=True).write(update_vals)
                if 'referral_partner_id' in update_vals and update_vals['referral_partner_id']:
                    opportunity.sudo()._create_invoice_activity_from_appointment(self)
                    
        except Exception as e:
            pass
    
    def _get_customer_partner(self):
        """Get the correct customer partner using the same logic as customer_name computation"""
        self.ensure_one()
        
        if not self.partner_ids:
            return False
        customer_partner = None
        internal_partners = []
        customer_candidates = []
        
        for partner in self.partner_ids:
            is_internal_user = False
            if partner.user_ids:
                for user in partner.user_ids:
                    if not user.share:
                        is_internal_user = True
                        internal_partners.append(partner)
                        break
            if not is_internal_user:
                customer_candidates.append(partner)
        if customer_candidates:
            customer_partner = max(customer_candidates, key=lambda p: p.create_date or fields.Datetime.now())
        if not customer_partner:
            for partner in self.partner_ids:
                if partner not in internal_partners:
                    customer_partner = partner
                    break
        if not customer_partner and self.partner_ids:
            customer_partner = self.partner_ids[-1]
        
        return customer_partner

    def action_recreate_tasks(self):
        """Manual button to recreate tasks after they were deleted"""
        self.ensure_one()
        self.tasks_deleted_manually = False
        return self.create_snagging_tasks()

    def action_view_tasks(self):
        """Action to view tasks from smart button"""
        self.ensure_one()
        action = self.env.ref('project.action_view_task').read()[0]
        action['domain'] = [('calendar_event_id', '=', self.id)]
        action['context'] = {'default_calendar_event_id': self.id}
        if len(self.task_ids) == 1:
            action['views'] = [(self.env.ref('project.view_task_form2').id, 'form')]
            action['res_id'] = self.task_ids.id
        return action
    
