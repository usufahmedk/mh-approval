# Copyright 2026 M&H Services
"""
Claude Code integration layer for Odoo.sh via XML-RPC.

Provides read/write access to the Odoo database for:
- Querying approval request status
- Creating/managing procurement records
- Triggering workflows programmatically
- Reading configuration data
"""
import xmlrpc.client
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class OdooConfig:
    """Configuration for Odoo.sh connection."""
    url: str
    db: str
    username: str
    password: str
    protocol: str = "jsonrpc"
    port: int = 443


class OdooRPCClient:
    """JSON-RPC client for Odoo.sh integration."""

    def __init__(self, config: OdooConfig):
        self.config = config
        self._uid: Optional[int] = None
        self._models = None
        self._common = None

    def connect(self) -> bool:
        """Establish connection to Odoo.sh instance."""
        endpoint = f"{self.config.url}:{self.config.port}/jsonrpc"
        self._common = xmlrpc.client.ServerProxy(endpoint, allow_none=True)
        self._models = xmlrpc.client.ServerProxy(endpoint, allow_none=True)

        try:
            self._uid = self._common(
                "common", "authenticate",
                self.config.db, self.config.username, self.config.password, {}
            )
            return bool(self._uid)
        except Exception:
            return False

    def execute(self, model: str, method: str, *args, **kwargs) -> Any:
        """Execute a model method via RPC."""
        return self._models(
            "object", "execute_kw",
            self.config.db, self._uid, self.config.password,
            model, method, args, [kwargs] if kwargs else []
        )

    def get_pending_approvals(self, user_id: Optional[int] = None) -> list[dict]:
        """Return all pending approval requests."""
        domain = [("stage_type", "=", "pending")]
        if user_id:
            domain.append(("approver_ids.user_id", "=", user_id))
        return self.execute(
            "approval.request", "search_read", [domain],
            {"fields": ["id", "name", "res_model", "res_id", "create_date"]}
        )

    def get_approval_config(self, model_name: str) -> dict:
        """Get approval workflow config for a specific model."""
        return self.execute(
            "approval.workflow.config", "search_read",
            [("model_id.model", "=", model_name), ("active", "=", True)],
            {"fields": ["id", "name", "domain", "stage_ids"]}
        )

    def get_purchase_orders(self, state: str = "to_approve") -> list[dict]:
        """Retrieve purchase orders by state."""
        return self.execute(
            "purchase.order", "search_read", [("state", "=", state)],
            {"fields": ["id", "name", "partner_id", "amount_total", "approval_state", "create_date"]}
        )

    def get_expenses(self, state: str = "draft") -> list[dict]:
        """Retrieve expense records by state."""
        return self.execute(
            "hr.expense", "search_read", [("state", "=", state)],
            {"fields": ["id", "name", "amount", "employee_id", "approval_state"]}
        )

    def get_vendor_bills(self, state: str = "draft") -> list[dict]:
        """Retrieve vendor bills by state."""
        return self.execute(
            "account.move", "search_read",
            [("move_type", "=", "in_invoice"), ("state", "=", state)],
            {"fields": ["id", "name", "partner_id", "amount_total", "approval_state", "invoice_date"]}
        )

    def submit_for_approval(self, model: str, record_id: int) -> dict:
        """Submit a document for approval."""
        return self.execute(model, "action_submit_for_approval", [record_id])