# Copyright 2026 Abdalrahman Shahrour
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """Extend account.payment with approval workflow capabilities.

    Uses inline pattern to avoid field name collisions.
    Only applies to outgoing payments (vendor payments) that need approval.

    State flow: draft → pending_approval → approved → posted
                                              ↘ rejected
                                              ↘ returned
    """

    _name = "account.payment"
    _inherit = ["account.payment"]

    # --- Re-declare mixin fields to avoid collision ---
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

    # --- Approval compute -------------------------------------------------

    def _compute_approval_request_count(self):
        Request = self.env["approval.request"]
        for record in self:
            record.approval_request_count = Request.search_count(
                [("res_model", "=", record._name), ("res_id", "=", record.id)]
            )

    # --- Approval helpers (inline from approval.mixin) -------------------

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

    def action_submit_for_approval(self):
        """Submit payment(s) for approval."""
        for record in self:
            if record.state != "draft":
                raise UserError(
                    _("Only draft payments can be submitted for approval.")
                )
            if record.approval_state not in ("draft", "returned"):
                raise UserError(
                    _(
                        'Only payments in "Draft" or "Returned" state can be '
                        "submitted for approval."
                    )
                )
            config = record._get_approval_config()
            if not config:
                raise UserError(
                    _('No active approval workflow is configured for model "%s".')
                    % record._name
                )
            if not config.stage_ids:
                raise UserError(
                    _('The approval workflow "%s" has no stages defined.')
                    % config.name
                )
            self.env["approval.request"]._create_from_record(record, config)
            record.write({"approval_state": "pending_approval"})

    def action_view_approval_requests(self):
        """Smart button: open all approval requests linked to this payment."""
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

    # --- Block post until approved ----------------------------------------

    def action_post(self):
        """Require approval before confirming payment.

        Only applies to draft payments that have a workflow config.
        """
        for payment in self:
            if payment.state != "draft":
                continue
            config = payment._get_approval_config()
            if not config:
                continue  # No workflow configured, allow direct post

            if payment.approval_state == "approved":
                continue  # Already approved, proceed

            if payment.approval_state in ("draft", "returned"):
                raise UserError(
                    _(
                        "Submit this payment for approval before confirming. "
                        "Payment: %s."
                    )
                    % payment.display_name
                )
            if payment.approval_state == "pending_approval":
                raise UserError(
                    _(
                        "This payment is still pending approval and cannot be "
                        "confirmed yet. Payment: %s."
                    )
                    % payment.display_name
                )
            if payment.approval_state == "rejected":
                raise UserError(
                    _(
                        "This payment was rejected. Reset to draft and resubmit "
                        "for approval. Payment: %s."
                    )
                    % payment.display_name
                )

        return super().action_post()

    def action_draft(self):
        """Reset approval state when payment is returned to draft."""
        result = super().action_draft()
        self.filtered(lambda p: p.approval_state != "draft").write(
            {"approval_state": "draft"}
        )
        return result