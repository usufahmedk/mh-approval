# Copyright 2026 Abdalrahman Shahrour
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    """Extend purchase.order with approval workflow capabilities.

    Inherits approval.mixin directly since purchase.order does not have
    field name conflicts with the mixin's approval_state and
    approval_request_count fields.
    """

    _name = "purchase.order"
    _inherit = ["purchase.order", "approval.mixin", "mail.thread"]

    # --- Block confirm until approved ---------------------------------

    def button_approve(self, force=False):
        """Require approval before final approval (single-stage lock)."""
        for po in self:
            if po.state in ("draft", "sent", "to_approve"):
                config = po._get_approval_config()
                if config and po.approval_state not in ("approved", "draft"):
                    if po.approval_state == "pending_approval":
                        raise UserError(
                            _(
                                "This quotation is still pending approval "
                                'and cannot be approved yet. Order: "%s".'
                            )
                            % po.display_name
                        )
                    if po.approval_state == "rejected":
                        raise UserError(
                            _(
                                "This quotation was rejected. Return it to "
                                "draft, edit, and resubmit for approval. "
                                'Order: "%s".'
                            )
                            % po.display_name
                        )
        return super().button_approve(force=force)

    def button_draft(self):
        """Reset approval state when PO is returned to draft."""
        result = super().button_draft()
        self.filtered(lambda po: po.approval_state != "draft").write(
            {"approval_state": "draft"}
        )
        return result

    def action_rfq_send(self):
        """Block sending RFQ if pending approval."""
        for po in self:
            if po.state in ("draft", "sent", "to_approve"):
                config = po._get_approval_config()
                if config and po.approval_state == "pending_approval":
                    raise UserError(
                        _(
                            "This quotation is still pending approval and "
                            'cannot be sent yet. Order: "%s".'
                        )
                        % po.display_name
                    )
        return super().action_rfq_send()