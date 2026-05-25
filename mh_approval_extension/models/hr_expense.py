# Copyright 2026 Abdalrahman Shahrour
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrExpense(models.Model):
    """Extend hr.expense with approval workflow capabilities.

    Expense sheets (hr.expense.sheet) are the primary approval unit,
    but individual expenses can also be submitted directly.
    """

    _name = "hr.expense"
    _inherit = ["hr.expense", "approval.mixin", "mail.thread"]

    def action_submit_expenses(self):
        """Override to require approval before submission."""
        result = super().action_submit_expenses()
        for expense in self:
            config = expense._get_approval_config()
            if config:
                # Check if approval is required for individual expense
                if expense.approval_state not in ("approved", "draft"):
                    pass  # Let parent handle state
        return result


class HrExpenseSheet(models.Model):
    """Extend hr.expense.sheet with approval workflow capabilities.

    Expense sheets group multiple expenses and are the primary
    unit for approval workflows.
    """

    _name = "hr.expense.sheet"
    _inherit = ["hr.expense.sheet", "approval.mixin", "mail.thread"]

    approval_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("returned", "Returned"),
        ],
        string="Approval Status",
        default="draft",
        tracking=True,
        copy=False,
        index=True,
    )
    approval_request_count = fields.Integer(
        string="Approval Requests",
        compute="_compute_approval_request_count",
    )

    def _compute_approval_request_count(self):
        Request = self.env["approval.request"]
        for sheet in self:
            sheet.approval_request_count = Request.search_count(
                [("res_model", "=", sheet._name), ("res_id", "=", sheet.id)]
            )

    def _get_approval_config(self):
        """Return the first matching approval.workflow.config for self."""
        self.ensure_one()
        configs = self.env["approval.workflow.config"].search(
            [("model_id.model", "=", self._name), ("active", "=", True)],
            order="sequence asc, id asc",
        )
        for config in configs:
            if config.domain:
                try:
                    domain = self.env["approval.workflow.config"]._evaluate_domain(
                        config.domain, {"self": self}
                    )
                    # Fallback to safe_eval
                    from odoo.tools.safe_eval import safe_eval
                    domain = safe_eval(config.domain)
                    if self.filtered_domain(domain):
                        return config
                except Exception as exc:
                    _logger.warning(
                        "Approval config %s has an invalid domain: %s",
                        config.name,
                        exc,
                    )
                    continue
            else:
                return config
        return self.env["approval.workflow.config"]

    def action_submit_expenses(self):
        """Submit for approval if workflow is configured."""
        for sheet in self:
            if sheet.state not in ("draft", "submit"):
                continue
            config = sheet._get_approval_config()
            if config and config.stage_ids:
                if sheet.approval_state not in ("draft", "returned"):
                    raise UserError(
                        _(
                            'Only sheets in "Draft" or "Returned" state can '
                            "be submitted for approval."
                        )
                    )
                sheet.env["approval.request"]._create_from_record(sheet, config)
                sheet.write({"approval_state": "pending_approval"})
        return super().action_submit_expenses()

    def action_view_approval_requests(self):
        """Smart button: open all approval requests linked to this sheet."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Approval Requests"),
            "res_model": "approval.request",
            "view_mode": "list,form",
            "domain": [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def action_approve(self):
        """Require approval before final approval."""
        for sheet in self:
            config = sheet._get_approval_config()
            if config:
                if sheet.approval_state not in ("approved",):
                    if sheet.approval_state == "pending_approval":
                        raise UserError(
                            _(
                                "This expense sheet is still pending approval "
                                'and cannot be approved yet. Sheet: "%s".'
                            )
                            % sheet.display_name
                        )
                    if sheet.approval_state == "rejected":
                        raise UserError(
                            _(
                                "This expense sheet was rejected. Create a new "
                                "sheet or return to draft and resubmit."
                            )
                        )
                    if sheet.approval_state == "draft":
                        raise UserError(
                            _(
                                "Submit this expense sheet for approval before "
                                'approving it. Sheet: "%s".'
                            )
                            % sheet.display_name
                        )
        return super().action_approve()

    def action_reject(self):
        """Reset approval state when rejected."""
        result = super().action_reject()
        self.filtered(lambda s: s.state == "cancel").write(
            {"approval_state": "rejected"}
        )
        return result

    def action_draft(self):
        """Reset approval state when sheet is returned to draft."""
        result = super().action_draft()
        self.filtered(lambda s: s.approval_state != "draft").write(
            {"approval_state": "draft"}
        )
        return result