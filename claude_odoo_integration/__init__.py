"""Claude Code + Odoo.sh integration package."""
from .odoo_client import OdooRPCClient, OdooConfig
from .connection_manager import ConnectionManager

__all__ = ["OdooRPCClient", "OdooConfig", "ConnectionManager"]