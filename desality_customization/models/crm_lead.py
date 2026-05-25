from odoo import models, fields, api
class CrmLead(models.Model):
    _inherit = 'crm.lead'

    referral_partner_id = fields.Many2one(
        'res.partner',
        string='Referral Partner',
        domain="[('is_referral_partner', '=', True)]",
        help='Partner who referred this lead',
        index=True,
    )
    
    unit_type = fields.Selection([
        ('townhouse', 'Townhouse'),
        ('villa', 'Villa'),
        ('apartment', 'Apartment'),
    ], string='Unit Type', help='Type of property unit')
    
    delivery_date = fields.Date(
        string='Delivery Date',
        help='Expected delivery date for this lead/project',
        index=True,
    )
    
    commission_bill_ids = fields.One2many(
        'account.move',
        'crm_lead_id',
        string='Commission Bills',
        help='Vendor bills generated for commissions',
        domain=[('move_type', '=', 'in_invoice')],
    )
    
    commission_bill_count = fields.Integer(
        string='Commission Bills Count',
        compute='_compute_commission_bill_count',
        store=True,
    )
    
    invoice_ids = fields.One2many(
        'account.move',
        'crm_lead_id',
        string='Customer Invoices',
        help='Customer invoices related to this CRM lead',
        domain=[('move_type', 'in', ['out_invoice', 'out_refund'])],
    )
    
    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_count',
    )
    
    original_name = fields.Char(
        string='Original Lead Name',
        help='Stores the original lead name before formatting',
        index=True,
        store=True,
    )
    
    referral_commission_amount = fields.Monetary(
        string='Referral Commission Amount',
        compute='_compute_referral_commission_amount',
        store=True,
        currency_field='company_currency',
        help='Calculated commission amount for the referral partner based on expected revenue and commission percentage',
        readonly=True,
    )
    
    invoice_activity_id = fields.Many2one(
        'mail.activity',
        string='Invoice Activity ID',
        help='ID of the invoice activity created automatically that will be completed when invoice is created from sales order',
        ondelete='set null',
    )
    
    has_confirmed_orders = fields.Boolean(
        string='Has Confirmed Sales Orders',
        compute='_compute_has_confirmed_orders',
        help='True if this lead has confirmed sales orders',
    )
    
    referral_bill_number = fields.Char(
        string='Bill Number',
        help='Bill number from the posted commission bill',
        readonly=True,
        store=True,
        index=True,
    )
    
    referral_bill_paid_amount = fields.Monetary(
        string='Paid Amount',
        help='Amount paid from the commission bill',
        readonly=True,
        store=True,
        currency_field='company_currency',
    )
    
    referral_commission_percentage = fields.Float(
        string='Commission Percentage',
        help='Commission percentage from the referral partner record',
        related='referral_partner_id.referral_commission',
        readonly=True,
        store=True,
        digits=(5, 2),
    )
    
    lost_reason_description = fields.Html(
        string='Lost Reason Description',
        help='Detailed description of why the lead was lost',
        readonly=True,
        store=True,
    )

    @api.depends('commission_bill_ids')
    def _compute_commission_bill_count(self):
        for record in self:
            record.commission_bill_count = len(record.commission_bill_ids)
    
    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)
    
    def _compute_has_confirmed_orders(self):
        for record in self:
            try:

                if hasattr(record, 'order_ids') and record.order_ids:
                    record.has_confirmed_orders = bool(
                        record.order_ids.filtered(lambda o: o.state in ['sale', 'done'])
                    )
                else:

                    if 'sale.order' in self.env:

                        confirmed_orders = self.env['sale.order'].search([
                            ('opportunity_id', '=', record.id),
                            ('state', 'in', ['sale', 'done'])
                        ], limit=1)
                        record.has_confirmed_orders = bool(confirmed_orders)
                    else:

                        record.has_confirmed_orders = False
            except (AttributeError, KeyError):

                if 'sale.order' in self.env:
                    try:
                        confirmed_orders = self.env['sale.order'].search([
                            ('opportunity_id', '=', record.id),
                            ('state', 'in', ['sale', 'done'])
                        ], limit=1)
                        record.has_confirmed_orders = bool(confirmed_orders)
                    except KeyError:
                        record.has_confirmed_orders = False
                else:
                    record.has_confirmed_orders = False
    
    @api.depends('referral_partner_id', 'expected_revenue', 'referral_partner_id.referral_commission')
    def _compute_referral_commission_amount(self):
        for record in self:
            if record.referral_partner_id and record.referral_partner_id.referral_commission > 0 and record.expected_revenue:
                record.referral_commission_amount = record.expected_revenue * record.referral_partner_id.referral_commission / 100.0
            else:
                record.referral_commission_amount = 0.0

    def _format_lead_name(self):
        """Format lead name as: Contact Name - Lead Name - Unit Type"""
        parts = []
        

        if self.contact_name:
            parts.append(self.contact_name)
        

        original_name = self.original_name or self.name
        

        if original_name and ' - ' not in original_name:
            parts.append(original_name)
        elif original_name and ' - ' in original_name:

            name_parts = original_name.split(' - ')
            if len(name_parts) >= 2:

                lead_part = name_parts[1] if len(name_parts) > 2 else name_parts[0]
                if lead_part and lead_part != (self.contact_name or ''):
                    parts.append(lead_part)
        

        if self.unit_type:
            unit_type_display = dict(self._fields['unit_type'].selection).get(self.unit_type)
            if unit_type_display:
                parts.append(unit_type_display)
        
        return ' - '.join(parts) if parts else original_name or 'New Lead'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            if 'name' in vals:
                vals['original_name'] = vals['name']
            

            if not vals.get('user_id'):
                default_user = self.env['res.users'].search([
                    ('is_default_lead_assignee', '=', True),
                    ('active', '=', True)
                ], limit=1)
                if default_user:
                    vals['user_id'] = default_user.id
        

        records = super().create(vals_list)
        

        for record in records:
            if record.partner_id and record.partner_id.user_id and record.partner_id.user_id != record.user_id:

                default_user = self.env['res.users'].search([
                    ('is_default_lead_assignee', '=', True),
                    ('active', '=', True)
                ], limit=1)
                if default_user and record.user_id == default_user:

                    pass
                elif default_user and not record.user_id:

                    record.user_id = default_user
            

            source = self.env.context.get('source', '')
            is_from_appointment = 'appointment' in source.lower() or hasattr(record, 'calendar_event_id')
            
            if not is_from_appointment:
                formatted_name = record._format_lead_name()
                if formatted_name != record.name:

                    super(CrmLead, record.with_context(skip_name_formatting=True)).write({'name': formatted_name})
            

        
        return records

    def _create_invoice_activity_from_appointment(self, calendar_event):
        """Create invoice activity on the CRM lead from appointment"""
        self.ensure_one()
        
        

        appointment_type = None
        if calendar_event and calendar_event.appointment_type_id:
            appointment_type = calendar_event.appointment_type_id
        elif not calendar_event:

            appointment_types = self.env['appointment.type'].search([('invoice_activity_assignee_id', '!=', False)], limit=1)
            if appointment_types:
                appointment_type = appointment_types[0]
            

        assignee = None
        if appointment_type and appointment_type.invoice_activity_assignee_id:
            assignee = appointment_type.invoice_activity_assignee_id
        else:

            assignee = self.user_id or self.env.ref('base.user_admin')
            

        try:
            activity_type = self.env.ref('mail.mail_activity_data_todo')
        except:
            activity_type = self.env['mail.activity.type'].search([('name', '=', 'To Do')], limit=1)
            
        if not activity_type:
            return
            

        crm_lead_model = self.env['ir.model'].search([('model', '=', 'crm.lead')], limit=1)
        if not crm_lead_model:
            return
        

        activity_vals = {
            'activity_type_id': activity_type.id,
            'summary': f'Create Invoice for {self.name}',
            'note': f'Appointment: {calendar_event.name}\nReferral Partner: {self.referral_partner_id.name}',
            'res_model': 'crm.lead',
            'res_model_id': crm_lead_model.id,
            'res_id': self.id,
            'user_id': assignee.id,
            'date_deadline': fields.Date.today(),
        }
        
        activity = self.env['mail.activity'].create(activity_vals)
        

        self.invoice_activity_id = activity.id
        
        return activity

    
    def _check_invoice_activity_completion(self):
        """Check if the stored invoice activity has been manually completed and clear if so"""
        for record in self:
            if record.invoice_activity_id:
                if not record.invoice_activity_id.exists() or record.invoice_activity_id.state == 'done':
                            record.invoice_activity_id = False
    def write(self, vals):

        if self.env.context.get('skip_name_formatting'):
            return super().write(vals)
        
        for record in self:
            if not record.original_name:
                current_name = record.name or ''
                if ' - ' in current_name:
                    parts = current_name.split(' - ')
                    if len(parts) >= 2:
                        original_name = parts[1] if record.contact_name and parts[0] == record.contact_name else parts[0]
                    else:
                        original_name = current_name
                else:
                    original_name = current_name
                super(CrmLead, record.with_context(skip_name_formatting=True)).write({'original_name': original_name})
        
        if 'name' in vals and not any(field in vals for field in ['contact_name', 'unit_type']):
            vals['original_name'] = vals['name']
        
        result = super().write(vals)
        
        if 'invoice_activity_id' in vals:
            for record in self:
                pass
        
        if any(field in vals for field in ['contact_name', 'name', 'unit_type']):
            for record in self:
                is_from_appointment = False
                if hasattr(record, 'calendar_event_ids') and record.calendar_event_ids:
                    is_from_appointment = True
                
                if is_from_appointment and 'unit_type' not in vals:
                    continue
                
                formatted_name = record._format_lead_name()
                if formatted_name != record.name:
                        super(CrmLead, record.with_context(skip_name_formatting=True)).write({'name': formatted_name})
        
        return result

    def _get_sales_order_details(self):
        """Helper method to format sales order product details for commission bills"""

        try:
            if not hasattr(self, 'order_ids') or not self.order_ids:
                return ""
            

            confirmed_orders = self.order_ids.filtered(lambda o: o.state in ['sale', 'done'])
        except (AttributeError, KeyError):

            if 'sale.order' in self.env:
                try:

                    confirmed_orders = self.env['sale.order'].search([
                        ('opportunity_id', '=', self.id),
                        ('state', 'in', ['sale', 'done'])
                    ])
                except KeyError:
                    return ""
            else:

                return ""
        
        if not confirmed_orders:
            return ""
        
        details = ["\n\nConfirmed Sales Orders:"]
        
        for order in confirmed_orders:
            details.append(f"{order.name}:")
            for line in order.order_line:
                if line.product_id:  # Only include product lines
                    details.append(f"- {line.product_id.name} (Qty: {int(line.product_uom_qty)}) @ ${line.price_unit:,.2f}")
        
        return "\n".join(details)

    def action_view_commission_bills(self):
        """Action to view commission bills from smart button - purchase journal only"""
        self.ensure_one()
        action = self.env.ref('account.action_move_in_invoice_type').read()[0]
        action['domain'] = [
            ('crm_lead_id', '=', self.id),
            ('move_type', '=', 'in_invoice')
        ]
        action['context'] = {'default_move_type': 'in_invoice', 'default_crm_lead_id': self.id}
        if len(self.commission_bill_ids) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = self.commission_bill_ids.id
        return action

    def action_view_invoices(self):
        """Action to view customer invoices from smart button"""
        self.ensure_one()
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [
            ('crm_lead_id', '=', self.id),
            ('move_type', 'in', ['out_invoice', 'out_refund'])
        ]
        action['context'] = {'default_move_type': 'out_invoice', 'default_crm_lead_id': self.id}
        if len(self.invoice_ids) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = self.invoice_ids.id
        return action

    def create_commission_bills(self):
        """Create vendor bills for referral and ambassador commissions"""
        self.ensure_one()
        
        if not self.referral_partner_id:
            return
        

        existing_bills = self.env['account.move'].search([
            ('crm_lead_id', '=', self.id),
            ('move_type', '=', 'in_invoice')
        ])
        if existing_bills:
            return existing_bills
        

        commission_product = self.env['product.template'].search([
            ('is_commission_product', '=', True)
        ], limit=1)
        
        if not commission_product:
            return
        

        commission_product_variant = commission_product.product_variant_id
        
        expected_revenue = self.expected_revenue or 0.0
        bills_created = []
        

        if self.referral_partner_id.referral_commission > 0:
            referral_amount = expected_revenue * self.referral_partner_id.referral_commission / 100.0
            base_description = f"Referral Commission - {self.name}"
            sales_order_details = self._get_sales_order_details()
            full_description = base_description + sales_order_details
            
            referral_bill = self._create_commission_bill(
                partner=self.referral_partner_id,
                product=commission_product_variant,
                amount=referral_amount,
                description=full_description
            )
            if referral_bill:
                bills_created.append(referral_bill)
        


        ambassador_user = self.referral_partner_id.user_id
        if ambassador_user and ambassador_user.partner_id.ambassador_commission > 0:
            ambassador_partner = ambassador_user.partner_id
            ambassador_amount = expected_revenue * ambassador_partner.ambassador_commission / 100.0
            base_description = f"Ambassador Commission - {self.name}"
            sales_order_details = self._get_sales_order_details()
            full_description = base_description + sales_order_details
            
            ambassador_bill = self._create_commission_bill(
                partner=ambassador_partner,
                product=commission_product_variant,
                amount=ambassador_amount,
                description=full_description
            )
            if ambassador_bill:
                bills_created.append(ambassador_bill)
        
        if bills_created:
            self.message_post(
                body=f"✅ Created {len(bills_created)} commission bill(s) for this opportunity.",
                message_type='notification'
            )
        
        return bills_created
    
    def _create_commission_bill(self, partner, product, amount, description):
        """Helper method to create individual commission bill"""
        try:

            journal = self.env['account.journal'].search([
                ('type', '=', 'purchase'),
                ('company_id', '=', self.company_id.id or self.env.company.id)
            ], limit=1)
            
            if not journal:
                    return False
            

            expense_account = (
                product.property_account_expense_id or
                product.categ_id.property_account_expense_categ_id or
                self.env['account.account'].search([
                    ('company_id', '=', self.company_id.id or self.env.company.id),
                    ('account_type', '=', 'expense'),
                    ('deprecated', '=', False),
                ], limit=1)
            )
            
            if not expense_account:
                    return False
            
            bill_vals = {
                'move_type': 'in_invoice',
                'journal_id': journal.id,
                'partner_id': partner.id,
                'crm_lead_id': self.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id,
                    'name': description,
                    'quantity': 1,
                    'price_unit': amount,
                    'account_id': expense_account.id,
                })],
            }
            
            bill = self.env['account.move'].sudo().create(bill_vals)
            return bill
            
        except Exception as e:
            pass
            return False
class CrmLeadLost(models.TransientModel):
    _inherit = 'crm.lead.lost'

    def action_lost_reason_apply(self):
        """Override to save lost_feedback to CRM lead's lost_reason_description field"""

        if self.lost_feedback and self.lead_ids:
            self.lead_ids.write({'lost_reason_description': self.lost_feedback})
        

        return super().action_lost_reason_apply()