from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    crm_lead_id = fields.Many2one(
        'crm.lead',
        string='CRM Lead',
        help='Link to the CRM lead that generated this commission bill',
        index=True,
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-confirm invoice activities when invoices are created"""
        moves = super().create(vals_list)
        
        for move in moves:
            if not move.crm_lead_id and move.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
                crm_lead_found = None
                if hasattr(move, 'invoice_line_ids') and move.invoice_line_ids:
                    for line in move.invoice_line_ids:
                        if hasattr(line, 'sale_line_ids') and line.sale_line_ids:
                            for sale_line in line.sale_line_ids:
                                if hasattr(sale_line.order_id, 'opportunity_id') and sale_line.order_id.opportunity_id:
                                    crm_lead_found = sale_line.order_id.opportunity_id
                                    break
                        if crm_lead_found:
                            break
                if not crm_lead_found and move.invoice_origin:
                    try:
                        sale_orders = self.env['sale.order'].search([
                            ('name', '=', move.invoice_origin)
                        ])
                        for order in sale_orders:
                            if hasattr(order, 'opportunity_id') and order.opportunity_id:
                                crm_lead_found = order.opportunity_id
                                break
                    except Exception as e:
                        pass
                if crm_lead_found:
                    move.crm_lead_id = crm_lead_found.id
            if move.crm_lead_id and move.move_type in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
                move._auto_confirm_invoice_activities()
        
        return moves

    def write(self, vals):
        """Override write to handle CRM lead linking and payment updates"""
        result = super().write(vals)
        
        if 'invoice_origin' in vals and not self.crm_lead_id:
            for move in self:
                move._auto_link_crm_lead_from_origin()
        if ('payment_state' in vals or 'amount_residual' in vals) and not self.env.context.get('skip_crm_update'):
            for move in self:
                if move.crm_lead_id and move.move_type == 'in_invoice' and move.state == 'posted':
                    move._update_crm_paid_amount()
        
        return result
    
    def _auto_link_crm_lead_from_origin(self):
        """Try to link CRM lead from invoice origin (sales order reference)"""
        self.ensure_one()
        
        if not self.invoice_origin or self.crm_lead_id:
            return

        try:
            if 'sale.order' not in self.env:
                return
            sale_orders = self.env['sale.order'].search([
                ('name', '=', self.invoice_origin)
            ])
            
            for order in sale_orders:
                if hasattr(order, 'opportunity_id') and order.opportunity_id:
                    self.crm_lead_id = order.opportunity_id.id
                    break
        except Exception as e:
            pass
    
    def _auto_confirm_invoice_activities(self):
        """Auto-confirm the specific stored invoice activity on the related CRM lead"""
        self.ensure_one()
        
        if not self.crm_lead_id:
            return
        
        try:
            if not self.crm_lead_id.invoice_activity_id:
                return
            
            activity = self.crm_lead_id.invoice_activity_id
            if not activity.exists():
                self.crm_lead_id.invoice_activity_id = False
                return

            if activity.state == 'done':
                self.crm_lead_id.invoice_activity_id = False
                return
            completion_note = f"Invoice created: {self.name} ({self.move_type})"
            
            activity.action_done(feedback=completion_note)
            self.crm_lead_id.invoice_activity_id = False
            
            self.crm_lead_id.message_post(
                body=f"✅ Invoice activity automatically completed: {completion_note}",
                message_type='notification'
            )
                
        except Exception as e:
            pass
    
    def action_post(self):
        """Override action_post to update CRM lead with bill details when commission bill is posted"""
        result = super().action_post()
        
        for move in self:
            if move.crm_lead_id and move.move_type == 'in_invoice':
                move._update_crm_bill_details()
        
        return result
    
    def _update_crm_bill_details(self):
        """Update CRM lead with bill number and paid amount when bill is posted"""
        self.ensure_one()
        
        if not self.crm_lead_id:
            return
        
        try:
            paid_amount = abs(self.amount_total_signed - self.amount_residual_signed)
            vals = {
                'referral_bill_number': self.name,
                'referral_bill_paid_amount': paid_amount,
            }
            
            self.crm_lead_id.write(vals)
            
            self.crm_lead_id.message_post(
                body=f"✅ Commission bill posted: {self.name} (Paid: ${paid_amount:,.2f})",
                message_type='notification'
            )
            
        except Exception as e:
            pass
    
    
    def _update_crm_paid_amount(self):
        """Update CRM lead with current paid amount"""
        self.ensure_one()
        
        if not self.crm_lead_id:
            return
        
        try:
            paid_amount = abs(self.amount_total_signed - self.amount_residual_signed)
            self.crm_lead_id.write({'referral_bill_paid_amount': paid_amount})
            
        except Exception as e:
            pass
    
    def _reconcile_payments(self, payment_lines, writeoff_acc_id=False, writeoff_journal_id=False):
        """Override to update CRM lead when payments are reconciled"""
        result = super()._reconcile_payments(payment_lines, writeoff_acc_id, writeoff_journal_id)
        for move in self:
            if move.crm_lead_id and move.move_type == 'in_invoice' and move.state == 'posted':
                move._update_crm_paid_amount()
        
        return result
    
    def js_assign_outstanding_line(self, line_id):
        """Override to update CRM lead when outstanding payments are assigned"""
        result = super().js_assign_outstanding_line(line_id)
        if self.crm_lead_id and self.move_type == 'in_invoice' and self.state == 'posted':
            self._update_crm_paid_amount()
        
        return result